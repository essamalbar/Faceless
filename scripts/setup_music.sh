#!/usr/bin/env bash
# Download a curated bundle of CC0 / CC-BY atmospheric horror tracks
# into assets/music/. Run once.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BUNDLE_DIR="$REPO_ROOT/assets/music"
mkdir -p "$BUNDLE_DIR"

# Track list — replace these URLs with actual CC0/CC-BY tracks you've vetted.
# Format: filename|mood|license|source_url|attribution
# License must be CC0 or CC-BY (verify on source page before using).
# Recommended sources:
#   https://pixabay.com/music/search/horror%20ambient/
#   https://freemusicarchive.org/genre/Soundtrack/
TRACKS=(
  # MOOD: drone (long sustained tones, no melody)
  # "drone-01.mp3|drone|CC0|https://pixabay.com/.../drone-1.mp3|"
  # "drone-02.mp3|drone|CC0|https://pixabay.com/.../drone-2.mp3|"
  # MOOD: dread (low rumble, heartbeat-like)
  # "dread-01.mp3|dread|CC0|https://pixabay.com/.../dread-1.mp3|"
  # MOOD: cosmic (otherworldly, spacious)
  # "cosmic-01.mp3|cosmic|CC0|https://pixabay.com/.../cosmic-1.mp3|"
  # MOOD: discovery (slow tension build)
  # "discovery-01.mp3|discovery|CC0|https://pixabay.com/.../discovery-1.mp3|"
)

if [ ${#TRACKS[@]} -eq 0 ]; then
  echo "ERROR: TRACKS array is empty. Populate scripts/setup_music.sh with vetted CC0/CC-BY URLs first."
  echo "Recommended sources:"
  echo "  https://pixabay.com/music/search/horror%20ambient/"
  echo "  https://freemusicarchive.org/"
  exit 1
fi

JSON_ENTRIES=()
for entry in "${TRACKS[@]}"; do
  IFS='|' read -r filename mood license source_url attribution <<<"$entry"
  echo "Downloading $filename ..."
  curl -fsSL "$source_url" -o "$BUNDLE_DIR/$filename"
  duration_s=$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$BUNDLE_DIR/$filename" | cut -d. -f1)
  attr_json="null"
  [ -n "$attribution" ] && attr_json="\"$attribution\""
  JSON_ENTRIES+=("{\"filename\":\"$filename\",\"duration_s\":$duration_s,\"mood\":\"$mood\",\"license\":\"$license\",\"source_url\":\"$source_url\",\"attribution\":$attr_json}")
done

# Write tracks.json
{
  echo "["
  for i in "${!JSON_ENTRIES[@]}"; do
    if [ "$i" -eq $((${#JSON_ENTRIES[@]} - 1)) ]; then
      echo "  ${JSON_ENTRIES[$i]}"
    else
      echo "  ${JSON_ENTRIES[$i]},"
    fi
  done
  echo "]"
} > "$BUNDLE_DIR/tracks.json"

echo "Bundle written to $BUNDLE_DIR with ${#TRACKS[@]} tracks."
