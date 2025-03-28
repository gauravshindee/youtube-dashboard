# dashboard.py
import streamlit as st
import json
import os
import pandas as pd
import yt_dlp
import time
import zipfile
import requests
import gspread
from oauth2client.service_account import ServiceAccountCredentials

from fetch_videos import fetch_all as fetch_videos_main

# --- GitHub ZIP URLs ---
RAW_ZIP_URL_OFFICIAL = "https://raw.githubusercontent.com/gauravshindee/youtube-dashboard/main/data/archive.csv.zip"
RAW_ZIP_URL_THIRD_PARTY = "https://raw.githubusercontent.com/gauravshindee/youtube-dashboard/main/data/archive_third_party.csv.zip"

# --- Download and extract if not already present ---
def download_and_extract_zip(url, extract_to):
    zip_path = "temp.zip"
    r = requests.get(url)
    if r.status_code == 200:
        with open(zip_path, "wb") as f:
            f.write(r.content)
        with zipfile.ZipFile(zip_path, "r") as zip_ref:
            zip_ref.extractall("data")
        os.remove(zip_path)
    else:
        st.error(f"❌ Failed to download zip from {url}")

os.makedirs("data", exist_ok=True)

if not os.path.exists("data/archive.csv"):
    download_and_extract_zip(RAW_ZIP_URL_OFFICIAL, "data")
if not os.path.exists("data/archive_third_party.csv"):
    download_and_extract_zip(RAW_ZIP_URL_THIRD_PARTY, "data")

# --- Secure Login ---
CORRECT_PASSWORD = "DemoUp2025!"
LOGIN_TIMEOUT = 4 * 60 * 60

def authenticate():
    st.set_page_config(page_title="🔐 Secure Login", layout="centered")
    st.markdown("## 🔐 Welcome to DemoUp Dashboard")
    password = st.text_input("Password", type="password")
    if password == CORRECT_PASSWORD:
        st.session_state["authenticated"] = True
        st.session_state["login_time"] = time.time()
        st.success("Access granted. Loading dashboard...")
        st.rerun()
    elif password:
        st.error("❌ Incorrect password.")

auth_time = st.session_state.get("login_time", 0)
time_since_login = time.time() - auth_time
if "authenticated" not in st.session_state or not st.session_state["authenticated"] or time_since_login > LOGIN_TIMEOUT:
    st.session_state["authenticated"] = False
    authenticate()
    st.stop()

# --- Setup Directories ---
os.makedirs("downloads", exist_ok=True)

# --- File Paths ---
NOT_RELEVANT_FILE = "data/not_relevant.json"
ARCHIVE_FILE = "data/archive.csv"
ARCHIVE_THIRD_PARTY_FILE = "data/archive_third_party.csv"

# --- Google Sheets Setup ---
SHEET_ID = "1VULPPJEhAtgdZE3ocWeAXsUVZFL7iGGC5TdyrBgKjzY"
SHEET_NAME = "Sheet1"

# Save secret to local file
if not os.path.exists("gcp_credentials.json"):
    with open("gcp_credentials.json", "w") as f:
        f.write(st.secrets["gcp_service_account"])

# Auth function for gspread
def get_gsheet_client():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_name("gcp_credentials.json", scope)
    return gspread.authorize(creds)

def load_videos():
    client = get_gsheet_client()
    sheet = client.open_by_key(SHEET_ID).worksheet(SHEET_NAME)
    records = sheet.get_all_records()
    return records

def save_videos(data):
    client = get_gsheet_client()
    sheet = client.open_by_key(SHEET_ID).worksheet(SHEET_NAME)
    sheet.clear()
    headers = list(data[0].keys())
    sheet.append_row(headers)
    for row in data:
        sheet.append_row([row.get(h, "") for h in headers])

def load_not_relevant():
    if not os.path.exists(NOT_RELEVANT_FILE):
        return []
    with open(NOT_RELEVANT_FILE, "r") as f:
        return json.load(f)

def save_not_relevant(data):
    with open(NOT_RELEVANT_FILE, "w") as f:
        json.dump(data, f, indent=2)

def download_video(video_url):
    ydl_opts = {
        "format": "best[ext=mp4]/best",
        "outtmpl": "downloads/%(id)s.%(ext)s",
        "quiet": True
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(video_url, download=True)
        video_id = info.get("id")
        ext = info.get("ext")
        file_path = f"downloads/{video_id}.{ext}"
        return file_path, f"{video_id}.{ext}"

# --- UI Config ---
st.set_page_config(page_title="YouTube Dashboard", layout="wide")
st.title("📺 YouTube Video Dashboard")

# --- Sidebar View ---
view = st.sidebar.radio("📂 Select View", ["⚡ QuickWatch", "🚫 Not Relevant", "📦 Archive (Official)", "📦 Archive (Third-Party)"])

if view == "⚡ QuickWatch":
    with st.expander("📡 Run Manual Video Fetch (Admin Only)"):
        password = st.text_input("Enter admin password to fetch new videos", type="password")
        if password == "demoup123":
            if st.button("🔁 Fetch New Videos Now"):
                with st.spinner("Fetching videos..."):
                    try:
                        fetch_videos_main()
                        st.success("✅ Fetch completed successfully.")
                        st.rerun()
                    except Exception as e:
                        st.error("❌ Fetch failed.")
                        st.exception(e)
        elif password:
            st.error("❌ Incorrect password.")

    st.markdown("---")
    videos = load_videos()
    not_relevant = load_not_relevant()

    for video in videos:
        if video['link'] in [v['link'] for v in not_relevant]:
            continue
        st.subheader(video["title"])
        st.caption(f"{video['channel_name']} • {video['publish_date']}")
        st.video(video["link"])
        col1, col2 = st.columns(2)
        with col1:
            if st.button("⬇️ Download", key=f"dl_{video['link']}"):
                with st.spinner("Downloading..."):
                    file_path, file_name = download_video(video["link"])
                    with open(file_path, "rb") as file:
                        st.download_button("📥 Save", data=file, file_name=file_name, mime="video/mp4")
        with col2:
            if st.button("🚫 Not Relevant", key=f"nr_{video['link']}"):
                not_relevant.append(video)
                save_not_relevant(not_relevant)
                st.rerun()

elif view == "🚫 Not Relevant":
    videos = load_not_relevant()
    if not videos:
        st.info("No not-relevant videos yet.")
    else:
        for video in videos:
            st.subheader(video["title"])
            st.caption(f"{video['channel_name']} • {video['publish_date']}")
            st.video(video["link"])

elif view == "📦 Archive (Official)":
    archive_view(ARCHIVE_FILE, label="Archive (Official)")

elif view == "📦 Archive (Third-Party)":
    archive_view(ARCHIVE_THIRD_PARTY_FILE, label="Archive (Third-Party)")
