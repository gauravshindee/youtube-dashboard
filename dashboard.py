# dashboard.py
import streamlit as st
import json
import os
import pandas as pd
import yt_dlp
import time
import zipfile
import requests

from fetch_videos import main as fetch_videos_main  # Make sure fetch_videos.py has a main() function


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
DATA_FILE = "data/quickwatch.json"
NOT_RELEVANT_FILE = "data/not_relevant.json"
ARCHIVE_FILE = "data/archive.csv"
ARCHIVE_THIRD_PARTY_FILE = "data/archive_third_party.csv"

def load_videos():
    if not os.path.exists(DATA_FILE):
        return []
    with open(DATA_FILE, "r") as f:
        return json.load(f)

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

# --- Archive View ---
def archive_view(csv_path, label="Archive"):
    if not os.path.exists(csv_path):
        st.warning(f"{label} CSV not found.")
        return

    try:
        df = pd.read_csv(csv_path, encoding="utf-8", on_bad_lines="skip")
    except UnicodeDecodeError:
        df = pd.read_csv(csv_path, encoding="latin1", on_bad_lines="skip")

    df.columns = df.columns.str.strip().str.lower()
    df["publish_date"] = pd.to_datetime(df["publish_date"], errors="coerce")

    st.subheader(f"📦 {label}")
    st.markdown("### Filters")
    col1, col2, col3 = st.columns(3)
    with col1:
        search_query = st.text_input("🔍 Search title", key=f"{label}_search")
    with col2:
        channel_names = df["channel_name"].dropna().unique().tolist()
        selected_channel = st.selectbox("🎞 Channel", ["All"] + sorted(channel_names), key=f"{label}_channel")
    with col3:
        min_date = df["publish_date"].min().date()
        max_date = df["publish_date"].max().date()
        start_date, end_date = st.date_input("📅 Date range", [min_date, max_date], key=f"{label}_date")

    filtered = df.copy()
    if search_query:
        filtered = filtered[filtered["title"].str.contains(search_query, case=False, na=False)]
    if selected_channel != "All":
        filtered = filtered[filtered["channel_name"] == selected_channel]
    filtered = filtered[(filtered["publish_date"].dt.date >= start_date) & (filtered["publish_date"].dt.date <= end_date)]

    st.markdown(f"**🔎 {len(filtered)} results found**")
    st.markdown("---")

    per_page = 10
    total_pages = max((len(filtered) - 1) // per_page + 1, 1)
    page = st.number_input("Page", min_value=1, max_value=total_pages, value=1, key=f"{label}_page")

    start = (page - 1) * per_page
    end = start + per_page
    for _, row in filtered.iloc[start:end].iterrows():
        st.subheader(row["title"])
        st.caption(f"{row['channel_name']} • {row['publish_date'].strftime('%Y-%m-%d')}")
        st.video(row["video_link"])
        st.button("⬇️ Download", key=f"dl_{row['video_link']}_{label}")

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
