"""
api_server.py

FastAPI backend for real-time and historical analytics dashboard.
Provides FPS stats, camera health, zone transitions, and track summaries.

Author: [Your Name]
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from typing import Dict, List, Any
import uvicorn
import os
import json
from datetime import datetime
from collections import defaultdict
from global_id_service.cache_instance import redis_cache

app = FastAPI(title="MCT Dashboard API", version="1.0")

# === CORS Middleware ===
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# === Helper ===
def parse_fps_log(log_path: str) -> Dict[str, List[Dict[str, Any]]]:
    if not os.path.exists(log_path):
        raise FileNotFoundError(f"Log file not found: {log_path}")

    camera_fps = defaultdict(list)
    with open(log_path, 'r') as f:
        for line in f:
            if '**PERF:' in line and '{' in line:
                try:
                    json_start = line.index('{')
                    payload = eval(line[json_start:])
                    time_str = payload.get("Time")
                    timestamp = datetime.strptime(time_str, "%Y-%m-%d %H:%M:%S").timestamp()
                    for cam, fps in payload.items():
                        if cam != "Time":
                            camera_fps[cam].append({"time": timestamp, "fps": fps})
                except Exception:
                    continue
    return camera_fps

# === API Endpoints ===
@app.get("/api/ping")
def ping():
    return {"msg": "pong"}

@app.get("/api/cameras")
def get_cameras():
    try:
        logs_dir = "/opt/nvidia/deepstream/deepstream-7.1/MCT/logs"
        fps_files = [f for f in os.listdir(logs_dir) if f.startswith("fps_") and f.endswith(".log")]
        all_cams = set()
        for log_file in fps_files:
            full_path = os.path.join(logs_dir, log_file)
            fps_data = parse_fps_log(full_path)
            all_cams.update(fps_data.keys())
        return list(all_cams)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/fps/{camera_id}")
def get_camera_fps(camera_id: str):
    try:
        from app.transition_graph import MultiZoneCameraConfig
        config = MultiZoneCameraConfig("app/camera_config.yaml")
        zone = config.get_zone_of_camera(camera_id)
        if not zone:
            raise HTTPException(status_code=404, detail=f"Camera '{camera_id}' not assigned to any zone")

        fps_log_path = f"/opt/nvidia/deepstream/deepstream-7.1/MCT/logs/fps_{zone}.log"
        if not os.path.exists(fps_log_path):
            raise HTTPException(status_code=404, detail=f"FPS log for zone '{zone}' not found")

        fps_data = parse_fps_log(fps_log_path)
        if camera_id not in fps_data:
            raise HTTPException(status_code=404, detail=f"No FPS data for camera '{camera_id}' in zone '{zone}'")

        return fps_data[camera_id]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/health")
def get_system_health():
    return {"status": "OK", "timestamp": datetime.now().isoformat()}

@app.get("/api/tracking/summary")
def get_tracking_summary():
    r = redis_cache.redis
    keys = r.keys("stream*")
    total = len(keys)
    per_cam_active = defaultdict(int)
    for key in keys:
        cam = key.split(":")[0]
        per_cam_active[cam] += 1

    global_keys = r.keys("global_id:*")
    per_cam_global_ids = defaultdict(int)
    for key in global_keys:
        try:
            val = r.get(key)
            data = json.loads(val) if isinstance(val, str) else val
            cam = data.get("camera_id")
            if cam:
                per_cam_global_ids[cam] += 1
        except Exception:
            continue

    return {
        "total_tracks": total,
        "per_camera": dict(per_cam_active),
        "global_ids": dict(per_cam_global_ids)
    }

@app.get("/api/zone_transitions")
def get_zone_transitions():
    return {"transitions": []}

@app.get("/api/health/cameras")
def get_camera_health():
    try:
        logs_dir = "/opt/nvidia/deepstream/deepstream-7.1/MCT/logs"
        fps_files = [f for f in os.listdir(logs_dir) if f.startswith("fps_") and f.endswith(".log")]
        now = datetime.now().timestamp()
        health = {}

        for log_file in fps_files:
            full_path = os.path.join(logs_dir, log_file)
            fps_data = parse_fps_log(full_path)
            for cam, logs in fps_data.items():
                try:
                    last_entry = logs[-1]
                    last_time = last_entry["time"]
                    last_fps = last_entry["fps"]
                    if last_fps == 0.0:
                        health[cam] = "DEAD"
                    else:
                        health[cam] = "LIVE"
                except Exception as e:
                    print(f"[ERROR] Health check failed for {cam}: {e}")
                    health[cam] = "DEAD"
        return health
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/zones")
def get_zones():
    from app.transition_graph import MultiZoneCameraConfig
    camera_config = MultiZoneCameraConfig("app/camera_config.yaml")
    zone_map = {}
    for cam_id in camera_config.camera_uri_map:
        zone = camera_config.get_zone_of_camera(cam_id)
        zone_map.setdefault(zone, []).append(cam_id)
    return zone_map

@app.get("/api/global_ids")
def get_active_global_ids():
    try:
        r = redis_cache.redis
        keys = r.keys("global_id:*")
        global_ids = []
        for key in keys:
            value = r.get(key)
            if not value:
                continue
            try:
                data = json.loads(value)
                global_ids.append({
                    "global_id": data.get("global_id", "unknown"),
                    "camera_id": data.get("camera_id", "unknown"),
                    "track_id": data.get("track_id", "unknown"),
                    "zone": data.get("zone", "unknown"),
                    "timestamp": data.get("timestamp", 0),
                    "raw": data
                })
            except Exception:
                parts = key.split(":")
                global_ids.append({
                    "global_id": parts[-1],
                    "camera_id": parts[1] if len(parts) > 2 else "unknown",
                    "track_id": parts[2] if len(parts) > 2 else "unknown",
                    "zone": "unknown",
                    "timestamp": 0,
                    "raw": value
                })
        global_ids.sort(key=lambda x: x["timestamp"], reverse=True)
        return {"count": len(global_ids), "items": global_ids}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/track_ids/{global_id}")
def get_track_ids(global_id: int):
    track_ids = redis_cache.get_all_track_ids(global_id)
    return {"global_id": global_id, "track_ids": track_ids}

# === Entry Point ===
if __name__ == "__main__":
    uvicorn.run("dashboard.api_server:app", host="0.0.0.0", port=8088, reload=True)
