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
QUICKWATCH_TAB = "quickwatch"
NOT_RELEVANT_TAB = "not_relevant"
MOVIE_ID_TAB = "downloaded_movie_id"

SERVICE_ACCOUNT_SECRET = json.loads(st.secrets["gcp_service_account"])
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
credentials = ServiceAccountCredentials.from_json_keyfile_dict(SERVICE_ACCOUNT_SECRET, scope)
gs_client = gspread.authorize(credentials)

# --- Data functions ---
def get_sheet(tab):
    try:
        return gs_client.open_by_key(GOOGLE_SHEET_ID).worksheet(tab)
    except gspread.exceptions.WorksheetNotFound:
        sheet = gs_client.open_by_key(GOOGLE_SHEET_ID).add_worksheet(title=tab, rows="1000", cols="10")
        if tab == NOT_RELEVANT_TAB:
            sheet.append_row(["video_id", "title", "channel_name", "publish_date", "link"])
        if tab == MOVIE_ID_TAB:
            sheet.append_row(["movie_id"])
        return sheet

def load_quickwatch():
    sheet = get_sheet(QUICKWATCH_TAB)
    return sheet.get_all_records()

def load_not_relevant():
    sheet = get_sheet(NOT_RELEVANT_TAB)
    return sheet.get_all_records()

def save_movie_id(movie_id):
    sheet = get_sheet(MOVIE_ID_TAB)
    sheet.append_row([movie_id])

def move_to_not_relevant(video):
    try:
        sheet_qw = get_sheet(QUICKWATCH_TAB)
        qw_data = pd.DataFrame(sheet_qw.get_all_records())
        row_index = qw_data[qw_data["video_id"] == video["video_id"]].index
        if not row_index.empty:
            row_num = row_index[0] + 2
            sheet_qw.delete_rows(row_num)
        sheet_nr = get_sheet(NOT_RELEVANT_TAB)
        sheet_nr.append_row([video[k] for k in ["video_id", "title", "channel_name", "publish_date", "link"]])
    except Exception as e:
        st.error(f"Failed to move to Not Relevant: {e}")

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
if "authenticated" not in st.session_state or not st.session_state["authenticated"] or time.time() - auth_time > LOGIN_TIMEOUT:
    st.session_state["authenticated"] = False
    authenticate()
    st.stop()

# --- Downloader ---
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
        path = f"downloads/{video_id}.{ext}"
        return path, f"{video_id}.{ext}"

# --- UI Config ---
st.set_page_config(page_title="YouTube Dashboard", layout="wide")
st.title("📺 YouTube Video Dashboard")

# --- Views ---
view = st.sidebar.radio("📂 Select View", ["⚡ QuickWatch", "🚫 Not Relevant"])

if view == "⚡ QuickWatch":
    with st.expander("📡 Run Manual Video Fetch (Admin Only)"):
        password = st.text_input("Enter admin password to fetch new videos", type="password")
        if password == "demoup123":
            if st.button("🔁 Fetch New Videos Now"):
                with st.spinner("Fetching videos..."):
                    try:
                        fetch_videos_main()
                        st.success("✅ Fetch completed.")
                        st.rerun()
                    except Exception as e:
                        st.error("❌ Fetch failed.")
                        st.exception(e)

    videos = load_quickwatch()
    not_relevant = load_not_relevant()

    df = pd.DataFrame(videos)
    df["publish_date"] = pd.to_datetime(df["publish_date"], errors="coerce")

    st.markdown("### Filters")
    col1, col2, col3 = st.columns(3)
    with col1:
        query = st.text_input("🔍 Search title")
    with col2:
        channel = st.selectbox("🎞 Channel", ["All"] + sorted(df["channel_name"].dropna().unique().tolist()))
    with col3:
        min_date = df["publish_date"].min().date()
        max_date = df["publish_date"].max().date()
        date_range = st.date_input("📅 Date range", [min_date, max_date])

    if query:
        df = df[df["title"].str.contains(query, case=False, na=False)]
    if channel != "All":
        df = df[df["channel_name"] == channel]
    df = df[df["publish_date"].dt.date.between(date_range[0], date_range[1])]

    total_results = len(df)
    st.markdown(f"**🔎 {total_results} results found**")
    st.markdown("---")

    # Pagination
    per_page = 20
    total_pages = max((total_results - 1) // per_page + 1, 1)
    page = st.number_input("Page", min_value=1, max_value=total_pages, value=1, key="quickwatch_page_top")
    start = (page - 1) * per_page
    end = start + per_page

    # Show videos
    for idx, row in df.iloc[start:end].iterrows():
        st.subheader(row["title"])
        st.caption(f"{row['channel_name']} • {row['publish_date'].strftime('%Y-%m-%d')}")
        st.video(row["link"])
        col1, col2 = st.columns(2)
        with col1:
            if st.button("⬇️ Download", key=f"dl_{row['link']}"):
                with st.spinner("Downloading..."):
                    file_path, file_name = download_video(row["link"])
                    with open(file_path, "rb") as file:
                        with st.modal("💾 Enter DemoUp Movie ID"):
                            st.markdown("### Enter Movie ID")
                            movie_id = st.text_input("Enter numeric DemoUp Movie ID")
                            if movie_id and not movie_id.isnumeric():
                                st.error("Only numbers allowed.")
                            elif movie_id and st.button("Save ID"):
                                save_movie_id(movie_id)
                                st.success("✅ Saved.")
                                st.download_button("📥 Download Video", data=file, file_name=file_name, mime="video/mp4")
        with col2:
            if st.button("🚫 Not Relevant", key=f"nr_{row['link']}"):
                video_obj = {
                    "video_id": row["video_id"],
                    "title": row["title"],
                    "channel_name": row["channel_name"],
                    "publish_date": row["publish_date"].strftime('%Y-%m-%d'),
                    "link": row["link"]
                }
                move_to_not_relevant(video_obj)
                st.rerun()

    st.markdown(f"Page {page} of {total_pages}")

elif view == "🚫 Not Relevant":
    videos = load_not_relevant()
    if not videos:
        st.info("No not-relevant videos yet.")
    else:
        for video in videos:
            st.subheader(video["title"])
            st.caption(f"{video['channel_name']} • {video['publish_date']}")
            st.video(video["link"])
