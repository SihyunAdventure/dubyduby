#!/usr/bin/env python3
"""Generate ASS subtitle (YouTube style: white text on rounded semi-transparent box).

Timing strategy:
  Subtitle cues anchor to actual KO audio playback positions (not source EN
  timestamps). Computed from per-utterance wav durations after silenceremove
  + atempo, so subtitles match what the viewer hears.

Reads:
  output/<video_id>/3_translation/utterances.json
  output/<video_id>/4_synth/utt-NNN.wav (durations)
  output/<video_id>/5_intermediate/dub_raw.wav and dub_clean.wav (silence removal)
  output/<video_id>/5_intermediate/atempo.txt

Writes:
  output/<video_id>/6_final/subtitles.ass
"""
import json
import sys
import wave
from pathlib import Path

import numpy as np
from PIL import ImageFont


MAX_CHARS_PER_LINE = 28
MAX_LINES = 2
MAX_BOX_WIDTH_RATIO = 0.85  # cap box width to 85% of video width (force wrap)
FONT_NAME = "Pretendard"
FONT_SIZE = 56
PLAY_RES_X = 1920
PLAY_RES_Y = 1080

PAD_X = 24
PAD_Y = 10
LINE_SPACING = 4
BOX_RADIUS = 8
MARGIN_V = 80

COLOR_TEXT = "&H00FFFFFF"
COLOR_BOX = "&H80000000"

FONT_PATH = Path(__file__).parent.parent / "fonts" / "Pretendard-Bold.ttf"
_FONT = ImageFont.truetype(str(FONT_PATH), FONT_SIZE)
_ASCENT, _DESCENT = _FONT.getmetrics()
LINE_HEIGHT = _ASCENT + _DESCENT


def ms_to_ass_time(ms: int) -> str:
    h = ms // 3600000
    m = (ms % 3600000) // 60000
    s = (ms % 60000) // 1000
    cs = (ms % 1000) // 10
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def _line_width_px(line: str) -> int:
    bbox = _FONT.getbbox(line)
    return bbox[2] - bbox[0]


def wrap_korean(text: str, max_per_line: int = MAX_CHARS_PER_LINE):
    """Wrap by space into <= MAX_LINES, then enforce pixel max width.
    If a line exceeds (PLAY_RES_X * MAX_BOX_WIDTH_RATIO - PAD_X*2), break on space.
    """
    max_px = PLAY_RES_X * MAX_BOX_WIDTH_RATIO - PAD_X * 2
    text = text.strip()
    words = text.split(" ")

    # Greedy pack by pixel width AND char count
    lines = []
    current = []
    for w in words:
        candidate = " ".join(current + [w]) if current else w
        if (
            len(candidate) > max_per_line and current
        ) or _line_width_px(candidate) > max_px:
            if current:
                lines.append(" ".join(current))
                current = [w]
            else:
                # Single very long word — hard split
                lines.append(w[:max_per_line])
                current = [w[max_per_line:]]
        else:
            current.append(w)
    if current:
        lines.append(" ".join(current))

    # Coalesce overflow into last line if > MAX_LINES
    if len(lines) > MAX_LINES:
        lines = lines[:MAX_LINES - 1] + [" ".join(lines[MAX_LINES - 1:])]
    return lines


def rounded_rect_drawing(w: float, h: float, r: float) -> str:
    c = r * 0.4477
    cmds = [
        f"m {r} 0",
        f"l {w - r} 0",
        f"b {w - c} 0 {w} {c} {w} {r}",
        f"l {w} {h - r}",
        f"b {w} {h - c} {w - c} {h} {w - r} {h}",
        f"l {r} {h}",
        f"b {c} {h} 0 {h - c} 0 {h - r}",
        f"l 0 {r}",
        f"b 0 {c} {c} 0 {r} 0",
    ]
    return " ".join(cmds)


def measure_lines(lines):
    if not lines:
        return PAD_X * 2, PAD_Y * 2
    widths = [(_FONT.getbbox(l)[2] - _FONT.getbbox(l)[0]) for l in lines]
    w = max(widths) + PAD_X * 2
    h = len(lines) * LINE_HEIGHT + (len(lines) - 1) * LINE_SPACING + PAD_Y * 2
    return w, h


def wav_duration_ms(path: Path) -> int:
    with wave.open(str(path), "rb") as wf:
        return int(wf.getnframes() / wf.getframerate() * 1000)


SILENCE_STOP_DURATION_MS = 200  # must match finalize.sh stop_duration=0.2
# Per-utt leading silence measured directly from wav (Supertonic wavs have
# variable padding 50–500ms). Threshold for "voice" in i16 PCM peak.
VOICE_AMPLITUDE_THRESHOLD = 0.01  # ~ -40dBFS in normalized [-1, 1]


def measure_leading_silence_ms(wav_path: Path) -> int:
    """Find ms from start where amplitude first exceeds threshold."""
    with wave.open(str(wav_path), "rb") as wf:
        n = wf.getnframes()
        sr = wf.getframerate()
        raw = wf.readframes(n)
    samples = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
    threshold = VOICE_AMPLITUDE_THRESHOLD
    above = np.where(np.abs(samples) > threshold)[0]
    if len(above) == 0:
        return 0
    return int(above[0] / sr * 1000)


def _parse_raw_silences(path: Path):
    """Return list of (start_ms, end_ms) silence segments from raw silencedetect."""
    import re
    if not path.exists():
        return []
    starts, ends = [], []
    for line in path.read_text().splitlines():
        m = re.search(r"silence_start:\s*([\d.]+)", line)
        if m:
            starts.append(int(float(m.group(1)) * 1000))
        m2 = re.search(r"silence_end:\s*([\d.]+)", line)
        if m2:
            ends.append(int(float(m2.group(1)) * 1000))
    # Pair them — silencedetect emits start/end in order
    pairs = []
    for s, e in zip(starts, ends):
        if e > s:
            pairs.append((s, e))
    return pairs


def _cumulative_cut(t_raw_ms: int, silences) -> int:
    """How many ms of silence got removed up to position t_raw_ms in raw audio.

    silenceremove behavior: each silence chunk longer than SILENCE_STOP_DURATION
    gets trimmed to SILENCE_STOP_DURATION (≈ 200ms kept).
    """
    cut = 0
    for s_start, s_end in silences:
        if s_end <= t_raw_ms:
            # Whole silence is before t — full cut
            dur = s_end - s_start
            if dur > SILENCE_STOP_DURATION_MS:
                cut += dur - SILENCE_STOP_DURATION_MS
        elif s_start < t_raw_ms < s_end:
            # t is inside this silence — partial. Keep first 200ms, cut rest.
            inside = t_raw_ms - s_start
            cut += max(0, inside - SILENCE_STOP_DURATION_MS)
            break
        else:
            # silence is entirely after t
            break
    return cut


def _parse_final_onsets(path: Path) -> list:
    """Return voice onset times (ms) from silencedetect on dub_final.wav."""
    import re
    if not path.exists():
        return []
    starts = []
    ends = []
    for line in path.read_text().splitlines():
        m = re.search(r"silence_start:\s*([\d.]+)", line)
        if m:
            starts.append(int(float(m.group(1)) * 1000))
        m2 = re.search(r"silence_end:\s*([\d.]+)", line)
        if m2:
            ends.append(int(float(m2.group(1)) * 1000))
    # Voice begins at silence_end (or at 0 if no leading silence)
    onsets = list(ends)
    if not starts or starts[0] > 100:
        onsets.insert(0, 0)
    return onsets


def _snap_to_onset(cue_ms: int, onsets: list, tolerance_ms: int = 500) -> int:
    if not onsets:
        return cue_ms
    nearest = min(onsets, key=lambda o: abs(o - cue_ms))
    return nearest if abs(nearest - cue_ms) <= tolerance_ms else cue_ms


def compute_audio_timing(utterances, base: Path, atempo: float = 1.0) -> list:
    """Use placement.json from place_timeline.py — per-utt placement at
    utterance.start_ms with per-utt atempo. Each cue anchors to source video
    speaker timeline; cue end = placed audio end.
    """
    placement = json.load(open(base / "5_intermediate" / "placement.json"))
    by_idx = {p["i"]: p for p in placement}
    out = []
    for i, u in enumerate(utterances):
        p = by_idx.get(i)
        if not p:
            continue
        out.append((u, p["start_ms"], p["end_ms"]))

    # Snap each cue start to nearest real voice onset detected on dub_final.wav.
    # Corrects accumulated algorithm drift (silenceremove non-linearity, atempo
    # rounding) by anchoring to ground truth.
    final_onsets = _parse_final_onsets(base / "5_intermediate" / "silence_log_final.txt")
    if final_onsets:
        out = [(u, _snap_to_onset(s, final_onsets), e) for u, s, e in out]

    # Sustain each cue exactly to the start of the next — no gap at all,
    # so subtitles flow continuously without flicker between utterances.
    for i in range(len(out) - 1):
        u, s, e = out[i]
        next_start = out[i + 1][1]
        out[i] = (u, s, max(e, next_start))
    return out


def build_ass(timed_utts) -> str:
    header = f"""[Script Info]
Title: dubyduby
ScriptType: v4.00+
PlayResX: {PLAY_RES_X}
PlayResY: {PLAY_RES_Y}
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Text,{FONT_NAME},{FONT_SIZE},{COLOR_TEXT},{COLOR_TEXT},&H00000000&,&H00000000&,1,0,0,0,100,100,0,0,1,0,0,5,0,0,0,1
Style: Box,{FONT_NAME},{FONT_SIZE},{COLOR_BOX},{COLOR_BOX},{COLOR_BOX},{COLOR_BOX},0,0,0,0,100,100,0,0,1,0,0,7,0,0,0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    out = [header]
    for u, start_ms, end_ms in timed_utts:
        if end_ms <= start_ms:
            end_ms = start_ms + 1000
        lines = wrap_korean(u["text"])
        box_w, box_h = measure_lines(lines)
        center_x = PLAY_RES_X / 2
        box_bottom_y = PLAY_RES_Y - MARGIN_V
        box_top_y = box_bottom_y - box_h
        box_x = center_x - box_w / 2
        text_center_y = box_top_y + box_h / 2
        drawing = rounded_rect_drawing(box_w, box_h, BOX_RADIUS)
        out.append(
            f"Dialogue: 0,{ms_to_ass_time(start_ms)},{ms_to_ass_time(end_ms)},Box,,0,0,0,,"
            f"{{\\pos({box_x:.0f},{box_top_y:.0f})\\an7\\bord0\\shad0\\p1}}{drawing}{{\\p0}}\n"
        )
        text = r"\N".join(lines)
        out.append(
            f"Dialogue: 1,{ms_to_ass_time(start_ms)},{ms_to_ass_time(end_ms)},Text,,0,0,0,,"
            f"{{\\pos({center_x:.0f},{text_center_y:.0f})\\an5}}{text}\n"
        )
    return "".join(out)


def main():
    if len(sys.argv) != 2:
        sys.exit("Usage: subtitle.py <video_id>")
    video_id = sys.argv[1]
    base = Path(f"output/{video_id}")
    utts = json.load(open(base / "3_translation" / "utterances.json"))
    timed = compute_audio_timing(utts, base)
    out = base / "6_final" / "subtitles.ass"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(build_ass(timed))
    print(f"[subtitle] {len(timed)} cues → {out}")


if __name__ == "__main__":
    main()
