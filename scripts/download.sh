#!/usr/bin/env bash
# Download YouTube video + audio.
# Outputs: output/<video_id>/1_source/{video.mp4, audio.mp3}
# Echoes: VIDEO_ID=<id> on stdout (consumed by dub.sh orchestrator).
set -e
URL="${1:?Usage: $0 <youtube_url> [duration_seconds]}"
DURATION="${2:-}"

cd "$(dirname "$0")/.."
YTDLP="binaries/yt-dlp"
[ -x "$YTDLP" ] || { echo "Run bash scripts/setup.sh first" >&2; exit 1; }

VIDEO_ID=$("$YTDLP" --get-id --no-warnings "$URL")
OUT_DIR="output/$VIDEO_ID/1_source"
mkdir -p "$OUT_DIR"

"$YTDLP" --no-playlist --no-warnings \
  -f "bv*+ba/b" --merge-output-format mp4 \
  --extract-audio --audio-format mp3 \
  --keep-video \
  -o "$OUT_DIR/full.%(ext)s" "$URL" >&2

# Rename to predictable names
[ -f "$OUT_DIR/full.mp4" ] && mv "$OUT_DIR/full.mp4" "$OUT_DIR/video.mp4"
[ -f "$OUT_DIR/full.mp3" ] && mv "$OUT_DIR/full.mp3" "$OUT_DIR/audio.mp3"
# yt-dlp leaves f### intermediates; clean
rm -f "$OUT_DIR"/full.* "$OUT_DIR"/*.f*.* 2>/dev/null || true

if [ -n "$DURATION" ]; then
  ffmpeg -y -hide_banner -loglevel error -i "$OUT_DIR/video.mp4" -t "$DURATION" "$OUT_DIR/.cut.mp4"
  ffmpeg -y -hide_banner -loglevel error -i "$OUT_DIR/audio.mp3" -t "$DURATION" "$OUT_DIR/.cut.mp3"
  mv "$OUT_DIR/.cut.mp4" "$OUT_DIR/video.mp4"
  mv "$OUT_DIR/.cut.mp3" "$OUT_DIR/audio.mp3"
fi

echo "VIDEO_ID=$VIDEO_ID"
