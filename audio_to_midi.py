"""
librosaでピッチ検出 → MIDIファイル生成
"""
import librosa
import numpy as np
import mido
from mido import MidiFile, MidiTrack, Message, MetaMessage
import os

AUDIO_FILE = "/home/user/cl1/piano_audio.wav"
OUTPUT_MIDI = "/home/user/cl1/song.mid"
BPM = 120
HOP_LENGTH = 512  # フレームのホップ長

y, sr = librosa.load(AUDIO_FILE, sr=22050, mono=True)
print(f"Audio loaded: {len(y)/sr:.2f}s, sr={sr}")

# ピッチ検出（pyin: ピアノ等の単音に強い）
f0, voiced_flag, voiced_probs = librosa.pyin(
    y,
    fmin=librosa.note_to_hz('C2'),
    fmax=librosa.note_to_hz('C7'),
    sr=sr,
    hop_length=HOP_LENGTH,
)

times = librosa.times_like(f0, sr=sr, hop_length=HOP_LENGTH)

# 周波数 → MIDIノート番号
def hz_to_midi(hz):
    if hz is None or np.isnan(hz) or hz <= 0:
        return None
    return int(round(69 + 12 * np.log2(hz / 440.0)))

# ノートイベントをまとめる（連続する同じノートを1つのノートに）
notes = []  # (start_sec, end_sec, midi_note)
current_note = None
current_start = None

for i, (t, hz, voiced) in enumerate(zip(times, f0, voiced_flag)):
    note = hz_to_midi(hz) if voiced else None
    if note != current_note:
        if current_note is not None and current_start is not None:
            duration = t - current_start
            if duration > 0.05:  # 50ms未満のノートは除外
                notes.append((current_start, t, current_note))
        current_note = note
        current_start = t if note is not None else None

# 最後のノートを閉じる
if current_note is not None and current_start is not None:
    notes.append((current_start, times[-1], current_note))

print(f"Detected {len(notes)} notes")
for s, e, n in notes[:10]:
    print(f"  {s:.3f}s - {e:.3f}s : {n} ({librosa.midi_to_note(n)})")

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
    delta = tick - prev_tick
    if delta < 0:
        delta = 0
    track.append(Message(msg_type, note=note, velocity=vel, time=delta))
    prev_tick = tick

mid.save(OUTPUT_MIDI)
print(f"Saved: {OUTPUT_MIDI}")
