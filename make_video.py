"""
Sora動画に音声＋UGCテロップを合成するスクリプト
ffmpegベースで確実に動作
"""
import os
import subprocess
from PIL import Image, ImageDraw, ImageFont
import numpy as np

FONT_PATH = "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"
VIDEO_PATH = "/home/user/cl1/sora_silent.mp4"
AUDIO_PATH = "/home/user/cl1/tts_output.mp3"
OUTPUT_PATH = "/home/user/cl1/output_final.mp4"
FFMPEG = "/usr/local/bin/ffmpeg"

W, H = 704, 1280
FONT_SIZE = 76

SUBTITLES = [
    ("こんばんは", 0.0, 1.0),
    ("リナです", 1.0, 1.9),
    ("今日も歌います", 1.9, 3.4),
    ("聴いてね", 3.4, 4.3),
]


def make_text_png(text, out_path):
    """白文字+黒枠のUGCスタイルテキスト画像を生成"""
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    font = ImageFont.truetype(FONT_PATH, FONT_SIZE)

    bbox = draw.textbbox((0, 0), text, font=font)
    text_w = bbox[2] - bbox[0]
    x = (W - text_w) // 2
    y = int(H * 0.72)

    # 黒枠
    draw.text((x, y), text, font=font, fill=(0, 0, 0, 255),
              stroke_width=8, stroke_fill=(0, 0, 0, 255))
    # 白文字
    draw.text((x, y), text, font=font, fill=(255, 255, 255, 255))

    img.save(out_path)


def build_ffmpeg_overlay_filter():
    """複数テロップのoverlayフィルターを構築"""
    # まずPNG画像を生成してffmpegのoverlay入力として使う
    inputs = []
    filter_parts = []
    input_idx = 2  # 0=video, 1=audio

    for i, (text, start, end) in enumerate(SUBTITLES):
        png_path = f"/tmp/sub_{i}.png"
        make_text_png(text, png_path)
        inputs.extend(["-i", png_path])

    # filterグラフ構築
    prev = "[0:v]"
    filter_chains = []
    for i, (text, start, end) in enumerate(SUBTITLES):
        out_label = f"[v{i}]" if i < len(SUBTITLES) - 1 else "[vout]"
        chain = (
            f"{prev}[{i+2}:v]overlay="
            f"x=0:y=0:"
            f"enable='between(t,{start},{end})'"
            f"{out_label}"
        )
        filter_chains.append(chain)
        prev = f"[v{i}]"

    filter_str = ";".join(filter_chains)
    return inputs, filter_str


def main():
    print("Generating subtitle PNGs...")
    input_extras, filter_str = build_ffmpeg_overlay_filter()

    cmd = [
        FFMPEG, "-y",
        "-i", VIDEO_PATH,
        "-i", AUDIO_PATH,
    ] + input_extras + [
        "-filter_complex", filter_str,
        "-map", "[vout]",
        "-map", "1:a",
        "-c:v", "libx264",
        "-c:a", "aac",
        "-shortest",
        OUTPUT_PATH,
    ]

    print("Running ffmpeg...")
    print(" ".join(cmd))
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print("STDERR:", result.stderr[-3000:])
        raise RuntimeError("ffmpeg failed")

    size = os.path.getsize(OUTPUT_PATH) / 1024 / 1024
    print(f"Done! {OUTPUT_PATH} ({size:.1f} MB)")


if __name__ == "__main__":
    main()
