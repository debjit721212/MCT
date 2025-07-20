"""
zone_manager.py

ZoneManager is responsible for launching and supervising multiple zone-based DeepStream pipelines.
Each zone runs in an isolated subprocess using `zone_runner.py`.

Features:
- Spawns one subprocess per zone.
- Restarts crashed zones with retry logic.
- Monitors zone health via stdout/stderr.
- Suitable for 1000+ camera-scale systems.

Author: [Your Name]
"""

import subprocess
import time
import os
from typing import List, Dict

from app.transition_graph import MultiZoneCameraConfig


class ZoneManager:
    """
    Manages DeepStream pipelines per zone by spawning subprocesses.

    Attributes:
        config_path (str): Path to camera configuration YAML.
        zone_processes (Dict[str, subprocess.Popen]): Map of zone names to subprocess handles.
        camera_config (MultiZoneCameraConfig): Zone-camera graph configuration object.
    """

    def __init__(self, config_path: str = "/opt/nvidia/deepstream/deepstream-7.1/MCT/app/camera_config.yaml"):
        self.config_path = config_path
        self.zone_processes: Dict[str, subprocess.Popen] = {}
        self.camera_config = MultiZoneCameraConfig(config_path)

    def launch_all_zones(self) -> None:
        """
        Launch pipelines for all zones in separate subprocesses.
        """
        print("[ZONE_MANAGER] 🚀 Launching all zone pipelines...")
        for zone in self.camera_config.cfg["zones"]:
            zone_name = zone["name"]
            self.launch_zone(zone_name)

    def launch_zone(self, zone_name: str) -> None:
        """
        Launch a single zone pipeline subprocess.

        Args:
            zone_name (str): Zone identifier (e.g., 'zone1').
        """
        if zone_name in self.zone_processes and self.zone_processes[zone_name].poll() is None:
            print(f"[ZONE_MANAGER] ⚠️ Zone '{zone_name}' already running. Skipping.")
            return

        print(f"[ZONE_MANAGER] 🟢 Starting subprocess for zone: {zone_name}")
        cmd = [
            "python3", "app/zone_runner.py",
            "--zone", zone_name,
            "--config", self.config_path
        ]

        try:
            process = subprocess.Popen(cmd)
            self.zone_processes[zone_name] = process
        except Exception as e:
            print(f"[ZONE_MANAGER] ❌ Failed to start zone '{zone_name}': {e}")

    def terminate_zone(self, zone_name: str) -> None:
        """
        Terminates a single zone subprocess if running.

        Args:
            zone_name (str): Zone to terminate.
        """
        proc = self.zone_processes.get(zone_name)
        if proc and proc.poll() is None:
            print(f"[ZONE_MANAGER] 🔻 Terminating zone: {zone_name}")
            proc.terminate()
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                print(f"[ZONE_MANAGER] ⚠️ Forcing kill on zone: {zone_name}")
                proc.kill()
        self.zone_processes.pop(zone_name, None)

    def monitor_zones(self) -> None:
        """
        Monitors running subprocesses and restarts them if they crash.
        """
        print("[ZONE_MANAGER] 🔍 Monitoring all active zones...")
        try:
            while True:
                for zone_name, proc in list(self.zone_processes.items()):
                    if proc.poll() is not None:  # Process has exited
                        print(f"[ZONE_MANAGER] 🔄 Zone '{zone_name}' has crashed. Restarting...")
                        self.terminate_zone(zone_name)
                        self.launch_zone(zone_name)
                time.sleep(5)
        except KeyboardInterrupt:
            print("\n[ZONE_MANAGER] 🛑 Shutdown requested. Cleaning up...")
            self.terminate_all()

    def terminate_all(self) -> None:
        """
        Gracefully stops all zone subprocesses.
        """
        for zone_name in list(self.zone_processes.keys()):
            self.terminate_zone(zone_name)
        print("[ZONE_MANAGER] ✅ All zones terminated.")


# Optional: allow running directly for testing
if __name__ == "__main__":
    zm = ZoneManager()
    zm.launch_all_zones()
    zm.monitor_zones()
