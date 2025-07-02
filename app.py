import os
import uuid
import json
import requests
import subprocess
from flask import Flask, request, jsonify, send_file, after_this_request

app = Flask(__name__)

@app.route('/')
def home():
    return "🎬 FFmpeg API is running on Render."

@app.route('/generate-video', methods=['POST'])
def generate_video():
    try:
        data = request.get_json(force=True)
        image_url = data.get('image_url')
        audio_url = data.get('audio_url')
        subtitle = data.get('subtitle', '')

        if not all([image_url, audio_url, subtitle]):
            return jsonify({"error": "Missing one or more required fields"}), 400

        uid = str(uuid.uuid4())
        image_path = f"{uid}_image.jpg"
        audio_path = f"{uid}_audio.mp3"
        subtitle_path = f"{uid}.ass"
        output_path = f"{uid}_output.mp4"

        # Download image and audio
        with open(image_path, "wb") as f:
            f.write(requests.get(image_url).content)
        with open(audio_path, "wb") as f:
            f.write(requests.get(audio_url).content)

        # Get audio duration
        probe = subprocess.run([
            "ffprobe", "-v", "error", "-show_entries",
            "format=duration", "-of", "json", audio_path
        ], capture_output=True, text=True)

        duration_data = json.loads(probe.stdout)
        duration = float(duration_data["format"]["duration"])
        end_time = f"0:00:{int(duration):02d}.00"

        # Generate subtitle file
        with open(subtitle_path, 'w', encoding='utf-8') as f:
            f.write(f"""
[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, BackColour, Bold, Italic, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Arial,48,&H00FFFFFF,&H80000000,-1,0,1,2,0,2,30,30,80,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
Dialogue: 0,0:00:00.00,{end_time},Default,,0,0,0,,{subtitle}
""")

        # Run FFmpeg
        ffmpeg_cmd = [
            "ffmpeg",
            "-y",
            "-loop", "1",
            "-i", image_path,
            "-i", audio_path,
            "-vf", f"ass={subtitle_path},scale=1080:1920",
            "-t", str(duration),
            "-c:v", "libx264",
            "-c:a", "aac",
            "-b:a", "192k",
            "-pix_fmt", "yuv420p",
            "-shortest",
            output_path
        ]
        subprocess.run(ffmpeg_cmd, check=True)

        # Clean up after request
        @after_this_request
        def cleanup(response):
            for f in [image_path, audio_path, subtitle_path, output_path]:
                try:
                    os.remove(f)
                except Exception as e:
                    print(f"⚠️ Could not delete {f}: {e}")
            return response

        # Send the generated video
        return send_file(output_path, mimetype='video/mp4', as_attachment=False)

    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
