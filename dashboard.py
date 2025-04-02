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

SERVICE_ACCOUNT_SECRET = json.loads(st.secrets["gcp_service_account"])
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
credentials = ServiceAccountCredentials.from_json_keyfile_dict(SERVICE_ACCOUNT_SECRET, scope)
gs_client = gspread.authorize(credentials)

# --- Download Archives ---
RAW_ZIP_URL_OFFICIAL = "https://raw.githubusercontent.com/gauravshindee/youtube-dashboard/main/data/archive.csv.zip"
RAW_ZIP_URL_THIRD_PARTY = "https://raw.githubusercontent.com/gauravshindee/youtube-dashboard/main/data/archive_third_party.csv.zip"

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

# --- Google Sheets Functions ---
def load_sheet(sheet_name):
    return gs_client.open_by_key(GOOGLE_SHEET_ID).worksheet(sheet_name)

def load_quickwatch():
    return load_sheet(QUICKWATCH_SHEET).get_all_records()

def load_not_relevant():
    try:
        return load_sheet(NOT_RELEVANT_SHEET).get_all_records()
    except gspread.exceptions.WorksheetNotFound:
        return []

def save_movie_id(movie_id):
    sh = gs_client.open_by_key(GOOGLE_SHEET_ID)
    try:
        sheet = sh.worksheet(MOVIE_ID_SHEET)
    except gspread.exceptions.WorksheetNotFound:
        sheet = sh.add_worksheet(title=MOVIE_ID_SHEET, rows="1000", cols="1")
        sheet.update("A1", [["movie_id"]])
    sheet.append_row([movie_id])

def move_to_not_relevant(video):
    try:
        sh = gs_client.open_by_key(GOOGLE_SHEET_ID)
        qsheet = sh.worksheet(QUICKWATCH_SHEET)
        nsheet = None
        try:
            nsheet = sh.worksheet(NOT_RELEVANT_SHEET)
        except gspread.exceptions.WorksheetNotFound:
            nsheet = sh.add_worksheet(title=NOT_RELEVANT_SHEET, rows="1000", cols="5")
            nsheet.update("A1:E1", [["video_id", "title", "channel_name", "publish_date", "link"]])

        rows = qsheet.get_all_records()
        updated_rows = []
        removed_video = None

        for row in rows:
            if row.get("video_id") == video["video_id"]:
                removed_video = row
            else:
                updated_rows.append(row)

        if removed_video:
            # Ensure all values are strings for serialization safety
            cleaned = [str(removed_video.get(col, "")) for col in ["video_id", "title", "channel_name", "publish_date", "link"]]
            nsheet.append_row(cleaned)

        if updated_rows:
            qsheet.clear()
            qsheet.append_row(list(updated_rows[0].keys()))
            qsheet.append_rows([list(row.values()) for row in updated_rows])
        else:
            qsheet.clear()
            qsheet.append_row(["video_id", "title", "channel_name", "publish_date", "link"])
    except Exception as e:
        st.error(f"Failed to move to Not Relevant: {e}")

# --- Video Download ---
os.makedirs("downloads", exist_ok=True)

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

# --- Archive View ---
def archive_view(csv_path, label):
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
        selected_channel = st.selectbox("🎞 Channel", ["All"] + sorted(df["channel_name"].dropna().unique()), key=f"{label}_channel")
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
    total_pages = max(1, (len(filtered) - 1) // per_page + 1)
    page = st.number_input("Page", 1, total_pages, 1, key=f"{label}_page")

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

# --- Sidebar Navigation ---
view = st.sidebar.radio("📂 Select View", ["⚡ QuickWatch", "🚫 Not Relevant", "📦 Archive (Official)", "📦 Archive (Third-Party)"])

# --- QuickWatch View ---
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

    # --- Filters ---
    col1, col2, col3 = st.columns(3)
    with col1:
        search_query = st.text_input("🔍 Search title")
    with col2:
        selected_channel = st.selectbox("🎞 Channel", ["All"] + sorted(df["channel_name"].dropna().unique()))
    with col3:
        min_date = df["publish_date"].min().date()
        max_date = df["publish_date"].max().date()
        start_date, end_date = st.date_input("📅 Date range", [min_date, max_date])

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

    st.markdown(f"Page {page} of {total_pages}", help="Navigate pages")
    start = (page - 1) * per_page
    end = start + per_page
    page_videos = filtered.iloc[start:end].to_dict("records")

    for video in page_videos:
        st.subheader(video["title"])
        st.caption(f"{video['channel_name']} • {video['publish_date']}")
        st.video(video["link"])

        col1, col2 = st.columns(2)
        with col1:
            if st.button("⬇️ Download", key=f"dl_{video['link']}"):
                with st.spinner("Downloading..."):
                    path, fname = download_video(video["link"])
                    with open(path, "rb") as file:
                        with st.modal("💾 Enter DemoUp Movie ID", key=f"modal_{video['link']}"):
                            st.markdown("### 💾 Save Movie ID")
                            movie_id = st.text_input("Enter numeric DemoUp Movie ID", key=f"id_{video['link']}")
                            if movie_id and not movie_id.isnumeric():
                                st.error("Only numbers allowed.")
                            elif movie_id and st.button("Save ID", key=f"save_{video['link']}"):
                                save_movie_id(movie_id)
                                st.success("Saved.")
                                st.download_button("📥 Download", data=file, file_name=fname, mime="video/mp4")
        with col2:
            if st.button("🚫 Not Relevant", key=f"nr_{video['link']}"):
                move_to_not_relevant(video)
                st.rerun()

    st.markdown(f"Page {page} of {total_pages}", help="Navigate pages")

# --- Not Relevant View ---
elif view == "🚫 Not Relevant":
    st.subheader("🚫 Not Relevant Videos")
    videos = load_not_relevant()
    for video in videos:
        st.subheader(video["title"])
        st.caption(f"{video['channel_name']} • {video['publish_date']}")
        st.video(video["link"])

elif view == "📦 Archive (Official)":
    archive_view("data/archive.csv", label="Archive (Official)")

elif view == "📦 Archive (Third-Party)":
    archive_view("data/archive_third_party.csv", label="Archive (Third-Party)")
