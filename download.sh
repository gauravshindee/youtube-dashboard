#!/bin/bash

# --- Settings ---
COOKIES_FILE="cookies.txt"
OUTPUT_DIR="./downloads"

# --- Ensure output dir exists ---
mkdir -p "$OUTPUT_DIR"

# --- Read URL from input argument ---
VIDEO_URL="$1"
if [[ -z "$VIDEO_URL" ]]; then
    echo "❌ No video URL provided."
    exit 1
fi

# --- Download using yt-dlp ---
yt-dlp --cookies "$COOKIES_FILE" \
       -f "bv*[ext=mp4]+ba[ext=m4a]/b[ext=mp4]/bv*+ba/b" \
       -o "$OUTPUT_DIR/%(id)s.%(ext)s" "$VIDEO_URL"

# --- Capture the last downloaded filename ---
DOWNLOADED_FILE=$(ls -t "$OUTPUT_DIR" | head -n 1)

# --- Output only the filename (used by dashboard.py) ---
echo "$DOWNLOADED_FILE"
