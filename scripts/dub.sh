#!/usr/bin/env bash
# Orchestrator. Two phases:
#   Phase 1 (pre-translation): download + transcribe → exits, waits for agent to write sentences.json
#   Phase 2 (post-translation): match_timing + synthesize + finalize → dubbed_video.mp4
#
# Agent (Claude, Codex, etc.) is expected to read 2_transcript/transcript.md and write
# 3_translation/sentences.json (EN+KO array). See AGENTS.md for translation guidelines.
#
# Usage: dub.sh <youtube_url> [duration_seconds]
set -e
URL="${1:?Usage: $0 <youtube_url> [duration_seconds]}"
DURATION="${2:-}"

cd "$(dirname "$0")/.."

[ -d .venv ] || { echo "Run bash scripts/setup.sh first"; exit 1; }

# Phase 1 — yt-dlp gets video_id; skip download/transcribe if already done
VIDEO_ID=$("$(dirname "$0")/../binaries/yt-dlp" --get-id --no-warnings "$URL")
echo "[dub] video_id=$VIDEO_ID"
BASE="output/$VIDEO_ID"

if [ ! -f "$BASE/1_source/video.mp4" ] || [ ! -f "$BASE/1_source/audio.mp3" ]; then
  bash scripts/download.sh "$URL" "$DURATION"
else
  echo "[dub] source exists, skip download"
fi

if [ ! -f "$BASE/2_transcript/tokens.json" ]; then
  bash scripts/transcribe.sh "$VIDEO_ID"
else
  echo "[dub] transcript exists, skip transcribe"
fi

# Speaker analysis (pitch → gender → voice) — runs once per video
if [ ! -f "$BASE/2_transcript/speakers.json" ]; then
  # shellcheck disable=SC1091
  source .venv/bin/activate
  python3 scripts/analyze_speakers.py "$VIDEO_ID"
else
  echo "[dub] speakers exists, skip analyze"
fi

SENT="output/$VIDEO_ID/3_translation/sentences.json"
mkdir -p "output/$VIDEO_ID/3_translation"

if [ ! -f "$SENT" ]; then
  cat <<EOF

==> Agent needs to write $SENT now.

    Source:  output/$VIDEO_ID/2_transcript/transcript.md
    Output:  $SENT
    Schema:  [{"en": "<EN sentence>", "ko": "<KO translation>"}, ...]
    Guidelines: AGENTS.md → "Translation guidelines"

    Then re-run:  bash scripts/dub.sh "$URL"

EOF
  exit 0
fi

# Phase 2 — sentences.json exists, finalize
# shellcheck disable=SC1091
source .venv/bin/activate
python3 scripts/match_timing.py "$VIDEO_ID"
python3 scripts/synthesize.py "$VIDEO_ID"
bash scripts/finalize.sh "$VIDEO_ID"

OUT="output/$VIDEO_ID/6_final/dubbed_video.mp4"
echo ""
echo "DONE → $OUT"
echo "Copy to Desktop:  cp \"$OUT\" \"$HOME/Desktop/dubyduby-$VIDEO_ID.mp4\""
