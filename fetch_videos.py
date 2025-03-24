import os
import json
import requests
from datetime import datetime, timedelta
from datetime import timezone

# --- Config
YT_API_KEYS = [
    "AIzaSyC-t7UxIIq_DOpKDkwczPQdjF_t6jT-aWM",
    "AIzaSyBPaHfzgR5WjjFRsleNLy3jaEkeMKC5oCw",
    "AIzaSyAL7Yzo-Gs7Z0HDWupZQm-FyceR61957r8",
    "AIzaSyDABj0SyfncEo2Ivfzipa05QHntgS3ckXQ",
    "AIzaSyAt9mqKMTuP55dHak2ino1uQoetPA9Cw50",
    "AIzaSyB7kMF2ap66E3C-rruyW0RKgPNMzJkRESY",
    "AIzaSyA8bcHPm__m-0VrlzU1wt3x1pJ7-qN7GvU",
    "AIzaSyD1ldfQ0FABISwOg34TG7aLS1uSthKMgJI",
    "AIzaSyBND_zoE03KqJtZyIYeKV4Of3NfoUTUHPo",
    "AIzaSyDmj5VuzBeMbhEnMn19fekgm5CkRK4vRPU",
    "AIzaSyAiOIzFKIUWFTiwMhNrRcXE5M8zz6rwDuQ"
]

BRAND_CHANNELS = {
"Samsung UK": "UC9KAEEmWnKkiBeskVPDYCZA",
"Sony Philippines": "UCHd7ya8j4qw27zb2gOhg6dA",
 "Philco Brasil": "UCP2AYtTUq1vowl3MDm0B46Q",
"Reusch": "UCmSFup7i7EkqadgC_8w2I1g",
"LENOXX® Oficial": "UC1SE4aZDz95sTWDmUEY7-NQ",
"Cambridge Audio": "UClrzM8Vc1ecjoGxsFqHsMmQ",
"Mondial Eletrodomésticos": "UCrCG_0FjETX43_IMuuqaZDA",
"Solo Stove": "UCVztOJ7K9JaNTuhyHFsZz1w",
"Weber Grills": "UCEBG5mwkD55WseNJryLdDSw",
"Enders Germany": "UCNAD2vqPaqaTg9zojDmwpOA",
"Sunset BBQ": "UCbbO59yZVmMUHtqUWVY0UYw",
"Samsung Philippines": "UCMVrFdXvbLLPziDG2EClOBQ",
"TCL MEA": "UCp2xjQtNp-3yDo8ilEyf91Q",
"ZTE | nubia Perú": "UC-8rIgT-5mXZ4-H7Qxt0H8Q",
"Samsung South Africa": "UCNHPnm8RtlOecbQvNoBSxZw",
"vivo Colombia": "UCeq_EGGRAmS-Dy6WZdZkPSA",
"realme Malaysia": "UCGTzNXK7ll44XcJWBzs1efA",
"HOKA India": "UCJ3URGL2AD3gZ_HiCiQkQFA",
"Voigtländer": "UCYPLM7nlOAm9jyKBfCiS0iQ",
"foto fantazia": "UCn6XKbGxrsKjoO9AP8ZooYQ",
"Daitsu España": "UCsDfVq9RCx1XdNvSW-9oUvw",
"AEG Australia & New Zealand": "UCtR_ju_-uw-7jmzQrS-cTCQ",
"HMD": "UC8ZbLfj2ByWKkafT6N2hapw",
"LG USA Support": "UCp481MCNVXV3CfmmI_oUq8w",
"Sparkworld Ltd": "UC0wiUStlUYqAkjFAAg1WU4A",
"ECOVACS APAC": "UCNw6_DCBIQQEb1KejCu2BIQ",
"Benelli Bhaktapur": "UCdEYtvL3dCYCd5PF9A_biIw",
"ASUS Singapore": "UCYfADoql3w6SvodxP4b_SNQ",
"CASO Design": "UCxRDnn7gsDdW7NWQ5XGLmmg",
"FRITZ!Box": "UC0YAfafei2jsZ-aPQOCDZZg",
"Netflix Brasil": "UCc1l5mTmAv2GC_PXrBpqyKQ",
"Thonet & Vander": "UCHsoK9VqW8_X1_VGTEFWTbw",
"Braun India": "UCRpQxx4hUh7yyvr2Up1LHYQ",
"SIGMA UK": "UC6WsaehNvjlUTEYJsDj227w",
"ZHIYUN-TECH": "UCeeYm4DCcKiN6hmKBspX8Ig",
"TefalFrance": "UCBjBXQFWikARBT75dyupQ7w",
"Duracell Arabia": "UCuYQXd96FxjyUKvfxNyZKfg",
"VDS-Online": "UCQVqMobKn3iKjwsi_WXmFRA",
"ASUS ROG ES": "UCwgKaTf4XpP0sFOpM_-RHTQ",
"Google": "UCK8sQmJBp8GCxrOtXWBpyEA",
"Tubesca-Comabi": "UCiiudWOV9mAvU9c7VkV4kmA",
"Sudio": "UCWf5NCzMk7GI0XNNJ6tTS5w",
"Goecker since 1862": "UCe-Iya5cAIYOyEM_uKAWWIA",
"Wahlpro": "UCPBKHu3r9javZyytxn5M-yg",
"XIAOMI Israel": "UCGte2E8p7R8_XWqDxe8aVGQ",
"Blaupunkt Car Multimedia & Foldable E-Bikes": "UCYh9kKvLTy5Qyj7Nx8Qs3_A",
"NiloxOfficial": "UCrMlWG9bjqy19MvYYf1otmw",
"TCL Indonesia": "UCRsYMObeP7bM17y77Y9hctQ",
"Video ad upload channel for 297-293-3472": "UCYr04ZUh_Hjjrbhlp18qNrg",
"PlayStation Europe": "UCg_JwOXFtu3iEtbr4ttXm9g",
"JBL Professional": "UCMp9a9-_jAvxVj1caBHbSzw",
"Kärcher México": "UC5KNyIKw94Whb9XvhJpAs-A",
"Sony Philippines": "UCHd7ya8j4qw27zb2gOhg6dA",
"2TTOYS: LEGO, PLAYMOBIL & COBI": "UCuvXd5X-18szDPlV0APoSGQ"
}

OUTPUT_FILE = "data/quickwatch.json"

# --- Helpers
def load_existing_videos():
    if not os.path.exists(OUTPUT_FILE):
        return []
    with open(OUTPUT_FILE, "r") as f:
        return json.load(f)

def save_videos(data):
    with open(OUTPUT_FILE, "w") as f:
        json.dump(data, f, indent=2)

def get_recent_uploads(channel_id, api_key):
    base_url = "https://www.googleapis.com/youtube/v3/search"
    published_after = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat("T")

    params = {
        "key": api_key,
        "channelId": channel_id,
        "part": "snippet",
        "order": "date",
        "maxResults": 10,
        "publishedAfter": published_after,
        "type": "video"
    }

    res = requests.get(base_url, params=params)
    if res.status_code != 200:
        return []

    items = res.json().get("items", [])
    return [{
        "video_id": item["id"]["videoId"],
        "title": item["snippet"]["title"],
        "channel_name": item["snippet"]["channelTitle"],
        "publish_date": item["snippet"]["publishedAt"].split("T")[0],
        "link": f"https://www.youtube.com/watch?v={item['id']['videoId']}"
    } for item in items]

# --- Main fetcher
def fetch_all():
    existing = load_existing_videos()
    existing_ids = {v["video_id"] for v in existing}

    api_index = 0
    new_videos = []

    for brand, channel_id in BRAND_CHANNELS.items():
        api_key = YT_API_KEYS[api_index % len(YT_API_KEYS)]
        api_index += 1

        try:
            recent = get_recent_uploads(channel_id, api_key)
            for vid in recent:
                if vid["video_id"] not in existing_ids:
                    new_videos.append(vid)
                    existing_ids.add(vid["video_id"])
        except Exception as e:
            print(f"Error fetching from {brand}: {e}")

    combined = existing + new_videos
    save_videos(combined)
    print(f"✅ Fetched {len(new_videos)} new videos. Total: {len(combined)}")

if __name__ == "__main__":
    fetch_all()
