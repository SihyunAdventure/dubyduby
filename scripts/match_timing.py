#!/usr/bin/env python3
"""Match agent-written sentences.json to token timing → utterances.json + sentences.md.

Usage: match_timing.py <video_id>
"""
import json
import sys
from pathlib import Path


def main():
    if len(sys.argv) != 2:
        sys.exit("Usage: match_timing.py <video_id>")
    video_id = sys.argv[1]

    base = Path(f"output/{video_id}")
    tokens = json.load(open(base / "2_transcript" / "tokens.json"))["tokens"]
    sentences = json.load(open(base / "3_translation" / "sentences.json"))

    full = ""
    c2t = []
    for ti, t in enumerate(tokens):
        for _ in t["text"]:
            c2t.append(ti)
        full += t["text"]

    utts = []
    search = 0
    no_match = []
    for si, s in enumerate(sentences):
        en = s["en"]
        idx = full.find(en, search)
        if idx == -1:
            # Cursor may have passed it (out-of-order match earlier). Try full search.
            idx = full.find(en)
            if idx == -1:
                no_match.append((si, en[:60]))
                continue
        end = idx + len(en) - 1
        ft = tokens[c2t[idx]]
        lt = tokens[c2t[end]]
        utts.append({
            "start_ms": ft["start_ms"],
            "end_ms": lt["end_ms"],
            "text": s["ko"],                       # subtitle display (e.g. "3.0")
            "tts_text": s.get("ko_tts", s["ko"]),  # synthesis input (e.g. "삼 점 영")
            "language": "ko",
            "speaker": ft.get("speaker"),  # from Soniox diarization (None if disabled)
        })
        search = end + 1

    out = base / "3_translation" / "utterances.json"
    json.dump(utts, open(out, "w"), ensure_ascii=False, indent=2)

    # Human-readable sentences.md
    lines = ["# Sentences (EN ↔ KO)", "",
             f"Matched: {len(utts)}/{len(sentences)}", ""]
    if no_match:
        lines.append("## ⚠️ No-match")
        for si, en in no_match:
            lines.append(f"- [{si}] `{en}`")
        lines.append("")
    lines += ["## Table", "", "| # | EN | KO |", "|---|----|----|"]
    for i, s in enumerate(sentences):
        en = s["en"].replace("|", "\\|")
        ko = s["ko"].replace("|", "\\|")
        lines.append(f"| {i} | {en} | {ko} |")
    (base / "3_translation" / "sentences.md").write_text("\n".join(lines))

    print(f"Matched: {len(utts)}/{len(sentences)} → {out}")
    if no_match:
        print(f"NO MATCH: {len(no_match)} sentences")
        for si, en in no_match:
            print(f"  [{si}] {en!r}")
        sys.exit(1)


if __name__ == "__main__":
    main()
