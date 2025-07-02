import os
import uuid
import requests
import subprocess
from flask import Flask, request, jsonify, send_file

app = Flask(__name__)

@app.route('/')
def home():
    return "🎬 FFmpeg API is running on Render."

@app.route('/generate-video', methods=['POST'])
def generate_video():
    try:
        data = request.json
        image_url = data['image_url']
        audio_url = data['audio_url']
        subtitle = data['subtitle']

        uid = str(uuid.uuid4())
        image_path = f"{uid}_img.jpg"
        audio_path = f"{uid}_audio.mp3"
        output_path = f"{uid}_video.mp4"
        subtitle_file = f"{uid}_subs.ass"

        # Download assets
        with open(image_path, 'wb') as f:
            f.write(requests.get(image_url).content)
        with open(audio_path, 'wb') as f:
            f.write(requests.get(audio_url).content)

        # Create subtitles
        with open(subtitle_file, 'w', encoding='utf-8') as f:
            f.write(f"""
[Script Info]
ScriptType: v4.00+

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, BackColour, Bold, Italic, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Arial,40,&H00FFFFFF,&H80000000,-1,0,1,2,0,2,30,30,80,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
Dialogue: 0,0:00:00.00,0:05:00.00,Default,,0,0,0,,{subtitle}
""")

        # FFmpeg video
        cmd = [
            "ffmpeg",
            "-y",
            "-loop", "1",
            "-i", image_path,
            "-i", audio_path,
            "-vf", f"ass={subtitle_file},scale=1080:1920",
            "-shortest",
            "-c:v", "libx264",
            "-c:a", "aac",
            "-b:a", "192k",
            "-pix_fmt", "yuv420p",
            output_path
        ]
        subprocess.run(cmd, check=True)

        # Serve file and clean up AFTER response is done
        def generate():
            with open(output_path, 'rb') as f:
                yield from f
            for file in [image_path, audio_path, subtitle_file, output_path]:
                try:
                    os.remove(file)
                except Exception as e:
                    print(f"⚠️ Could not delete {file}: {e}")

        return app.response_class(generate(), mimetype='video/mp4')

    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == '__main__':
    app.run(host="0.0.0.0", port=5000)
