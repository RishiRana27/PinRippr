from flask import Flask, render_template, request, jsonify, send_file
import requests
from bs4 import BeautifulSoup
import os
import random
import json
import re

app = Flask(__name__)
DOWNLOAD_FOLDER = "downloads"
os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/get_media_url", methods=["POST"])
def get_media_url():
    pin_url = request.form.get("pin_url")
    if not pin_url:
        return jsonify({"error": "Please provide a valid Pinterest URL. Like : https://pin.it/4NNqWD9nS"}), 400

    try:
        headers = {
            "User-Agent": "Mozilla/5.0"
        }
        response = requests.get(pin_url, headers=headers)
        if response.status_code != 200:
            return jsonify({"error": "Failed to fetch the Pinterest page."}), 400

        soup = BeautifulSoup(response.text, "html.parser")
        scripts = soup.find_all('script')

        # 1. Try to get video from contentUrl in JSON inside script
        for script in scripts:
            if script.string and 'contentUrl' in script.string:
                json_text_match = re.search(r'{.*"contentUrl":.*}', script.string)
                if json_text_match:
                    try:
                        data = json.loads(json_text_match.group())
                        media_url = data.get("contentUrl")
                        if media_url:
                            head_resp = requests.head(media_url, headers=headers)
                            if "video" in head_resp.headers.get("Content-Type", "").lower():
                                return jsonify({"media_url": media_url, "media_type": "video"})
                    except json.JSONDecodeError:
                        continue

        # 2. Check for GIFs before normal image
        images = soup.find_all("img")
        for img in images:
            src = img.get("src", "")
            alt = img.get("alt", "")
            if src.lower().endswith(".gif") and "pinimg.com/originals" in src:
                return jsonify({"media_url": src, "media_type": "gif"})

        # 3. Try to get image from <meta property="og:image">
        og_image = soup.find("meta", property="og:image")
        if og_image and og_image.get("content"):
            return jsonify({"media_url": og_image["content"], "media_type": "image"})

        # 4. Fallback: any valid image
        for img in images:
            src = img.get("src")
            if src and src.startswith("https://"):
                return jsonify({"media_url": src, "media_type": "image"})

        return jsonify({"error": "Media URL not found."}), 404

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/download", methods=["POST"])
def download_media():
    media_url = request.form.get("media_url")
    if not media_url:
        return "Invalid media URL.", 400

    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(media_url, headers=headers, stream=True)
        if response.status_code != 200:
            return "Failed to download media.", 400

        content_type = response.headers.get("Content-Type", "").lower()
        if "video" in content_type:
            ext = ".mp4"
        elif "image" in content_type:
            if "jpeg" in content_type:
                ext = ".jpg"
            elif "png" in content_type:
                ext = ".png"
            elif "gif" in content_type:
                ext = ".gif"
            else:
                ext = ".jpg" 
        else:
            ext = ".bin"

        filename = f"Pinterest_{random.randint(1, 100)}{ext}"
        file_path = os.path.join(DOWNLOAD_FOLDER, filename)

        # Save file in chunks to avoid memory issues
        with open(file_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)

        return jsonify({"filename": filename})

    except Exception as e:
        return f"Error: {str(e)}", 500

@app.route("/download_file/<filename>")
def download_file(filename):
    file_path = os.path.join(DOWNLOAD_FOLDER, filename)
    if not os.path.exists(file_path):
        return "File not found", 404
    return send_file(file_path, as_attachment=True)

if __name__ == "__main__":
    app.run(debug=True)
