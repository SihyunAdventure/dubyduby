#!/usr/bin/env bash
# Per-utterance timeline placement (not bulk concat+atempo). Each KO utt
# anchors to its source utterance.start_ms (English speaker's mouth cue),
# overflow-only atempo per utt. Source silence → KO silence (natural).
#
# Outputs:
#   output/<video_id>/6_final/{dubbed_audio.wav, dubbed_video.mp4}
#   output/<video_id>/5_intermediate/placement.json
set -e
VIDEO_ID="${1:?Usage: $0 <video_id>}"

cd "$(dirname "$0")/.."

BASE="output/$VIDEO_ID"
INTER="$BASE/5_intermediate"
FINAL="$BASE/6_final"
SRC_VIDEO="$BASE/1_source/video.mp4"
mkdir -p "$INTER" "$FINAL"

# venv python — explicit path is more reliable than `source activate` under set -e
PY=.venv/bin/python

# 1. Video duration in ms (used for silent buffer)
VID_DUR_S=$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$SRC_VIDEO")
VID_DUR_MS=$("$PY" -c "print(int($VID_DUR_S * 1000))")
echo "[finalize] video duration: ${VID_DUR_S}s (${VID_DUR_MS}ms)"

# 2. Place per-utt wavs at source timeline + per-utt atempo
"$PY" scripts/place_timeline.py "$VIDEO_ID" "$VID_DUR_MS"

# 3. silencedetect on dub for verification + subtitle snap
ffmpeg -hide_banner -i "$FINAL/dubbed_audio.wav" \
  -af "silencedetect=noise=-40dB:duration=0.1" -f null - 2>&1 \
  | grep -E "silence_(start|end)" > "$INTER/silence_log_final.txt" || true

# 4. ffmpeg mux video stream + ko audio
ffmpeg -y -hide_banner -loglevel error \
  -i "$SRC_VIDEO" -i "$FINAL/dubbed_audio.wav" \
  -map 0:v -map 1:a -c:v copy -c:a aac -shortest \
  "$FINAL/dubbed_video.mp4"
echo "OK: $FINAL/dubbed_video.mp4"

# 5. Generate ASS subtitle + burn-in version (timing from placement.json)
"$PY" scripts/subtitle.py "$VIDEO_ID"

FONT_DIR="$(pwd)/fonts"
SUB_FILE="$FINAL/subtitles.ass"
if [ -f "$SUB_FILE" ]; then
  FFMPEG_BIN=$(ls /opt/homebrew/Cellar/ffmpeg-full/*/bin/ffmpeg 2>/dev/null | head -1)
  [ -z "$FFMPEG_BIN" ] && FFMPEG_BIN=ffmpeg
  # H.265/HEVC for ~30-40% smaller files than H.264 at equivalent quality —
  # matters because subtitle burn-in forces video re-encode and we want to
  # stay close to the original source size. tag:v hvc1 keeps QuickTime / iOS happy.
  "$FFMPEG_BIN" -y -hide_banner -loglevel error \
    -i "$FINAL/dubbed_video.mp4" \
    -vf "subtitles=$SUB_FILE:fontsdir=$FONT_DIR" \
    -c:v libx265 -preset fast -crf 28 -tag:v hvc1 \
    -c:a copy -movflags +faststart \
    "$FINAL/dubbed_video_subtitled.mp4"
  echo "OK: $FINAL/dubbed_video_subtitled.mp4 (Korean subtitles burned in)"
fi
