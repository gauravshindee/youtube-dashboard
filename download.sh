#!/bin/bash

# Usage: bash download.sh "https://www.youtube.com/watch?v=VIDEO_ID"

URL="$1"
COOKIES_FILE="cookies.txt"
OUTPUT_DIR="."

# Check if URL was passed
if [ -z "$URL" ]; then
  echo "❌ No URL provided."
  exit 1
fi

# Check if cookies file exists
if [ ! -f "$COOKIES_FILE" ]; then
  echo "❌ cookies.txt not found in current directory."
  exit 1
fi

# Run yt-dlp to download best available .mp4 format (single file, no merging)
yt-dlp --cookies "$COOKIES_FILE" -f "best[ext=mp4]" -o "$OUTPUT_DIR/%(id)s.%(ext)s" "$URL"

# Print downloaded filename
yt-dlp --cookies "$COOKIES_FILE" --get-filename -f "best[ext=mp4]" -o "%(id)s.%(ext)s" "$URL"
