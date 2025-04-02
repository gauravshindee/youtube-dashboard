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

# --- Google Sheets Setup ---
GOOGLE_SHEET_ID = "1VULPPJEhAtgdZE3ocWeAXsUVZFL7iGGC5TdyrBgKjzY"
SHEET_QUICKWATCH = "quickwatch"
SHEET_NOT_RELEVANT = "not_relevant"
SHEET_MOVIE_IDS = "downloaded_movie_id"

SERVICE_ACCOUNT_SECRET = json.loads(st.secrets["gcp_service_account"])

scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
credentials = ServiceAccountCredentials.from_json_keyfile_dict(SERVICE_ACCOUNT_SECRET, scope)
gs_client = gspread.authorize(credentials)

# --- Helper Functions for GSheet ---
def get_sheet(sheet_name):
    sh = gs_client.open_by_key(GOOGLE_SHEET_ID)
    try:
        return sh.worksheet(sheet_name)
    except gspread.exceptions.WorksheetNotFound:
        sheet = sh.add_worksheet(title=sheet_name, rows="1000", cols="5")
        if sheet_name == SHEET_NOT_RELEVANT:
            sheet.update("A1:E1", [["video_id", "title", "channel_name", "publish_date", "link"]])
        return sheet

def load_sheet_records(sheet_name):
    sheet = get_sheet(sheet_name)
    return sheet.get_all_records()

def remove_video_from_sheet(sheet_name, video_id):
    sheet = get_sheet(sheet_name)
    records = sheet.get_all_records()
    headers = list(records[0].keys()) if records else ["video_id", "title", "channel_name", "publish_date", "link"]
    updated = [row for row in records if str(row["video_id"]) != str(video_id)]
    sheet.clear()
    sheet.append_row(headers)
    for row in updated:
        sheet.append_row([row.get(h, "") for h in headers])

def append_to_not_relevant(video):
    sheet = get_sheet(SHEET_NOT_RELEVANT)
    row = [video["video_id"], video["title"], video["channel_name"], video["publish_date"], video["link"]]
    sheet.append_row(row)

def save_movie_id_to_sheet(movie_id):
    try:
        sheet = get_sheet(SHEET_MOVIE_IDS)
        sheet.append_row([movie_id])
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
        file_path = f"downloads/{video_id}.{ext}"
        return file_path, f"{video_id}.{ext}"

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
if "authenticated" not in st.session_state or not st.session_state["authenticated"] or (time.time() - auth_time > LOGIN_TIMEOUT):
    st.session_state["authenticated"] = False
    authenticate()
    st.stop()

# --- UI Setup ---
st.set_page_config(page_title="YouTube Dashboard", layout="wide")
st.title("📺 YouTube Video Dashboard")

# --- Sidebar View ---
view = st.sidebar.radio("📂 Select View", ["⚡ QuickWatch", "🚫 Not Relevant", "📦 Archive (Official)", "📦 Archive (Third-Party)"])

# --- QuickWatch View ---
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

    st.subheader("⚡ QuickWatch")
    all_videos = load_sheet_records(SHEET_QUICKWATCH)
    not_relevant = load_sheet_records(SHEET_NOT_RELEVANT)
    excluded_ids = {v["video_id"] for v in not_relevant}

    # --- Filters ---
    col1, col2, col3 = st.columns(3)
    with col1:
        search_query = st.text_input("🔍 Search title")
    with col2:
        channel_names = sorted({v["channel_name"] for v in all_videos})
        selected_channel = st.selectbox("📼 Channel", ["All"] + channel_names)
    with col3:
        all_dates = [pd.to_datetime(v["publish_date"]) for v in all_videos]
        if all_dates:
            min_date = min(all_dates).date()
            max_date = max(all_dates).date()
        else:
            min_date = max_date = pd.Timestamp.today().date()
        start_date, end_date = st.date_input("📅 Date range", [min_date, max_date])

    # --- Filter Data ---
    filtered = [v for v in all_videos if v["video_id"] not in excluded_ids]
    if search_query:
        filtered = [v for v in filtered if search_query.lower() in v["title"].lower()]
    if selected_channel != "All":
        filtered = [v for v in filtered if v["channel_name"] == selected_channel]
    filtered = [v for v in filtered if start_date <= pd.to_datetime(v["publish_date"]).date() <= end_date]

    st.markdown(f"🔎 **{len(filtered)} results found**")
    st.markdown("---")

    # --- Pagination ---
    PER_PAGE = 20
    total_pages = max((len(filtered) - 1) // PER_PAGE + 1, 1)
    page = st.number_input("Page", min_value=1, max_value=total_pages, value=1, step=1, key="quickwatch_page")
    start = (page - 1) * PER_PAGE
    end = start + PER_PAGE
    st.markdown(f"<div style='text-align:right;'>Page {page} of {total_pages}</div>", unsafe_allow_html=True)

    for video in filtered[start:end]:
        st.subheader(video["title"])
        st.caption(f"{video['channel_name']} • {video['publish_date']}")
        st.video(video["link"])

        col1, col2 = st.columns(2)
        with col1:
            if st.button("⬇️ Download", key=f"dl_{video['video_id']}"):
                with st.spinner("Downloading..."):
                    file_path, file_name = download_video(video["link"])
                    with open(file_path, "rb") as file:
                        with st.modal("💾 Enter DemoUp Movie ID"):
                            st.markdown("### 💾 Save Movie ID")
                            movie_id = st.text_input("Enter numeric DemoUp Movie ID", key=f"id_{video['video_id']}")
                            if movie_id and not movie_id.isnumeric():
                                st.error("Only numbers allowed.")
                            elif movie_id and st.button("Save ID", key=f"save_{video['video_id']}"):
                                save_movie_id_to_sheet(movie_id)
                                st.success("Saved!")
                                st.download_button("📥 Save Video", data=file, file_name=file_name, mime="video/mp4")
        with col2:
            if st.button("🚫 Not Relevant", key=f"nr_{video['video_id']}"):
                append_to_not_relevant(video)
                remove_video_from_sheet(SHEET_QUICKWATCH, video["video_id"])
                st.success("✅ Moved to Not Relevant")
                st.rerun()

    st.markdown(f"<div style='text-align:right;'>Page {page} of {total_pages}</div>", unsafe_allow_html=True)

# --- Not Relevant View ---
elif view == "🚫 Not Relevant":
    videos = load_sheet_records(SHEET_NOT_RELEVANT)
    if not videos:
        st.info("No videos marked not relevant yet.")
    else:
        for video in videos:
            st.subheader(video["title"])
            st.caption(f"{video['channel_name']} • {video['publish_date']}")
            st.video(video["link"])

# --- Archive Views ---
elif view == "📦 Archive (Official)":
    st.info("Coming soon: Official Archive View")

elif view == "📦 Archive (Third-Party)":
    st.info("Coming soon: Third-Party Archive View")
