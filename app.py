import os
import uuid
import requests
import subprocess
from flask import Flask, request, jsonify
from datetime import datetime
import threading

app = Flask(__name__, static_folder="static")

# Ensure output folder exists
os.makedirs("static", exist_ok=True)

@app.route("/")
def home():
    return "🎬 FFmpeg API is running on Render."

@app.route("/generate-video", methods=["POST"])
def generate_video():
    scenes = request.json.get("scenes", [])
    if not scenes:
        return jsonify({"error": "Missing scenes array"}), 400

    unique_id = str(uuid.uuid4())
    threading.Thread(target=process_scenes, args=(scenes, unique_id)).start()

    return jsonify({
        "message": "🎬 Video generation started",
        "video_url": f"/static/{unique_id}_final_reel.mp4",
        "status": "processing"
    })


def process_scenes(scenes, unique_id):
    try:
        os.makedirs(f"temp/{unique_id}", exist_ok=True)
        concat_entries = []

        for idx, scene in enumerate(scenes):
            image_url = scene.get("image_url")
            audio_url = scene.get("audio_url")
            subtitle_text = scene.get("subtitle", f"Scene {idx+1}")

            if not image_url or not audio_url:
                continue

            image_path = f"temp/{unique_id}/scene_{idx}.jpg"
            audio_path = f"temp/{unique_id}/scene_{idx}.mp3"
            subtitle_path = f"temp/{unique_id}/scene_{idx}.ass"
            output_path = f"temp/{unique_id}/scene_{idx}.mp4"

            # Download image/audio
            with open(image_path, "wb") as f:
                f.write(requests.get(image_url).content)
            with open(audio_path, "wb") as f:
                f.write(requests.get(audio_url).content)

            # Create subtitle
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

            # FFmpeg command
            cmd = [
                "ffmpeg",
                "-loop", "1",
                "-i", image_path,
                "-i", audio_path,
                "-vf", f"scale=1080:1920,ass={subtitle_path}",
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
            subprocess.run(cmd, check=True)
            concat_entries.append(f"file '{output_path}'")

        # Concatenate videos
        concat_file = f"temp/{unique_id}/concat.txt"
        with open(concat_file, "w") as f:
            f.write("\n".join(concat_entries))

        final_path = f"static/{unique_id}_final_reel.mp4"
        concat_cmd = [
            "ffmpeg", "-f", "concat", "-safe", "0", "-i",
            concat_file, "-c", "copy", final_path
        ]
        subprocess.run(concat_cmd, check=True)

        # Cleanup
        subprocess.run(["rm", "-rf", f"temp/{unique_id}"])

    except Exception as e:
        print(f"Error during background video generation: {e}")



if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
