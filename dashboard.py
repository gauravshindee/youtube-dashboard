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

# --- Constants ---
GOOGLE_SHEET_ID = "1VULPPJEhAtgdZE3ocWeAXsUVZFL7iGGC5TdyrBgKjzY"
QUICKWATCH_SHEET = "quickwatch"
NOT_RELEVANT_SHEET = "not_relevant"
MOVIE_ID_SHEET = "downloaded_movie_id"
CORRECT_PASSWORD = "DemoUp2025!"
LOGIN_TIMEOUT = 4 * 60 * 60

SERVICE_ACCOUNT_SECRET = json.loads(st.secrets["gcp_service_account"])
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
credentials = ServiceAccountCredentials.from_json_keyfile_dict(SERVICE_ACCOUNT_SECRET, scope)
gs_client = gspread.authorize(credentials)

os.makedirs("downloads", exist_ok=True)

# --- UI Config ---
st.set_page_config(page_title="YouTube Dashboard", layout="wide")
st.title("📺 YouTube Video Dashboard")

# --- Authentication ---
def authenticate():
    st.markdown("## 🔐 Welcome to DemoUp Dashboard")
    password = st.text_input("Password", type="password")
    if password == CORRECT_PASSWORD:
        st.session_state["authenticated"] = True
        st.session_state["login_time"] = time.time()
        st.rerun()
    elif password:
        st.error("❌ Incorrect password.")

auth_time = st.session_state.get("login_time", 0)
time_since_login = time.time() - auth_time
if "authenticated" not in st.session_state or not st.session_state["authenticated"] or time_since_login > LOGIN_TIMEOUT:
    st.session_state["authenticated"] = False
    authenticate()
    st.stop()

# --- Google Sheets ---
def load_sheet(name):
    return gs_client.open_by_key(GOOGLE_SHEET_ID).worksheet(name)

def load_quickwatch():
    return load_sheet(QUICKWATCH_SHEET).get_all_records()

def load_not_relevant():
    try:
        return load_sheet(NOT_RELEVANT_SHEET).get_all_records()
    except gspread.exceptions.WorksheetNotFound:
        return []

def move_to_not_relevant(video):
    try:
        sh = gs_client.open_by_key(GOOGLE_SHEET_ID)
        qsheet = sh.worksheet(QUICKWATCH_SHEET)
        try:
            nsheet = sh.worksheet(NOT_RELEVANT_SHEET)
        except gspread.exceptions.WorksheetNotFound:
            nsheet = sh.add_worksheet(title=NOT_RELEVANT_SHEET, rows="1000", cols="5")
            nsheet.update("A1:E1", [["video_id", "title", "channel_name", "publish_date", "link"]])

        rows = qsheet.get_all_records()
        updated = []
        removed = None

        for r in rows:
            if r.get("video_id") == video["video_id"]:
                removed = r
            else:
                updated.append(r)

        if removed:
            nsheet.append_row([str(removed.get(col, "")) for col in ["video_id", "title", "channel_name", "publish_date", "link"]])

        qsheet.clear()
        if updated:
            qsheet.append_row(list(updated[0].keys()))
            qsheet.append_rows([list(row.values()) for row in updated])
        else:
            qsheet.append_row(["video_id", "title", "channel_name", "publish_date", "link"])
    except Exception as e:
        st.error(f"Failed to move to Not Relevant: {e}")

def save_movie_id_entry(movie_id, video):
    try:
        sh = gs_client.open_by_key(GOOGLE_SHEET_ID)
        try:
            sheet = sh.worksheet(MOVIE_ID_SHEET)
        except gspread.exceptions.WorksheetNotFound:
            sheet = sh.add_worksheet(title=MOVIE_ID_SHEET, rows="1000", cols="6")
            sheet.update("A1:F1", [["movie_id", "video_id", "title", "channel_name", "publish_date", "link"]])
        row = [
            str(movie_id),
            str(video.get("video_id", "")),
            str(video.get("title", "")),
            str(video.get("channel_name", "")),
            str(video.get("publish_date", "")),
            str(video.get("link", ""))
        ]
        sheet.append_row(row)
    except Exception as e:
        st.error(f"Failed to save Movie ID: {e}")

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
        return f"downloads/{video_id}.{ext}", f"{video_id}.{ext}"

# --- Sidebar View ---
view = st.sidebar.radio("📂 Select View", ["⚡ QuickWatch", "🚫 Not Relevant"])

if view == "⚡ QuickWatch":
    with st.expander("📡 Run Manual Video Fetch (Admin Only)"):
        admin_pw = st.text_input("Enter admin password", type="password")
        if admin_pw == "demoup123":
            if st.button("🔁 Fetch New Videos Now"):
                with st.spinner("Fetching videos..."):
                    try:
                        fetch_videos_main()
                        st.success("✅ Fetch completed.")
                        st.rerun()
                    except Exception as e:
                        st.error("❌ Fetch failed.")
                        st.exception(e)

    st.markdown("---")
    videos = load_quickwatch()
    not_relevant = load_not_relevant()

    df = pd.DataFrame(videos)
    df["publish_date"] = pd.to_datetime(df["publish_date"], errors="coerce")

    col1, col2, col3 = st.columns(3)
    with col1:
        search_query = st.text_input("🔍 Search title")
    with col2:
        selected_channel = st.selectbox("🎞 Channel", ["All"] + sorted(df["channel_name"].dropna().unique()))
    with col3:
        min_date = df["publish_date"].min().date()
        max_date = df["publish_date"].max().date()
        date_range = st.date_input("📅 Date range", [min_date, max_date])

    if len(date_range) != 2:
        st.warning("Please select both start and end dates.")
        st.stop()

    start_date, end_date = date_range

    filtered = df.copy()
    if search_query:
        filtered = filtered[filtered["title"].str.contains(search_query, case=False, na=False)]
    if selected_channel != "All":
        filtered = filtered[filtered["channel_name"] == selected_channel]
    filtered = filtered[(filtered["publish_date"].dt.date >= start_date) & (filtered["publish_date"].dt.date <= end_date)]

    st.markdown(f"**🔎 {len(filtered)} results found**")

    per_page = 20
    total_pages = max(1, (len(filtered) - 1) // per_page + 1)
    page = st.number_input("Page", 1, total_pages, 1, key="quickwatch_page")

    st.markdown(f"Page {page} of {total_pages}")
    start = (page - 1) * per_page
    end = start + per_page
    page_videos = filtered.iloc[start:end].to_dict("records")

    st.markdown("---")

    for video in page_videos:
        st.subheader(video["title"])
        st.caption(f"{video['channel_name']} • {video['publish_date']}")
        st.video(video["link"])

        col1, col2 = st.columns(2)
        with col1:
            if st.button("⬇️ Download", key=f"dl_{video['link']}"):
                with st.spinner("Downloading..."):
                    try:
                        path, fname = download_video(video["link"])
                        with open(path, "rb") as file:
                            with st.modal("💾 Enter DemoUp Movie ID", key=f"modal_{video['video_id']}"):
                                st.markdown("### 💾 Save Movie ID")
                                movie_id = st.text_input("Enter numeric DemoUp Movie ID", key=f"id_{video['video_id']}")
                                if movie_id and not movie_id.isnumeric():
                                    st.error("Only numbers allowed.")
                                elif movie_id and st.button("Save ID", key=f"save_{video['video_id']}"):
                                    save_movie_id_entry(movie_id, video)
                                    st.success("✅ Movie ID saved.")
                                    st.download_button("📥 Download", data=file, file_name=fname, mime="video/mp4")
                    except Exception as e:
                        st.error(f"Download failed: {e}")
        with col2:
            if st.button("🚫 Not Relevant", key=f"nr_{video['video_id']}"):
                move_to_not_relevant(video)
                st.rerun()

    st.markdown(f"Page {page} of {total_pages}")

elif view == "🚫 Not Relevant":
    st.subheader("🚫 Not Relevant Videos")
    videos = load_not_relevant()
    for video in videos:
        st.subheader(video["title"])
        st.caption(f"{video['channel_name']} • {video['publish_date']}")
        st.video(video["link"])
