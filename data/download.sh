#!/bin/bash

# Pfad zur Datei mit den YouTube-Links
LINKS_FILE="links.txt"

# Pfad zur Cookies-Datei
COOKIES_FILE="cookies.txt"

# Verzeichnis zum Speichern der heruntergeladenen Videos
OUTPUT_DIR="./downloads"

# Erstellen Sie das Ausgabeverzeichnis, falls es nicht existiert
mkdir -p "$OUTPUT_DIR"

# Überprüfen, ob die Datei mit den Links existiert
if [[ ! -f "$LINKS_FILE" ]]; then
    echo "Die Datei mit den Links wurde nicht gefunden: $LINKS_FILE"
    exit 1
fi

# Überprüfen, ob die Cookies-Datei existiert
if [[ ! -f "$COOKIES_FILE" ]]; then
    echo "Die Cookies-Datei wurde nicht gefunden: $COOKIES_FILE"
    exit 1
fi

# Schleife durch jede Zeile in der Datei mit den Links
while IFS= read -r URL; do
    # Überspringen Sie leere Zeilen
    if [[ -z "$URL" ]]; then
        continue
    fi

    # Herunterladen des Videos mit yt-dlp
    yt-dlp --cookies "$COOKIES_FILE" -f "bv*[ext=mp4]+ba[ext=m4a]/b[ext=mp4] / bv*+ba/b" -o "$OUTPUT_DIR/%(id)s.%(ext)s" "$URL"

    # Zufällige Pause zwischen 30 und 60 Sekunden einlegen
    PAUSE=$((30 + RANDOM % 31))
    echo "Warte $PAUSE Sekunden vor dem nächsten Download..."
    sleep $PAUSE

done < "$LINKS_FILE"