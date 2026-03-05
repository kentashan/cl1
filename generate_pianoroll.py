import mido
from PIL import Image, ImageDraw
import os

# --- 設定 ---
MIDI_FILE = "/home/user/cl1/song.mid"
OUTPUT_DIR = "/home/user/cl1/pianoroll_frames"
FPS = 30
VIDEO_DURATION = 16.05
FRAME_WIDTH = 1920
FRAME_HEIGHT = 200
WINDOW_SECONDS = 3.0
NOTE_OPACITY = 153
TIME_OFFSET = 0.0  # ずれがあれば調整

NOTE_MIN = 36  # C2
NOTE_MAX = 84  # C6

os.makedirs(OUTPUT_DIR, exist_ok=True)

mid = mido.MidiFile(MIDI_FILE)
ticks_per_beat = mid.ticks_per_beat

# テンポマップを全トラックから構築
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

total_frames = int(VIDEO_DURATION * FPS)
NOTE_RANGE = NOTE_MAX - NOTE_MIN

for frame_idx in range(total_frames):
    current_time = frame_idx / FPS
    window_start = current_time - WINDOW_SECONDS * 0.3
    window_end   = current_time + WINDOW_SECONDS * 0.7

    img = Image.new("RGBA", (FRAME_WIDTH, FRAME_HEIGHT), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    cursor_x = int(FRAME_WIDTH * 0.3)
    draw.line([(cursor_x, 0), (cursor_x, FRAME_HEIGHT)], fill=(255, 255, 255, 180), width=2)

    for start_sec, end_sec, note in notes:
        if end_sec < window_start or start_sec > window_end:
            continue
        if note < NOTE_MIN or note > NOTE_MAX:
            continue

        x1 = int((start_sec - window_start) / (window_end - window_start) * FRAME_WIDTH)
        x2 = int((end_sec   - window_start) / (window_end - window_start) * FRAME_WIDTH)
        x2 = max(x2, x1 + 4)

        y_ratio = (note - NOTE_MIN) / NOTE_RANGE
        y1 = int((1.0 - y_ratio) * (FRAME_HEIGHT - 20)) + 10
        y2 = y1 - 14

        is_active = start_sec <= current_time <= end_sec
        color = (100, 200, 255, NOTE_OPACITY) if not is_active else (255, 255, 100, 230)
        draw.rectangle([x1, y2, x2, y1], fill=color)

    img.save(f"{OUTPUT_DIR}/frame_{frame_idx:05d}.png")

    if frame_idx % 100 == 0:
        print(f"  {frame_idx}/{total_frames}")

print(f"Generated {total_frames} frames")
