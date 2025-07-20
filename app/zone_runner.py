"""
zone_runner.py

Entrypoint for launching a single zone-level DeepStream pipeline.

This script:
- Loads camera configuration for the specified zone.
- Initializes the DeepStream GStreamer pipeline via ZonePipeline.
- Runs the main GStreamer event loop.

Author: Debjit (Modified by Venkatesh & ChatGPT)
"""

import argparse
import gi
import sys
import signal

gi.require_version('Gst', '1.0')
from gi.repository import GObject, Gst
from gi.repository import GLib, Gst

from app.transition_graph import MultiZoneCameraConfig
from app.zone_pipeline import ZonePipeline
# from app.global_id_manager import GlobalIDManager
from global_id_service.qdrant_backend.id_manager import GlobalIDManager

# Initialize GStreamer
Gst.init(None)
GObject.threads_init()

def parse_args():
    """Parses CLI arguments for zone runner."""
    parser = argparse.ArgumentParser(description="Run DeepStream pipeline for a single zone.")
    parser.add_argument('--zone', type=str, required=True, help='Zone name to run (e.g., zone1)')
    parser.add_argument('--config', type=str, default='app/camera_config.yaml',
                        help='Path to camera config YAML')
    return parser.parse_args()

def main():
    args = parse_args()

    # Load config and validate zone
    config = MultiZoneCameraConfig(args.config)
    zone_cameras = [cam for cam in config.camera_uri_map if config.get_zone_of_camera(cam) == args.zone]

    if not zone_cameras:
        print(f"[ERROR] Zone '{args.zone}' not found or contains no cameras.", file=sys.stderr)
        sys.exit(1)

    print(f"[INFO] Launching zone pipeline for: {args.zone}")
    print(f"[INFO] Cameras in zone: {zone_cameras}")

    # Step 1: Initialize GlobalIDManager
    global_id_manager = GlobalIDManager()
    zone_name = args.zone
    fps_log_path = f"/opt/nvidia/deepstream/deepstream-7.1/MCT/logs/fps_{zone_name}.log"

     # Step 2: Initialize pipeline
    pipeline = ZonePipeline(
        zone_name=zone_name,
        camera_ids=zone_cameras,
        config=config,
        global_id_manager=global_id_manager,
        fps_log_path=fps_log_path
        
    )

    # Step 3: Run GObject loop
    loop = GLib.MainLoop()#GObject.MainLoop()

    def shutdown(sig, frame):
        print(f"\n[INFO] Shutting down zone: {args.zone}")
        pipeline.stop()
        loop.quit()

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    try:
        pipeline.start()  # <-- Only this now
        loop.run()
    except Exception as e:
        print(f"[ERROR] Exception in zone pipeline: {e}", file=sys.stderr)
        pipeline.stop()
        sys.exit(1)

if __name__ == '__main__':
    main()
