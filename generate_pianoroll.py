import mido
from PIL import Image, ImageDraw
import os
import math
import random

# --- 設定 ---
MIDI_FILE = "/home/user/cl1/song.mid"
OUTPUT_DIR = "/home/user/cl1/pianoroll_frames"
FPS = 30
VIDEO_DURATION = 16.05
FRAME_WIDTH = 786
FRAME_HEIGHT = 200
TIME_OFFSET = 0.0

CURSOR_X = 0.20       # カーソル固定位置（左20%）
PPS = 100             # pixels per second

NOTE_MIN = 36
NOTE_MAX = 84

os.makedirs(OUTPUT_DIR, exist_ok=True)

mid = mido.MidiFile(MIDI_FILE)
ticks_per_beat = mid.ticks_per_beat

tempo_map = [(0, 500000)]
for track in mid.tracks:
    abs_tick = 0
    for msg in track:
        abs_tick += msg.time
        if msg.type == 'set_tempo':
            tempo_map.append((abs_tick, msg.tempo))
tempo_map.sort(key=lambda x: x[0])

def tick_to_seconds(abs_tick):
    elapsed = 0.0
    prev_tick, prev_tempo = 0, 500000
    for tick, tempo in tempo_map:
        if tick >= abs_tick:
            break
        elapsed += mido.tick2second(tick - prev_tick, ticks_per_beat, prev_tempo)
        prev_tick, prev_tempo = tick, tempo
    elapsed += mido.tick2second(abs_tick - prev_tick, ticks_per_beat, prev_tempo)
    return elapsed

notes = []
for track in mid.tracks:
    abs_tick = 0
    active = {}
    for msg in track:
        abs_tick += msg.time
        if msg.type == 'note_on' and msg.velocity > 0:
            active[msg.note] = abs_tick
        elif msg.type in ('note_off', 'note_on') and msg.velocity == 0:
            if msg.note in active:
                start_sec = tick_to_seconds(active.pop(msg.note)) + TIME_OFFSET
                end_sec   = tick_to_seconds(abs_tick) + TIME_OFFSET
                notes.append((start_sec, end_sec, msg.note))

print(f"Notes loaded: {len(notes)}")
NOTE_RANGE = NOTE_MAX - NOTE_MIN

def pitch_color(note, is_active):
    ratio = (note - NOTE_MIN) / NOTE_RANGE
    hue = ratio * 270
    h = hue / 60.0
    i = int(h)
    f = h - i
    if i == 0:   r, g, b = 255, int(255*f), 0
    elif i == 1: r, g, b = int(255*(1-f)), 255, 0
    elif i == 2: r, g, b = 0, 255, int(255*f)
    elif i == 3: r, g, b = 0, int(255*(1-f)), 255
    elif i == 4: r, g, b = int(255*f), 0, 255
    else:        r, g, b = 255, 0, int(255*(1-f))
    if is_active:
        r = min(255, r + 70)
        g = min(255, g + 70)
        b = min(255, b + 70)
        return (r, g, b, 240)
    return (r, g, b, 180)

def draw_sparks(draw, cx, cy, color, time_since_hit, note_seed):
    """音符がカーソルに当たった瞬間の火花エフェクト"""
    SPARK_DURATION = 0.18  # 火花の持続時間（秒）
    if time_since_hit < 0 or time_since_hit > SPARK_DURATION:
        return
    r, g, b, _ = color
    progress = time_since_hit / SPARK_DURATION  # 0→1（消えていく）
    rng = random.Random(note_seed)

    # 火花: 外側に広がる小さな点
    for _ in range(12):
        angle = rng.uniform(0, 2 * math.pi)
        speed = rng.uniform(25, 65)
        dist = speed * time_since_hit
        sx = cx + int(dist * math.cos(angle))
        sy = cy + int(dist * math.sin(angle))
        size = max(1, int(3.5 * (1 - progress)))
        alpha = int(220 * (1 - progress))

        # ランダムに白か音符色の火花
        if rng.random() > 0.4:
            fc = (min(255,r+80), min(255,g+80), min(255,b+80), alpha)
        else:
            fc = (255, 255, 200, alpha)

        draw.ellipse([sx-size, sy-size, sx+size, sy+size], fill=fc)

    # 中心に明るいフラッシュ（ヒット直後だけ）
    if progress < 0.3:
        flash_r = int(10 * (0.3 - progress) / 0.3)
        flash_a = int(180 * (1 - progress / 0.3))
        draw.ellipse([cx-flash_r, cy-flash_r, cx+flash_r, cy+flash_r],
                     fill=(255, 255, 255, flash_a))

total_frames = int(VIDEO_DURATION * FPS)

for frame_idx in range(total_frames):
    current_time = frame_idx / FPS
    cursor_x = int(FRAME_WIDTH * CURSOR_X)

    img = Image.new("RGBA", (FRAME_WIDTH, FRAME_HEIGHT), (0, 0, 0, 0))
    bg = Image.new("RGBA", (FRAME_WIDTH, FRAME_HEIGHT), (0, 0, 0, 102))
    img = Image.alpha_composite(img, bg)
    draw = ImageDraw.Draw(img)

    spark_queue = []  # (cx, cy, color, time_since_hit, seed)

    for start_sec, end_sec, note in notes:
        if note < NOTE_MIN or note > NOTE_MAX:
            continue

        x1 = cursor_x + int((start_sec - current_time) * PPS)
        x2 = cursor_x + int((end_sec   - current_time) * PPS)
        x2 = max(x2, x1 + 3)

        if x2 < 0 or x1 > FRAME_WIDTH:
            continue

        y_ratio = (note - NOTE_MIN) / NOTE_RANGE
        y_center = int((1.0 - y_ratio) * (FRAME_HEIGHT - 24)) + 12
        h = 20

        is_active = start_sec <= current_time <= end_sec
        color = pitch_color(note, is_active)

        # アクティブ時: 薄いグロー
        if is_active:
            r, g, b, _ = color
            draw.rectangle([x1-2, y_center-h//2-2, x2+2, y_center+h//2+2],
                           fill=(r, g, b, 55))

        draw.rectangle([x1, y_center-h//2, x2, y_center+h//2], fill=color)

        # 火花: ヒット直後（SPARK_DURATION秒以内）
        time_since_hit = current_time - start_sec
        if 0 <= time_since_hit <= 0.18:
            spark_queue.append((cursor_x, y_center, color, time_since_hit, int(note * 1000 + start_sec * 100)))

    # カーソル線
    draw.line([(cursor_x, 0), (cursor_x, FRAME_HEIGHT)], fill=(255,255,255,40), width=5)
    draw.line([(cursor_x, 0), (cursor_x, FRAME_HEIGHT)], fill=(255,255,255,200), width=2)

    # 火花を最前面に描画
    for cx, cy, color, time_since_hit, seed in spark_queue:
        draw_sparks(draw, cx, cy, color, time_since_hit, seed)

    img.save(f"{OUTPUT_DIR}/frame_{frame_idx:05d}.png")
    if frame_idx % 100 == 0:
        print(f"  {frame_idx}/{total_frames}")

print(f"Generated {total_frames} frames")
