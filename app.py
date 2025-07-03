import os
import uuid
import requests
import subprocess
from flask import Flask, request, jsonify, send_from_directory
from datetime import datetime

app = Flask(__name__, static_folder="static")

# Ensure output folder exists
os.makedirs("static", exist_ok=True)


@app.route("/")
def home():
    return "🎬 FFmpeg API is running on Render."

@app.route("/merge-videos", methods=["POST"])
def merge_videos():
    data = request.json
    

    # Handle case where input is directly a list
    if isinstance(data, list):
        video_urls = [item["video_url"] for item in data]
    else:
        video_urls = data.get("video_urls")


    if not video_urls or not isinstance(video_urls, list) or len(video_urls) < 2:
        return jsonify({"error": "Provide at least two video URLs in a list under 'video_urls'"}), 400

    # Generate unique ID for merged video
    unique_id = str(uuid.uuid4())
    output_path = f"static/{unique_id}_merged.mp4"

    # Download all videos and prepare a file list
    temp_video_paths = []
    list_file_path = f"{unique_id}_list.txt"
    with open(list_file_path, "w") as list_file:
        for i, url in enumerate(video_urls):
            video_name = f"{unique_id}_part{i}.mp4"
            video_path = os.path.join("static", video_name)
            try:
                with open(video_path, "wb") as f:
                    f.write(requests.get(url).content)
            except Exception as e:
                return jsonify({"error": f"Failed to download video: {url}", "details": str(e)}), 500
            temp_video_paths.append(video_path)
            list_file.write(f"file '{video_path}'\n")

    # FFmpeg command to merge using concat demuxer
    cmd = [
        "ffmpeg",
        "-f", "concat",
        "-safe", "0",
        "-i", list_file_path,
        "-c", "copy",
        output_path
    ]

    try:
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as e:
        return jsonify({"error": "FFmpeg merge failed", "details": str(e)}), 500
    finally:
        # Cleanup temp files
        for file in temp_video_paths + [list_file_path]:
            if os.path.exists(file):
                os.remove(file)

    video_url = f"/static/{os.path.basename(output_path)}"
    return jsonify({"merged_video_url": video_url})



@app.route("/generate-video", methods=["POST"])
def generate_video():
    data = request.json
    image_url = data.get("image_url")
    audio_url = data.get("audio_url")
    subtitle_text = data.get("subtitle", "Hello from AI 🎉")

    if not image_url or not audio_url:
        return jsonify({"error": "Missing image_url or audio_url"}), 400

    # Generate unique ID
    unique_id = str(uuid.uuid4())
    image_path = f"{unique_id}_image.jpg"
    audio_path = f"{unique_id}_audio.mp3"
    subtitle_path = f"{unique_id}.ass"
    output_path = f"static/{unique_id}_output.mp4"

    # Download image
    with open(image_path, "wb") as f:
        f.write(requests.get(image_url).content)

    # Download audio
    with open(audio_path, "wb") as f:
        f.write(requests.get(audio_url).content)

    # Create .ass subtitle file
    ass_content = f"""
[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, BackColour, Bold, Italic, Alignment, MarginL, MarginR, MarginV, BorderStyle, Outline, Shadow, Encoding
Style: Default,Arial,50,&H00FFFFFF,&H00000000,-1,0,2,10,10,50,1,2,0,0

[Events]
Format: Layer, Start, End, Style, Text
Dialogue: 0,0:00:00.00,0:00:07.00,Default,{subtitle_text}
"""

    with open(subtitle_path, "w") as f:
        f.write(ass_content.strip())

    # Run FFmpeg command
    cmd = [
        "ffmpeg",
        "-loop", "1",
        "-i", image_path,
        "-i", audio_path,
        "-vf", f"scale=trunc(iw/2)*2:trunc(ih/2)*2,ass={subtitle_path}",
        "-c:v", "libx264",
        "-preset", "ultrafast",
        "-tune", "stillimage",
        "-t", "7",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        "-b:a", "128k",
        "-shortest",
        output_path
    ]



    try:
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as e:
        return jsonify({"error": "FFmpeg failed", "details": str(e)}), 500
    finally:
        # Clean up temp files
        for file in [image_path, audio_path, subtitle_path]:
            if os.path.exists(file):
                os.remove(file)

    video_url = f"/static/{os.path.basename(output_path)}"
    return jsonify({"video_url": video_url})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
