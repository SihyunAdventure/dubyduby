#!/usr/bin/env python3
"""Analyze speaker pitch (gender) and assign Supertonic voices.

Reads:
  output/<video_id>/1_source/audio.mp3
  output/<video_id>/2_transcript/tokens.json (Soniox with diarization)

Writes:
  output/<video_id>/2_transcript/speakers.json
    {"<speaker_id>": {"gender": "M"|"F", "voice": "M1"|..., "f0_median_hz": float}}

Voice assignment:
  - First M speaker → M1, second M → M2, ...
  - First F speaker → F1, second F → F2, ...
"""
import json
import sys
from pathlib import Path

import librosa
import numpy as np


F0_GENDER_BOUNDARY_HZ = 165.0  # below = M, above = F (rough industry standard)
SAMPLE_LIMIT_SEC = 30  # max audio per speaker for pitch analysis


def main():
    if len(sys.argv) != 2:
        sys.exit("Usage: analyze_speakers.py <video_id>")
    video_id = sys.argv[1]

    base = Path(f"output/{video_id}")
    audio_path = base / "1_source" / "audio.mp3"
    tokens = json.load(open(base / "2_transcript" / "tokens.json"))["tokens"]

    # Collect speaker → list of (start_ms, end_ms)
    ranges = {}
    for t in tokens:
        spk = t.get("speaker")
        if not spk:
            continue
        ranges.setdefault(spk, []).append((t["start_ms"], t["end_ms"]))

    if not ranges:
        print("[speakers] no speaker info — diarization not enabled or single speaker")
        out = {}
    else:
        y, sr = librosa.load(str(audio_path), sr=16000)
        out = {}
        for spk in sorted(ranges.keys()):
            segments = []
            total = 0.0
            for s_ms, e_ms in ranges[spk]:
                dur = (e_ms - s_ms) / 1000
                if total + dur > SAMPLE_LIMIT_SEC:
                    break
                s = int(s_ms / 1000 * sr)
                e = min(int(e_ms / 1000 * sr), len(y))
                segments.append(y[s:e])
                total += dur
            audio = np.concatenate(segments) if segments else np.array([])
            if len(audio) < sr:
                continue
            f0, _, _ = librosa.pyin(audio, fmin=50, fmax=400, sr=sr)
            voiced = f0[~np.isnan(f0)]
            if len(voiced) == 0:
                continue
            median_f0 = float(np.median(voiced))
            gender = "F" if median_f0 > F0_GENDER_BOUNDARY_HZ else "M"
            out[spk] = {
                "gender": gender,
                "f0_median_hz": round(median_f0, 1),
                "voice": None,  # filled below
            }

    # Assign voices: per-gender increment (M1, M2, ... and F1, F2, ...)
    m_idx = 0
    f_idx = 0
    for spk in sorted(out.keys()):
        if out[spk]["gender"] == "M":
            m_idx += 1
            out[spk]["voice"] = f"M{min(m_idx, 5)}"
        else:
            f_idx += 1
            out[spk]["voice"] = f"F{min(f_idx, 5)}"

    speakers_path = base / "2_transcript" / "speakers.json"
    json.dump(out, open(speakers_path, "w"), ensure_ascii=False, indent=2)

    # Human-readable
    md = base / "2_transcript" / "speakers.md"
    lines = ["# Speakers", "", f"Total: {len(out)}", ""]
    lines.append("| ID | Gender | f0 median (Hz) | Voice |")
    lines.append("|----|--------|----------------|-------|")
    for spk in sorted(out.keys()):
        s = out[spk]
        lines.append(f"| {spk} | {s['gender']} | {s['f0_median_hz']} | {s['voice']} |")
    md.write_text("\n".join(lines) + "\n")

    print(f"[speakers] {len(out)} speakers → {speakers_path}")
    for spk, info in sorted(out.items()):
        print(f"  {spk}: {info['gender']} ({info['f0_median_hz']:.1f}Hz) → {info['voice']}")


if __name__ == "__main__":
    main()
