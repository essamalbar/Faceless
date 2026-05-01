#!/usr/bin/env bash
# Generate 4 placeholder atmospheric horror tracks via ffmpeg synthesis.
# These are intentionally simple — public-domain (CC0) audio you generate
# locally. Replace with real CC-licensed tracks via scripts/setup_music.sh
# once you have curated URLs.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BUNDLE_DIR="$REPO_ROOT/assets/music"
mkdir -p "$BUNDLE_DIR"

DURATION=300  # 5 minutes per track

echo "Generating drone-01.mp3 (60Hz sustained drone with reverb)..."
ffmpeg -y -hide_banner -loglevel error \
  -f lavfi -i "sine=frequency=60:duration=$DURATION" \
  -filter:a "tremolo=f=0.3:d=0.3,aecho=0.8:0.9:1000:0.3,volume=0.7" \
  -ar 24000 -ac 2 -b:a 192k "$BUNDLE_DIR/drone-01.mp3"

echo "Generating dread-01.mp3 (40Hz sub-bass with heartbeat pulse)..."
ffmpeg -y -hide_banner -loglevel error \
  -f lavfi -i "sine=frequency=40:duration=$DURATION" \
  -filter:a "tremolo=f=1.0:d=0.5,aecho=0.8:0.9:500:0.4,volume=0.7" \
  -ar 24000 -ac 2 -b:a 192k "$BUNDLE_DIR/dread-01.mp3"

echo "Generating cosmic-01.mp3 (detuned sines with deep reverb)..."
ffmpeg -y -hide_banner -loglevel error \
  -f lavfi -i "sine=frequency=200:duration=$DURATION" \
  -filter:a "aecho=0.8:0.9:1500:0.5,aecho=0.8:0.7:2000:0.3,volume=0.3" \
  -ar 24000 -ac 2 -b:a 192k "$BUNDLE_DIR/cosmic-01.mp3"

echo "Generating discovery-01.mp3 (brown noise tension build)..."
ffmpeg -y -hide_banner -loglevel error \
  -f lavfi -i "anoisesrc=color=brown:duration=$DURATION" \
  -filter:a "afade=t=in:st=0:d=15,volume=0.15" \
  -ar 24000 -ac 2 -b:a 192k "$BUNDLE_DIR/discovery-01.mp3"

# Generate tracks.json
cat > "$BUNDLE_DIR/tracks.json" <<'JSON'
[
  {
    "filename": "drone-01.mp3",
    "duration_s": 300,
    "mood": "drone",
    "license": "CC0",
    "source_url": "synthesized locally via ffmpeg (placeholder)",
    "attribution": null
  },
  {
    "filename": "dread-01.mp3",
    "duration_s": 300,
    "mood": "dread",
    "license": "CC0",
    "source_url": "synthesized locally via ffmpeg (placeholder)",
    "attribution": null
  },
  {
    "filename": "cosmic-01.mp3",
    "duration_s": 300,
    "mood": "cosmic",
    "license": "CC0",
    "source_url": "synthesized locally via ffmpeg (placeholder)",
    "attribution": null
  },
  {
    "filename": "discovery-01.mp3",
    "duration_s": 300,
    "mood": "discovery",
    "license": "CC0",
    "source_url": "synthesized locally via ffmpeg (placeholder)",
    "attribution": null
  }
]
JSON

echo ""
echo "Done. Bundle written to $BUNDLE_DIR:"
ls -la "$BUNDLE_DIR"
echo ""
echo "These are placeholder tracks. To replace with curated CC-licensed music,"
echo "populate scripts/setup_music.sh with real URLs and run it instead."
