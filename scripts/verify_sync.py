#!/usr/bin/env python3
"""Verify subtitle timing matches actual KO audio voice onsets.

Runs silencedetect on dubbed_audio.wav and compares each detected voice
onset to the nearest subtitle cue start. Reports delta in ms.

Usage: verify_sync.py <video_id>
"""
import re
import subprocess
import sys
from pathlib import Path


def detect_voice_onsets(wav_path: Path, threshold_db: int = -40, min_dur: float = 0.1):
    """Return list of voice onset times (ms) from ffmpeg silencedetect."""
    cmd = [
        "ffmpeg", "-hide_banner", "-i", str(wav_path),
        "-af", f"silencedetect=noise={threshold_db}dB:duration={min_dur}",
        "-f", "null", "-",
    ]
    p = subprocess.run(cmd, capture_output=True, text=True)
    log = p.stderr  # silencedetect logs to stderr
    onsets_ms = []
    has_leading_silence = False
    for line in log.splitlines():
        m = re.search(r"silence_end:\s*([\d.]+)", line)
        if m:
            onsets_ms.append(int(float(m.group(1)) * 1000))
        m2 = re.search(r"silence_start:\s*([\d.]+)", line)
        if m2 and float(m2.group(1)) == 0.0:
            has_leading_silence = True
    if not has_leading_silence or not onsets_ms or onsets_ms[0] > 100:
        onsets_ms.insert(0, 0)
    return onsets_ms


def parse_ass_cues(ass_path: Path):
    """Return list of (start_ms, end_ms) for each Dialogue line with Style=Text."""
    cues = []
    for line in ass_path.read_text().splitlines():
        if not line.startswith("Dialogue:"):
            continue
        parts = line.split(",", 9)
        if len(parts) < 10 or parts[3].strip() != "Text":
            continue
        def t2ms(t):
            h, m, rest = t.split(":")
            s, cs = rest.split(".")
            return (int(h) * 3600 + int(m) * 60 + int(s)) * 1000 + int(cs) * 10
        cues.append((t2ms(parts[1].strip()), t2ms(parts[2].strip())))
    return cues


def main():
    if len(sys.argv) != 2:
        sys.exit("Usage: verify_sync.py <video_id>")
    video_id = sys.argv[1]
    base = Path(f"output/{video_id}")
    audio = base / "6_final" / "dubbed_audio.wav"
    ass = base / "6_final" / "subtitles.ass"

    onsets = detect_voice_onsets(audio)
    cues = parse_ass_cues(ass)

    print(f"Voice onsets detected: {len(onsets)}")
    print(f"Subtitle cues:         {len(cues)}")
    print()

    if len(onsets) == 0 or len(cues) == 0:
        sys.exit("No data — empty audio or subtitles")

    # Match: each cue.start → nearest onset within ±SEARCH_RADIUS_MS.
    # Searching globally for "nearest" is wrong: a cue in a dense-speech region has no
    # nearby onset (no silence to detect), and global-nearest picks an onset seconds
    # away from a completely different sentence — that's a measurement artifact, not
    # a sync error. Radius-bounded search separates "actually misaligned" from
    # "not measurable here."
    SEARCH_RADIUS_MS = 500

    deltas = []
    no_nearby = 0
    for i, (cue_start, _) in enumerate(cues):
        candidates = [o for o in onsets if abs(o - cue_start) <= SEARCH_RADIUS_MS]
        if not candidates:
            no_nearby += 1
            if i < 15 or i >= len(cues) - 5:
                print(f"  cue[{i:>3}] start={cue_start:>6}ms  onset=    N/A  Δ=  N/A  (no onset within ±{SEARCH_RADIUS_MS}ms — dense speech)")
            elif i == 15:
                print("  ...")
            continue
        nearest = min(candidates, key=lambda o: abs(o - cue_start))
        delta = cue_start - nearest
        deltas.append(delta)
        if i < 15 or i >= len(cues) - 5:
            sign = "+" if delta >= 0 else ""
            print(f"  cue[{i:>3}] start={cue_start:>6}ms  onset={nearest:>6}ms  Δ={sign}{delta:>5}ms")
        elif i == 15:
            print("  ...")

    print()
    import statistics
    if not deltas:
        print("No measurable cues (every cue is in dense speech).")
        return
    abs_deltas = [abs(d) for d in deltas]
    print(f"Measurable cues:   {len(deltas)}/{len(cues)} (N/A: {no_nearby} in dense speech)")
    print(f"Mean abs delta:    {statistics.mean(abs_deltas):>6.0f}ms")
    print(f"Median abs delta:  {statistics.median(abs_deltas):>6.0f}ms")
    print(f"Max abs delta:     {max(abs_deltas):>6}ms")
    print(f"Within ±100ms:     {sum(1 for d in abs_deltas if d <= 100)}/{len(deltas)} of measurable")
    print(f"Within ±300ms:     {sum(1 for d in abs_deltas if d <= 300)}/{len(deltas)} of measurable")


if __name__ == "__main__":
    main()
