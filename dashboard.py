import streamlit as st
import requests
import pandas as pd
import plotly.express as px
import json
from streamlit_autorefresh import st_autorefresh

# 🔁 Auto-refresh every 5 seconds (5000 ms)
st_autorefresh(interval=5000, limit=None, key="dashboard_refresh")

API_URL = "http://localhost:8088/api"

st.set_page_config(layout="wide")
st.title("📡 Multi-Camera Tracking Dashboard")

# === Fetch all cameras grouped by zone
zone_cam_response = requests.get(f"{API_URL}/zones")
if zone_cam_response.status_code != 200:
    st.error("Failed to fetch zone-camera mapping.")
    st.stop()

zone_camera_map = zone_cam_response.json()
zones = list(zone_camera_map.keys())

# === Select Zone
selected_zone = st.selectbox("📍 Select Zone", zones)

# === Select Camera within that Zone
selected_cam = st.selectbox("🎥 Select Camera", zone_camera_map[selected_zone])

# === FPS Chart ===
fps_response = requests.get(f"{API_URL}/fps/{selected_cam}")
if fps_response.status_code == 200:
    fps_data = fps_response.json()
    df = pd.DataFrame(fps_data)
    fig = px.line(df, x="time", y="fps", title=f"FPS Over Time - {selected_cam}")
    st.plotly_chart(fig, use_container_width=True)
else:
    st.warning("No FPS data available for this camera.")

# === Camera Health ===
cam_health_response = requests.get(f"{API_URL}/health/cameras")
if cam_health_response.status_code == 200:
    cam_health = cam_health_response.json()
    st.subheader("📶 Camera Health Status")
    health_df = pd.DataFrame(list(cam_health.items()), columns=["Camera", "Status"])
    health_df["🟢 Status"] = health_df["Status"].apply(lambda x: "🟢 LIVE" if x == "LIVE" else "🔴 DEAD")
    st.dataframe(health_df[["Camera", "🟢 Status"]])
else:
    st.error("Could not fetch camera health status.")

# === System Health Ping ===
health = requests.get(f"{API_URL}/health").json()
st.caption(f"**System Status**: `{health['status']}`  |  ⏱️ Last Ping: `{health['timestamp']}`")

# === Active Global IDs ===
st.subheader("🧬 Active Global IDs")
global_id_response = requests.get(f"{API_URL}/global_ids")

if global_id_response.status_code == 200:
    gid_data = global_id_response.json()
    gid_items = gid_data.get("items", [])

    if not gid_items:
        st.info("No active global IDs.")
    else:
        df_gid = pd.DataFrame(gid_items)

        # Convert raw field to dict if it's a JSON string
        df_gid["raw"] = df_gid["raw"].apply(
            lambda r: json.loads(r) if isinstance(r, str) and r.strip().startswith("{") else r
        )

        # Extract fields
        def extract_field(row, key):
            raw = row["raw"]
            if isinstance(raw, dict):
                return raw.get(key)
            return None

        df_gid["track_id"] = df_gid.apply(lambda row: extract_field(row, "track_id"), axis=1)
        df_gid["zone"] = df_gid.apply(lambda row: extract_field(row, "zone"), axis=1)
        df_gid["timestamp"] = df_gid.apply(lambda row: extract_field(row, "timestamp"), axis=1)
        df_gid["timestamp"] = pd.to_datetime(df_gid["timestamp"], unit="s", errors="coerce")

        # Filters
        cameras = df_gid["camera_id"].dropna().unique().tolist()
        selected_gid_cams = st.multiselect("🎥 Filter by Camera", cameras, default=cameras)

        df_gid_filtered = df_gid[df_gid["camera_id"].isin(selected_gid_cams)]

        st.dataframe(
            df_gid_filtered[["global_id", "camera_id", "track_id", "zone", "timestamp"]]
            .sort_values("timestamp", ascending=False),
            use_container_width=True,
            height=500
        )

        # ✅ NEW: Show track ID history for selected Global ID
        st.markdown("---")
        st.subheader("🧾 Global ID → Track ID History")
        selected_global_id = st.selectbox("Select a Global ID to view its track history", df_gid_filtered["global_id"].unique())

        history_resp = requests.get(f"{API_URL}/track_ids/{selected_global_id}")
        if history_resp.status_code == 200:
            history_data = history_resp.json()
            st.code("\n".join(history_data.get("track_ids", [])), language="text")
        else:
            st.error("Failed to load track ID history.")
else:
    st.error("Failed to fetch active global ID data.")
