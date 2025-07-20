import time
import json
import os
from threading import Lock
from datetime import datetime


class GETFPS:
    def __init__(self, stream_id: str):
        self.stream_id = stream_id
        self.start_time = time.time()
        self.frame_count = 0
        self.is_first = True
        self.lock = Lock()

    def update_fps(self):
        now = time.time()
        with self.lock:
            if self.is_first:
                self.start_time = now
                self.is_first = False
            else:
                self.frame_count += 1

    def get_fps(self) -> float:
        now = time.time()
        with self.lock:
            elapsed = now - self.start_time
            if elapsed == 0:
                return 0.0
            fps = self.frame_count / elapsed
            self.frame_count = 0
            self.start_time = now
        return round(fps, 2)

    def print_data(self):
        print(f"[DEBUG] Stream {self.stream_id} → frame_count: {self.frame_count}, start_time: {self.start_time}")


class PERF_DATA:
    def __init__(self, num_streams=1, log_path=None, stream_names=None):
        self.log_path = log_path
        self.lock = Lock()
        self.perf_dict = {}
        self.all_stream_fps = {}
        # 💥 Remove old log file if exists
        if self.log_path and os.path.exists(self.log_path):
            os.remove(self.log_path)

        # Allow custom stream names like ['camA', 'camB']
        if stream_names:
            for name in stream_names:
                self.all_stream_fps[name] = GETFPS(name)
        else:
            for i in range(num_streams):
                name = f"stream{i}"
                self.all_stream_fps[name] = GETFPS(name)

    def update_fps(self, stream_name: str):
        if stream_name not in self.all_stream_fps:
            # Auto-register missing streams
            with self.lock:
                self.all_stream_fps[stream_name] = GETFPS(stream_name)
                print(f"[WARN] Stream '{stream_name}' not initialized. Auto-registering.")
        self.all_stream_fps[stream_name].update_fps()

    def perf_print_callback(self):
        with self.lock:
            self.perf_dict = {
                name: stream.get_fps()
                for name, stream in self.all_stream_fps.items()
            }

        log_line = {
            "Time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            **self.perf_dict
        }

        print("**PERF:", log_line)

        if self.log_path:
            try:
                os.makedirs(os.path.dirname(self.log_path), exist_ok=True)
                with open(self.log_path, "a") as f:
                    f.write(f"**PERF: {json.dumps(log_line)}\n")
            except Exception as e:
                print(f"[ERROR] Failed to write FPS log: {e}")

        return True  # Needed by GLib.timeout_add

