#!/usr/bin/env bash
# Soniox STT batch. Reads SONIOX_API_KEY from .env (or env).
# Outputs: output/<video_id>/2_transcript/{tokens.json, transcript.md}
set -e
VIDEO_ID="${1:?Usage: $0 <video_id>}"

cd "$(dirname "$0")/.."
[ -f .env ] && set -a && . ./.env && set +a
[ -z "${SONIOX_API_KEY:-}" ] && { echo "SONIOX_API_KEY missing — set in .env" >&2; exit 1; }

AUDIO="output/$VIDEO_ID/1_source/audio.mp3"
[ ! -f "$AUDIO" ] && { echo "Audio missing: $AUDIO" >&2; exit 1; }

OUT_DIR="output/$VIDEO_ID/2_transcript"
mkdir -p "$OUT_DIR"

FILE_ID=$(curl -s -X POST https://api.soniox.com/v1/files \
  -H "Authorization: Bearer $SONIOX_API_KEY" \
  -F "file=@$AUDIO" | jq -r '.id')
[ "$FILE_ID" = "null" ] && { echo "Soniox upload failed" >&2; exit 1; }

TR_ID=$(curl -s -X POST https://api.soniox.com/v1/transcriptions \
  -H "Authorization: Bearer $SONIOX_API_KEY" \
  -H "Content-Type: application/json" \
  -d "{\"model\":\"stt-async-v4\",\"language_hints\":[\"en\",\"ko\"],\"file_id\":\"$FILE_ID\",\"enable_speaker_diarization\":true}" | jq -r '.id')

for _ in $(seq 1 120); do
  STATUS=$(curl -s "https://api.soniox.com/v1/transcriptions/$TR_ID" \
    -H "Authorization: Bearer $SONIOX_API_KEY" | jq -r '.status')
  echo "[transcribe] $STATUS" >&2
  [ "$STATUS" = "completed" ] && break
  [ "$STATUS" = "error" ] && exit 1
  sleep 3
done

curl -s "https://api.soniox.com/v1/transcriptions/$TR_ID/transcript" \
  -H "Authorization: Bearer $SONIOX_API_KEY" > "$OUT_DIR/tokens.json"

# Cleanup Soniox-side
curl -s -X DELETE "https://api.soniox.com/v1/transcriptions/$TR_ID" -H "Authorization: Bearer $SONIOX_API_KEY" >/dev/null || true
curl -s -X DELETE "https://api.soniox.com/v1/files/$FILE_ID" -H "Authorization: Bearer $SONIOX_API_KEY" >/dev/null || true

# Human-readable transcript
{
  echo "# EN transcript (Soniox)"
  echo ""
  echo "Tokens: $(jq '.tokens | length' "$OUT_DIR/tokens.json")"
  echo ""
  echo "## Full text"
  echo ""
  jq -r '[.tokens[].text] | join("")' "$OUT_DIR/tokens.json"
} > "$OUT_DIR/transcript.md"

echo "OK: $OUT_DIR/{tokens.json, transcript.md}"
