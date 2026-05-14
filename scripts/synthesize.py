#!/usr/bin/env python3
"""Synthesize each utterance with Supertonic.

Reads:
  output/<video_id>/3_translation/utterances.json
  output/<video_id>/2_transcript/speakers.json (optional, for multi-voice)

Writes:
  output/<video_id>/4_synth/utt-NNN.wav

Voice selection per utterance:
  1. If speakers.json exists and utterance has `speaker`: use speakers[speaker]["voice"]
  2. Else: DUBYDUBY_VOICE env (default "M1")
"""
import json
import os
import subprocess
import sys
import wave
from pathlib import Path

import numpy as np
from supertonic import TTS


def trim_wav_padding(path: Path, leading_keep_ms: int = 0, trailing_keep_ms: int = 120, threshold: float = 0.01):
    """Trim silence at both ends of wav, keeping configurable padding.

    leading_keep_ms=0 means leading silence is fully removed (subtitle anchors
    to voice onset). trailing_keep_ms=120 leaves natural breath at sentence end.
    """
    with wave.open(str(path), "rb") as wf:
        sr = wf.getframerate()
        n_channels = wf.getnchannels()
        sampwidth = wf.getsampwidth()
        raw = wf.readframes(wf.getnframes())
    samples = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0

    above = np.where(np.abs(samples) > threshold)[0]
    if len(above) == 0:
        return  # All silence — keep as-is

    leading_keep = int(leading_keep_ms / 1000 * sr)
    trailing_keep = int(trailing_keep_ms / 1000 * sr)

    start = max(0, above[0] - leading_keep)
    end = min(len(samples), above[-1] + 1 + trailing_keep)

    trimmed = samples[start:end]
    out = (trimmed * 32768).astype(np.int16).tobytes()
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(n_channels)
        wf.setsampwidth(sampwidth)
        wf.setframerate(sr)
        wf.writeframes(out)


def main():
    if len(sys.argv) != 2:
        sys.exit("Usage: synthesize.py <video_id>")
    video_id = sys.argv[1]
    fallback_voice = os.environ.get("DUBYDUBY_VOICE", "M1")

    base = Path(f"output/{video_id}")
    utts = json.load(open(base / "3_translation" / "utterances.json"))

    speakers_path = base / "2_transcript" / "speakers.json"
    speakers = {}
    if speakers_path.exists():
        speakers = json.load(open(speakers_path))

    out_dir = base / "4_synth"
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"[synth] {len(utts)} utterances, {len(speakers)} speakers")
    if speakers:
        for spk, info in sorted(speakers.items()):
            print(f"  speaker {spk}: {info['gender']} → {info['voice']}")
    else:
        print(f"  no speakers.json, using voice={fallback_voice} for all")

    tts = TTS(auto_download=True)
    style_cache = {}

    def get_style(voice):
        if voice not in style_cache:
            style_cache[voice] = tts.get_voice_style(voice_name=voice)
        return style_cache[voice]

    skipped = 0
    for i, u in enumerate(utts):
        tts_text = u.get("tts_text") or u["text"]
        if not tts_text.strip():
            skipped += 1
            continue
        spk = u.get("speaker")
        voice = speakers.get(spk, {}).get("voice") if spk else None
        voice = voice or fallback_voice
        style = get_style(voice)
        wav, dur = tts.synthesize(tts_text, voice_style=style, lang="ko")
        out = out_dir / f"utt-{i:03d}.wav"
        tts.save_audio(wav, str(out))
        # Trim leading silence fully + keep 120ms trailing for natural breath.
        # This anchors each utt's voice to wav start (subtitle = cumulative_raw
        # / atempo accurate) and keeps natural inter-utterance pause.
        trim_wav_padding(out, leading_keep_ms=0, trailing_keep_ms=120)
        if i % 20 == 0 or i == len(utts) - 1:
            spk_tag = f" spk={spk}" if spk else ""
            print(f"  [{i + 1:>3}/{len(utts)}] voice={voice}{spk_tag} dur={dur[0]:.2f}s → {out.name}")

    print(f"[synth] done: {len(utts) - skipped} wavs in {out_dir}/")


if __name__ == "__main__":
    main()
