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
WINDOW_SECONDS = 3.0
NOTE_OPACITY = 200
TIME_OFFSET = 0.0

NOTE_MIN = 36  # C2
NOTE_MAX = 84  # C6

os.makedirs(OUTPUT_DIR, exist_ok=True)

mid = mido.MidiFile(MIDI_FILE)
ticks_per_beat = mid.ticks_per_beat

# テンポマップ構築
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

def note_color(note, is_active, opacity):
    """ピッチに応じた虹色。アクティブ時は明るく・彩度高め"""
    ratio = (note - NOTE_MIN) / NOTE_RANGE  # 0.0(低音) → 1.0(高音)
    # 虹色: 低音=赤, 中音=緑/シアン, 高音=紫
    hue = ratio * 270  # 0=赤, 120=緑, 240=青, 270=紫
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
        # 白に近づける（明るく）
        r = min(255, r + 80)
        g = min(255, g + 80)
        b = min(255, b + 80)
        opacity = min(255, opacity + 55)

    return (r, g, b, opacity)

def draw_glow(draw, x1, y2, x2, y1, color, layers=3):
    """ノートの周囲にグロー（発光）エフェクトを描画"""
    r, g, b, a = color
    for i in range(layers, 0, -1):
        pad = i * 3
        glow_alpha = max(0, a // (layers + 1) * i // layers)
        draw.rectangle(
            [x1 - pad, y2 - pad, x2 + pad, y1 + pad],
            fill=(r, g, b, glow_alpha)
        )

def draw_sparkles(draw, cx, cy, color, seed, count=5):
    """カーソル付近にキラキラ（スパークル）を描画"""
    r, g, b, _ = color
    rng = random.Random(seed)
    for _ in range(count):
        sx = cx + rng.randint(-12, 12)
        sy = cy + rng.randint(-20, 20)
        size = rng.randint(1, 3)
        alpha = rng.randint(120, 220)
        draw.ellipse([sx-size, sy-size, sx+size, sy+size], fill=(r, g, b, alpha))
        # 十字スパークル
        draw.line([(sx-size*2, sy), (sx+size*2, sy)], fill=(255,255,255,alpha//2), width=1)
        draw.line([(sx, sy-size*2), (sx, sy+size*2)], fill=(255,255,255,alpha//2), width=1)

total_frames = int(VIDEO_DURATION * FPS)

for frame_idx in range(total_frames):
    current_time = frame_idx / FPS
    window_start = current_time - WINDOW_SECONDS * 0.3
    window_end   = current_time + WINDOW_SECONDS * 0.7

    img = Image.new("RGBA", (FRAME_WIDTH, FRAME_HEIGHT), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # 背景: 60%透過の黒（alpha = 255 * 0.4 = 102）
    bg = Image.new("RGBA", (FRAME_WIDTH, FRAME_HEIGHT), (0, 0, 0, 102))
    img = Image.alpha_composite(img, bg)
    draw = ImageDraw.Draw(img)

    cursor_x = int(FRAME_WIDTH * 0.3)

    # アクティブなノートを収集（スパークル用）
    active_notes_at_cursor = []
    for start_sec, end_sec, note in notes:
        if start_sec <= current_time <= end_sec and NOTE_MIN <= note <= NOTE_MAX:
            active_notes_at_cursor.append(note)

    # グロー → 通常ノートの順で描画
    for pass_num in range(2):  # 0=グロー, 1=本体
        for start_sec, end_sec, note in notes:
            if end_sec < window_start or start_sec > window_end:
                continue
            if note < NOTE_MIN or note > NOTE_MAX:
                continue

            x1 = int((start_sec - window_start) / (window_end - window_start) * FRAME_WIDTH)
            x2 = int((end_sec   - window_start) / (window_end - window_start) * FRAME_WIDTH)
            x2 = max(x2, x1 + 4)

            y_ratio = (note - NOTE_MIN) / NOTE_RANGE
            y1 = int((1.0 - y_ratio) * (FRAME_HEIGHT - 24)) + 12
            y2 = y1 - 14

            is_active = start_sec <= current_time <= end_sec
            color = note_color(note, is_active, NOTE_OPACITY)

            if pass_num == 0 and is_active:
                draw_glow(draw, x1, y2, x2, y1, color, layers=3)
            elif pass_num == 1:
                # アクティブ時は少し大きく
                if is_active:
                    draw.rectangle([x1-1, y2-2, x2+1, y1+2], fill=color)
                else:
                    draw.rectangle([x1, y2, x2, y1], fill=color)

    # カーソル線（グロー付き）
    for w, a in [(6, 30), (3, 70), (2, 180)]:
        draw.line([(cursor_x, 0), (cursor_x, FRAME_HEIGHT)], fill=(255, 255, 255, a), width=w)

    # スパークル（アクティブノートがある場合）
    for note in active_notes_at_cursor:
        y_ratio = (note - NOTE_MIN) / NOTE_RANGE
        note_y = int((1.0 - y_ratio) * (FRAME_HEIGHT - 24)) + 12 - 7
        color = note_color(note, True, 255)
        seed = frame_idx * 100 + note
        draw_sparkles(draw, cursor_x, note_y, color, seed, count=4)

    img.save(f"{OUTPUT_DIR}/frame_{frame_idx:05d}.png")

    if frame_idx % 100 == 0:
        print(f"  {frame_idx}/{total_frames}")

print(f"Generated {total_frames} frames")
