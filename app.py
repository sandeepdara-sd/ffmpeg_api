import os
import uuid
import requests
import subprocess
from flask import Flask, request, jsonify
from datetime import datetime

app = Flask(__name__, static_folder="static")

# Ensure output folder exists
os.makedirs("static", exist_ok=True)

@app.route("/")
def home():
    return "🎬 FFmpeg API is running on Render."

@app.route("/generate-video", methods=["POST"])
def generate_video():
    scenes = request.json.get("scenes", [])

    if not scenes or not isinstance(scenes, list):
        return jsonify({"error": "Invalid or missing 'scenes' list"}), 400

    segment_paths = []

    for i, scene in enumerate(scenes):
        image_url = scene.get("image_url")
        audio_url = scene.get("audio_url")
        subtitle_text = scene.get("subtitle", f"Scene {i+1}")

        if not image_url or not audio_url:
            return jsonify({"error": f"Missing data in scene {i+1}"}), 400

        uid = f"{uuid.uuid4()}_{i}"
        image_path = f"{uid}_image.jpg"
        audio_path = f"{uid}_audio.mp3"
        subtitle_path = f"{uid}.ass"
        output_path = f"{uid}_output.mp4"

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
Dialogue: 0,0:00:00.00,0:00:10.00,Default,{subtitle_text}
"""
        with open(subtitle_path, "w") as f:
            f.write(ass_content.strip())

        # Create individual video segment
        cmd = [
            "ffmpeg",
            "-loop", "1",
            "-i", image_path,
            "-i", audio_path,
            "-vf", f"scale=1080:1920,ass={subtitle_path}",
            "-c:v", "libx264",
            "-preset", "ultrafast",
            "-tune", "stillimage",
            "-pix_fmt", "yuv420p",
            "-c:a", "aac",
            "-b:a", "128k",
            "-shortest",
            "-y",
            output_path
        ]

        try:
            subprocess.run(cmd, check=True)
            segment_paths.append(output_path)
        except subprocess.CalledProcessError as e:
            return jsonify({"error": "FFmpeg failed", "scene": i + 1, "details": str(e)}), 500
        finally:
            for f in [image_path, audio_path, subtitle_path]:
                if os.path.exists(f):
                    os.remove(f)

    # Merge all segments into one video using concat
    concat_list_path = "concat_list.txt"
    with open(concat_list_path, "w") as f:
        for path in segment_paths:
            f.write(f"file '{path}'\n")

    final_output = f"static/{uuid.uuid4()}_final.mp4"
    cmd_concat = [
        "ffmpeg",
        "-f", "concat",
        "-safe", "0",
        "-i", concat_list_path,
        "-c", "copy",
        "-y",
        final_output
    ]

    try:
        subprocess.run(cmd_concat, check=True)
    except subprocess.CalledProcessError as e:
        return jsonify({"error": "Merging video failed", "details": str(e)}), 500
    finally:
        os.remove(concat_list_path)
        for f in segment_paths:
            if os.path.exists(f):
                os.remove(f)

    return jsonify({"video_url": f"/{final_output}"})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
