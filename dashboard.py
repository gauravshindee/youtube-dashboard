# dashboard.py
import streamlit as st
import json
import os
import subprocess
import pandas as pd
import yt_dlp
import time

# --- Secure Login Setup ---
CORRECT_PASSWORD = "DemoUp2025!"
LOGIN_TIMEOUT = 4 * 60 * 60  # 4 hours

def authenticate():
    st.set_page_config(page_title="🔐 Login", layout="centered")
    st.title("🔐 DemoUp Dashboard")
    password = st.text_input("Enter password to continue", type="password")
    if password == CORRECT_PASSWORD:
        st.session_state["authenticated"] = True
        st.session_state["login_time"] = time.time()
        st.success("Access granted. Loading...")
        st.rerun()
    elif password:
        st.error("❌ Incorrect password.")

auth_time = st.session_state.get("login_time", 0)
if "authenticated" not in st.session_state or not st.session_state["authenticated"] or (time.time() - auth_time > LOGIN_TIMEOUT):
    st.session_state["authenticated"] = False
    authenticate()
    st.stop()

# --- Setup Directories ---
os.makedirs("data", exist_ok=True)
os.makedirs("downloads", exist_ok=True)

# --- File Paths ---
DATA_FILE = "data/quickwatch.json"
NOT_RELEVANT_FILE = "data/not_relevant.json"
ARCHIVE_FILE = "data/archive.csv"
ARCHIVE_THIRD_PARTY_FILE = "data/archive_third_party.csv"

# --- Loaders ---
def load_videos():
    if not os.path.exists(DATA_FILE): return []
    with open(DATA_FILE, "r") as f: return json.load(f)

def load_not_relevant():
    if not os.path.exists(NOT_RELEVANT_FILE): return []
    with open(NOT_RELEVANT_FILE, "r") as f: return json.load(f)

def save_not_relevant(data):
    with open(NOT_RELEVANT_FILE, "w") as f: json.dump(data, f, indent=2)

# --- Download via yt-dlp ---
def download_video(video_url):
    ydl_opts = {
        "format": "best[ext=mp4]/best",
        "outtmpl": "downloads/%(id)s.%(ext)s",
        "quiet": True,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(video_url, download=True)
        video_id = info.get("id")
        ext = info.get("ext")
        file_path = f"downloads/{video_id}.{ext}"
        return file_path, f"{video_id}.{ext}"

# --- Archive Viewer ---
def archive_view(csv_path, label):
    if not os.path.exists(csv_path):
        st.warning(f"{label} CSV not found.")
        return

    try:
        df = pd.read_csv(csv_path, encoding="utf-8", encoding_errors="replace", on_bad_lines="skip")
    except Exception as e:
        st.error(f"Error reading {label} file: {e}")
        return

    df.columns = df.columns.str.strip().str.lower()
    st.subheader(f"📦 {label}")
    st.markdown("### Filters")

    # Filters
    col1, col2, col3 = st.columns(3)
    with col1:
        search_query = st.text_input("🔍 Title search", key=f"{label}_search")
    with col2:
        channels = df["channel_name"].dropna().unique().tolist()
        selected_channel = st.selectbox("🎞 Channel filter", ["All"] + sorted(channels), key=f"{label}_channel")
    with col3:
        df["publish_date"] = pd.to_datetime(df["publish_date"], errors="coerce")
        min_d = df["publish_date"].min().date()
        max_d = df["publish_date"].max().date()
        start_d, end_d = st.date_input("📅 Date range", [min_d, max_d], key=f"{label}_date")

    # Apply filters
    filtered = df.copy()
    if search_query:
        filtered = filtered[filtered["title"].str.contains(search_query, case=False, na=False)]
    if selected_channel != "All":
        filtered = filtered[filtered["channel_name"] == selected_channel]
    filtered = filtered[
        (filtered["publish_date"].dt.date >= start_d) &
        (filtered["publish_date"].dt.date <= end_d)
    ]

    st.markdown(f"**🔎 {len(filtered)} results found**")
    st.markdown("---")

    # Pagination
    per_page = 10
    total_pages = max(1, (len(filtered) - 1) // per_page + 1)
    page = st.number_input("Page", min_value=1, max_value=total_pages, value=1, key=f"{label}_page")
    paginated = filtered.iloc[(page-1)*per_page : page*per_page]

    for _, row in paginated.iterrows():
        st.subheader(row["title"])
        st.caption(f"{row['channel_name']} • {row['publish_date'].strftime('%Y-%m-%d')}")
        st.video(row["video_link"])
        st.button("⬇️ Download", key=f"dl_{row['video_link']}_{label}")

# --- UI Layout ---
st.set_page_config(page_title="YT Dashboard", layout="wide")
st.title("📺 YouTube Video Dashboard")

# Sidebar options
view = st.sidebar.radio("📂 Select View", [
    "⚡ QuickWatch",
    "🚫 Not Relevant",
    "📦 Archive (Official)",
    "📦 Archive (Third-Party)"
])

# Upload CSV
st.sidebar.markdown("### 📁 Upload Archive CSV")
upload_type = st.sidebar.selectbox("Select upload target", ["Archive (Official)", "Archive (Third-Party)"])
uploaded_file = st.sidebar.file_uploader("Upload CSV file", type="csv")
if uploaded_file:
    target_path = ARCHIVE_FILE if upload_type == "Archive (Official)" else ARCHIVE_THIRD_PARTY_FILE
    with open(target_path, "wb") as f:
        f.write(uploaded_file.read())
    st.sidebar.success(f"{upload_type} CSV uploaded and saved!")

# --- View Renderers ---
if view == "⚡ QuickWatch":
    with st.expander("📡 Manual Fetch (Admin Only)"):
        password = st.text_input("Enter admin password", type="password")
        if password == "demoup123":
            if st.button("🔁 Fetch New Videos Now"):
                with st.spinner("Fetching videos..."):
                    result = subprocess.run(["python3", "fetch_videos.py"], capture_output=True, text=True)
                if result.returncode == 0:
                    st.success("✅ Fetch completed.")
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
        if video["link"] in [v["link"] for v in not_relevant]:
            continue
        st.subheader(video["title"])
        st.caption(f"{video['channel_name']} • {video['publish_date']}")
        st.video(video["link"])

        col1, col2 = st.columns(2)
        with col1:
            if st.button("⬇️ Download", key=f"dl_{video['link']}"):
                with st.spinner("Downloading..."):
                    file_path, file_name = download_video(video["link"])
                    with open(file_path, "rb") as f:
                        st.download_button("📥 Save to device", f, file_name, mime="video/mp4")

        with col2:
            if st.button("🚫 Not Relevant", key=f"nr_{video['link']}"):
                not_relevant.append(video)
                save_not_relevant(not_relevant)
                st.rerun()

elif view == "🚫 Not Relevant":
    videos = load_not_relevant()
    if not videos:
        st.info("No videos marked as not relevant.")
    else:
        for video in videos:
            st.subheader(video["title"])
            st.caption(f"{video['channel_name']} • {video['publish_date']}")
            st.video(video["link"])

elif view == "📦 Archive (Official)":
    archive_view(ARCHIVE_FILE, "Archive (Official)")

elif view == "📦 Archive (Third-Party)":
    archive_view(ARCHIVE_THIRD_PARTY_FILE, "Archive (Third-Party)")
