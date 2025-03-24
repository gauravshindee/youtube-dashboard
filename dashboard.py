# dashboard.py
import streamlit as st
import json
import os
import subprocess
import pandas as pd
import yt_dlp

# Ensure directories exist
os.makedirs("data", exist_ok=True)
os.makedirs("downloads", exist_ok=True)

# File paths
DATA_FILE = "data/quickwatch.json"
NOT_RELEVANT_FILE = "data/not_relevant.json"
ARCHIVE_FILE = "data/archive.csv"

# --- Data functions
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

# --- Video download logic
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

# --- UI Config
st.set_page_config(page_title="YouTube Dashboard", layout="wide")
st.title("📺 YouTube Video Dashboard")

# Sidebar
view = st.sidebar.radio("📂 Select View", ["⚡ QuickWatch", "🚫 Not Relevant", "📦 Archive"])

# --- Views
if view == "⚡ QuickWatch":
    # Admin Manual Fetch
    with st.expander("📡 Run Manual Video Fetch (Admin Only)"):
        password = st.text_input("Enter admin password to fetch new videos", type="password")
        if password == "demoup123":
            if st.button("🔁 Fetch New Videos Now"):
                with st.spinner("Fetching videos... this may take up to 1–2 minutes..."):
                    result = subprocess.run(
                        ["python3", "fetch_videos.py"],
                        capture_output=True,
                        text=True
                    )

                if result.returncode == 0:
                    st.success("✅ Fetch completed successfully.")
                    st.text(result.stdout)
                    st.rerun()
                else:
                    st.error("❌ Fetch failed.")
                    st.code(result.stderr or "Unknown error")
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
                with st.spinner("Downloading video..."):
                    file_path, file_name = download_video(video["link"])
                    with open(file_path, "rb") as file:
                        st.download_button(
                            label="📥 Click here to save to your device",
                            data=file,
                            file_name=file_name,
                            mime="video/mp4"
                        )

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

elif view == "📦 Archive":
    if not os.path.exists(ARCHIVE_FILE):
        st.warning("Archive CSV not found.")
    else:
        df = pd.read_csv(ARCHIVE_FILE, encoding="utf-8", on_bad_lines="skip")

        # --- Search Bar
        search_query = st.text_input("🔍 Search title or channel", "")
        if search_query:
            df = df[df["title"].str.contains(search_query, case=False, na=False) |
                    df["channel_name"].str.contains(search_query, case=False, na=False)]

        # --- Pagination
        per_page = 10
        total_pages = (len(df) - 1) // per_page + 1
        page = st.number_input("Page", min_value=1, max_value=total_pages, value=1)

        start = (page - 1) * per_page
        end = start + per_page

        for _, row in df.iloc[start:end].iterrows():
            st.subheader(row["title"])
            st.caption(f"{row['channel_name']} • {row['publish_date']}")
            st.video(row["video_link"])
            st.button("⬇️ Download", key=f"dl_{row['video_link']}")
