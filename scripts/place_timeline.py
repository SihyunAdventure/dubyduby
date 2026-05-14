#!/usr/bin/env python3
"""Place per-utterance wavs at source video timeline positions.

Each utt anchors to utterance.start_ms (original English speaker mouth-cue).
If KO synth duration exceeds the slot before next utt, apply per-utt atempo
to fit (clamped [1.0, 1.6]). Silence in source video → silence in dub.

Reads:
  output/<video_id>/3_translation/utterances.json
  output/<video_id>/4_synth/utt-NNN.wav

Writes:
  output/<video_id>/6_final/dubbed_audio.wav (placed timeline)
  output/<video_id>/5_intermediate/placement.json (per-utt final timing)
"""
import json
import subprocess
import sys
import wave
from pathlib import Path

import numpy as np


ATEMPO_MIN = 1.0
ATEMPO_MAX = 1.6  # hard limit — beyond this Korean sounds rushed


def read_wav_i16(path: Path):
    with wave.open(str(path), "rb") as wf:
        sr = wf.getframerate()
        raw = wf.readframes(wf.getnframes())
    return np.frombuffer(raw, dtype=np.int16), sr


def write_wav_i16(path: Path, samples: np.ndarray, sr: int):
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(samples.astype(np.int16).tobytes())


def atempo_wav(in_path: Path, out_path: Path, factor: float):
    """Apply ffmpeg atempo filter."""
    subprocess.run([
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-i", str(in_path),
        "-af", f"atempo={factor:.4f}",
        str(out_path),
    ], check=True)


def main():
    if len(sys.argv) != 3:
        sys.exit("Usage: place_timeline.py <video_id> <video_duration_ms>")
    video_id = sys.argv[1]
    video_duration_ms = int(sys.argv[2])
    base = Path(f"output/{video_id}")
    utts = json.load(open(base / "3_translation" / "utterances.json"))
    synth_dir = base / "4_synth"
    inter_dir = base / "5_intermediate"
    final_dir = base / "6_final"
    inter_dir.mkdir(parents=True, exist_ok=True)
    final_dir.mkdir(parents=True, exist_ok=True)

    # Load all utt wavs first to get sample rate
    first_wav = synth_dir / "utt-000.wav"
    _, sr = read_wav_i16(first_wav)
    total_samples = int(video_duration_ms * sr / 1000)
    buf = np.zeros(total_samples, dtype=np.int32)  # accumulator (int32 for safe mixing)

    placements = []
    n = len(utts)
    for i, u in enumerate(utts):
        wav_path = synth_dir / f"utt-{i:03d}.wav"
        if not wav_path.exists():
            continue
        samples, _ = read_wav_i16(wav_path)
        wav_dur_ms = int(len(samples) / sr * 1000)
        start_ms = u["start_ms"]
        if i + 1 < n:
            next_start_ms = utts[i + 1]["start_ms"]
        else:
            next_start_ms = video_duration_ms
        slot_ms = next_start_ms - start_ms

        atempo = 1.0
        if wav_dur_ms > slot_ms and slot_ms > 0:
            atempo = min(wav_dur_ms / slot_ms, ATEMPO_MAX)
        if atempo > 1.0:
            scaled_path = inter_dir / f"utt-{i:03d}_scaled.wav"
            atempo_wav(wav_path, scaled_path, atempo)
            samples, _ = read_wav_i16(scaled_path)
            scaled_path.unlink()

        start_sample = int(start_ms * sr / 1000)
        end_sample = min(start_sample + len(samples), total_samples)
        copy_len = end_sample - start_sample
        buf[start_sample:end_sample] += samples[:copy_len].astype(np.int32)

        placements.append({
            "i": i,
            "start_ms": start_ms,
            "end_ms": start_ms + int(copy_len / sr * 1000),
            "atempo": round(atempo, 4),
            "slot_ms": slot_ms,
            "raw_dur_ms": wav_dur_ms,
        })

    # Clip int32 back to int16 range (no clipping expected since utts don't overlap)
    buf = np.clip(buf, -32768, 32767)
    write_wav_i16(final_dir / "dubbed_audio.wav", buf, sr)

    json.dump(placements, open(inter_dir / "placement.json", "w"), indent=2)
    n_scaled = sum(1 for p in placements if p["atempo"] > 1.0)
    print(f"[place] {len(placements)} utts placed at source timeline")
    print(f"[place] {n_scaled} scaled (atempo > 1.0), {len(placements) - n_scaled} natural")


if __name__ == "__main__":
    main()
