"""
librosaでピッチ検出 → MIDIファイル生成（精度向上版）
"""
import librosa
import numpy as np
import mido
from mido import MidiFile, MidiTrack, Message, MetaMessage

AUDIO_FILE = "/home/user/cl1/piano_audio.wav"
OUTPUT_MIDI = "/home/user/cl1/song.mid"
BPM = 120
HOP_LENGTH = 256       # 512→256 で時間解像度2倍
MIN_NOTE_SEC = 0.08    # 80ms未満のノートを除去（ノイズ対策）
MERGE_GAP_SEC = 0.04   # 同音で40ms以内のギャップはつなげる

y, sr = librosa.load(AUDIO_FILE, sr=22050, mono=True)
print(f"Audio loaded: {len(y)/sr:.2f}s, sr={sr}")

# pyin: 単音ピッチ検出（精度が高い）
f0, voiced_flag, voiced_probs = librosa.pyin(
    y,
    fmin=librosa.note_to_hz('C2'),
    fmax=librosa.note_to_hz('C7'),
    sr=sr,
    hop_length=HOP_LENGTH,
    fill_na=None,
)

times = librosa.times_like(f0, sr=sr, hop_length=HOP_LENGTH)

def hz_to_midi(hz):
    if hz is None or np.isnan(hz) or hz <= 0:
        return None
    return int(round(69 + 12 * np.log2(hz / 440.0)))

# フレームごとのMIDIノートに変換
frame_notes = []
for t, hz, voiced in zip(times, f0, voiced_flag):
    frame_notes.append(hz_to_midi(hz) if voiced else None)

# 連続する同ノートを1つのイベントにまとめる
raw_notes = []  # (start_sec, end_sec, midi_note)
current_note = None
current_start = None

for i, (t, note) in enumerate(zip(times, frame_notes)):
    if note != current_note:
        if current_note is not None and current_start is not None:
            raw_notes.append((current_start, t, current_note))
        current_note = note
        current_start = t if note is not None else None

if current_note is not None and current_start is not None:
    raw_notes.append((current_start, times[-1], current_note))

# 同ピッチで近接するノートをマージ
def merge_notes(notes, gap_sec):
    if not notes:
        return []
    merged = [list(notes[0])]
    for start, end, note in notes[1:]:
        prev = merged[-1]
        if note == prev[2] and (start - prev[1]) < gap_sec:
            prev[1] = end  # ギャップをつなげる
        else:
            merged.append([start, end, note])
    return [tuple(n) for n in merged]

notes = merge_notes(raw_notes, MERGE_GAP_SEC)

# 短すぎるノートを除去
notes = [(s, e, n) for s, e, n in notes if (e - s) >= MIN_NOTE_SEC]

print(f"Detected {len(notes)} notes (raw: {len(raw_notes)})")
for s, e, n in notes[:15]:
    print(f"  {s:.3f}s - {e:.3f}s ({e-s:.3f}s): {n} ({librosa.midi_to_note(n)})")

# MIDI生成
mid = MidiFile(type=0, ticks_per_beat=480)
track = MidiTrack()
mid.tracks.append(track)

tempo = mido.bpm2tempo(BPM)
track.append(MetaMessage('set_tempo', tempo=tempo, time=0))

def sec_to_tick(sec):
    return int(sec * (480 * BPM / 60))

events = []
for start, end, note in notes:
    events.append((sec_to_tick(start), 'note_on',  note, 80))
    events.append((sec_to_tick(end),   'note_off', note, 0))

events.sort(key=lambda x: x[0])

prev_tick = 0
for tick, msg_type, note, vel in events:
    delta = max(0, tick - prev_tick)
    track.append(Message(msg_type, note=note, velocity=vel, time=delta))
    prev_tick = tick

mid.save(OUTPUT_MIDI)
print(f"Saved: {OUTPUT_MIDI}")
