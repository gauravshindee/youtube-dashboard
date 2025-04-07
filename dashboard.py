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
import subprocess
from oauth2client.service_account import ServiceAccountCredentials

from fetch_videos import fetch_all as fetch_videos_main

# --- Constants ---
GOOGLE_SHEET_ID = "1VULPPJEhAtgdZE3ocWeAXsUVZFL7iGGC5TdyrBgKjzY"
QUICKWATCH_SHEET = "quickwatch"
NOT_RELEVANT_SHEET = "not_relevant"
ALREADY_DOWNLOADED_SHEET = "already downloaded"

SERVICE_ACCOUNT_SECRET = json.loads(st.secrets["gcp_service_account"])
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
credentials = ServiceAccountCredentials.from_json_keyfile_dict(SERVICE_ACCOUNT_SECRET, scope)
gs_client = gspread.authorize(credentials)

# --- Sheet Helpers ---
def load_sheet(name):
    return gs_client.open_by_key(GOOGLE_SHEET_ID).worksheet(name)

def load_quickwatch():
    return load_sheet(QUICKWATCH_SHEET).get_all_records()

def load_not_relevant():
    try:
        return load_sheet(NOT_RELEVANT_SHEET).get_all_records()
    except gspread.exceptions.WorksheetNotFound:
        return []

def load_already_downloaded():
    try:
        return load_sheet(ALREADY_DOWNLOADED_SHEET).get_all_records()
    except gspread.exceptions.WorksheetNotFound:
        return []

def move_to_sheet(video, sheet_name):
    try:
        sh = gs_client.open_by_key(GOOGLE_SHEET_ID)
        try:
            target_sheet = sh.worksheet(sheet_name)
        except gspread.exceptions.WorksheetNotFound:
            target_sheet = sh.add_worksheet(title=sheet_name, rows="1000", cols="5")
            target_sheet.append_row(["video_id", "title", "channel_name", "publish_date", "link"])
        target_sheet.append_row([
            str(video.get("video_id", "")),
            video.get("title", ""),
            video.get("channel_name", ""),
            str(video.get("publish_date", "")),
            video.get("link", "")
        ])
    except Exception as e:
        st.error(f"❌ Failed to save to {sheet_name} tab: {e}")

def remove_from_quickwatch(video_id):
    try:
        sh = gs_client.open_by_key(GOOGLE_SHEET_ID)
        qsheet = sh.worksheet(QUICKWATCH_SHEET)
        all_rows = qsheet.get_all_records()
        updated_rows = [row for row in all_rows if row.get("video_id") != video_id]
        qsheet.clear()
        if updated_rows:
            qsheet.append_row(list(updated_rows[0].keys()))
            qsheet.append_rows([list(r.values()) for r in updated_rows])
        else:
            qsheet.append_row(["video_id", "title", "channel_name", "publish_date", "link"])
    except Exception as e:
        st.error(f"❌ Failed to remove from quickwatch: {e}")

# --- Download Setup ---
os.makedirs("downloads", exist_ok=True)

def download_video(video_url):
    try:
        result = subprocess.run(
            ["bash", "download.sh", video_url],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd="data"
        )
        downloaded_file = result.stdout.strip().splitlines()[-1]
        full_path = os.path.join("data", downloaded_file)

        if not os.path.exists(full_path):
            st.error("❌ Download failed. File was not created.")
            st.code(result.stderr)
            return None, None, None

        local_path = os.path.join("downloads", downloaded_file)
        os.rename(full_path, local_path)

        return local_path, downloaded_file, os.path.splitext(downloaded_file)[0]

    except Exception as e:
        st.error(f"❌ Exception during download: {e}")
        return None, None, None

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

# --- UI Config ---
st.set_page_config(page_title="YouTube Dashboard", layout="wide")
st.title("📺 YouTube Video Dashboard")

view = st.sidebar.radio("📂 Select View", ["⚡ QuickWatch", "🚫 Not Relevant", "📥 Already Downloaded", "📦 Archive (Official)", "📦 Archive (Third-Party)"])

# --- QuickWatch ---
if view == "⚡ QuickWatch":
    videos = load_quickwatch()
    df = pd.DataFrame(videos)
    df["publish_date"] = pd.to_datetime(df["publish_date"], errors="coerce")

    col1, col2, col3 = st.columns(3)
    with col1:
        q = st.text_input("🔍 Search title")
    with col2:
        ch = st.selectbox("🎞 Channel", ["All"] + sorted(df["channel_name"].dropna().unique()))
    with col3:
        min_date = df["publish_date"].min().date()
        max_date = df["publish_date"].max().date()
        try:
            start, end = st.date_input("📅 Date range", [min_date, max_date])
        except ValueError:
            st.warning("Please select complete date range.")
            st.stop()

    filtered = df.copy()
    if q:
        filtered = filtered[filtered["title"].str.contains(q, case=False, na=False)]
    if ch != "All":
        filtered = filtered[filtered["channel_name"] == ch]
    filtered = filtered[(filtered["publish_date"].dt.date >= start) & (filtered["publish_date"].dt.date <= end)]

    st.markdown(f"**🔎 {len(filtered)} results**")
    per_page = 20
    total_pages = max(1, (len(filtered) - 1) // per_page + 1)
    page = st.number_input("Page", 1, total_pages, 1, key="quickwatch_page")

    st.markdown(f"Page {page} of {total_pages}")
    for video in filtered.iloc[(page-1)*per_page:page*per_page].to_dict("records"):
        st.subheader(video["title"])
        st.caption(f"{video['channel_name']} • {video['publish_date']}")
        st.video(video["link"])

        col1, col2 = st.columns(2)
        with col1:
            if st.button("⬇️ Download", key=f"dl_{video['link']}"):
                with st.spinner("Downloading..."):
                    path, fname, vid = download_video(video["link"])
                    if path and fname and vid:
                        try:
                            with open(path, "rb") as f:
                                file_bytes = f.read()
                            move_to_sheet(video, ALREADY_DOWNLOADED_SHEET)
                            remove_from_quickwatch(video["video_id"])
                            st.success("✅ Downloaded and moved to Already Downloaded.")
                            st.download_button("📥 Download Video", data=file_bytes, file_name=fname, mime="video/mp4")
                        except Exception as e:
                            st.error(f"❌ Error during final steps: {e}")
        with col2:
            if st.button("🚫 Not Relevant", key=f"nr_{video['video_id']}"):
                move_to_sheet(video, NOT_RELEVANT_SHEET)
                remove_from_quickwatch(video["video_id"])
                st.rerun()

    st.markdown(f"Page {page} of {total_pages}")

# --- Not Relevant View ---
elif view == "🚫 Not Relevant":
    st.subheader("🚫 Not Relevant Videos")
    for video in load_not_relevant():
        st.subheader(video["title"])
        st.caption(f"{video['channel_name']} • {video['publish_date']}")
        st.video(video["link"])

# --- Already Downloaded View ---
elif view == "📥 Already Downloaded":
    st.subheader("📥 Already Downloaded Videos")
    for video in load_already_downloaded():
        st.subheader(video["title"])
        st.caption(f"{video['channel_name']} • {video['publish_date']}")
        st.video(video["link"])

# --- Archive Views ---
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
    col1, col2, col3 = st.columns(3)
    with col1:
        query = st.text_input("🔍 Search title", key=f"{label}_search")
    with col2:
        channel = st.selectbox("🎞 Channel", ["All"] + sorted(df["channel_name"].dropna().unique()), key=f"{label}_channel")
    with col3:
        min_date = df["publish_date"].min().date()
        max_date = df["publish_date"].max().date()
        try:
            start_date, end_date = st.date_input("📅 Date range", [min_date, max_date], key=f"{label}_date")
        except ValueError:
            st.warning("Please select full date range.")
            return

    filtered = df.copy()
    if query:
        filtered = filtered[filtered["title"].str.contains(query, case=False, na=False)]
    if channel != "All":
        filtered = filtered[filtered["channel_name"] == channel]
    filtered = filtered[(filtered["publish_date"].dt.date >= start_date) & (filtered["publish_date"].dt.date <= end_date)]

    st.markdown(f"**🔎 {len(filtered)} results found**")
    per_page = 10
    pages = max(1, (len(filtered) - 1) // per_page + 1)
    page = st.number_input("Page", 1, pages, 1, key=f"{label}_page")

    for _, row in filtered.iloc[(page-1)*per_page:page*per_page].iterrows():
        st.subheader(row["title"])
        st.caption(f"{row['channel_name']} • {row['publish_date'].strftime('%Y-%m-%d')}")
        st.video(row["video_link"])

elif view == "📦 Archive (Official)":
    archive_view("data/archive.csv", "Archive (Official)")

elif view == "📦 Archive (Third-Party)":
    archive_view("data/archive_third_party.csv", "Archive (Third-Party)")
