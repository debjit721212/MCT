# project_root/
# ├── app/
# │   ├── deepstream_app.py             # Entry point for DeepStream MCT pipeline
# │   ├── global_id_manager.py          # Logic for assigning global IDs using embeddings
# │   ├── reid_inference.py             # ReID ONNX inference and cosine similarity matcher
# │   ├── camera_config.yaml            # List of camera streams, zones, transitions, weights
# │   ├── transition_graph.py           # Handles multi-zone transitions, reverse mapping, weights
# │   ├── metadata_parser.py            # Extracts bbox, track_id, embeddings, stream_id
# │   └── utils.py                      # Helper functions
# ├── models/
# │   ├── detector.trt                  # TensorRT optimized detector (e.g., YOLOv8)
# │   └── reid_model.onnx               # ReID model (OSNet / FastReID)
# ├── config/
# │   ├── config_tracker.txt
# │   ├── config_infer_primary.txt
# │   └── config_infer_reid.txt
# ├── dashboard/
# │   ├── main_dashboard.py             # Streamlit or Flask UI
# │   └── api_server.py                 # REST API to expose global ID stats
# ├── data/
# │   ├── global_tracks.db              # SQLite or PostgreSQL DB
# │   └── logs/                         # Runtime logs and tracking info
# ├── docker-compose.yml                # For microservice orchestration (Kafka, Redis, DB, UI)
# ├── requirements.txt                  # Python dependencies
# └── README.md

# ---- Enhanced camera_config.yaml ----
# zones:
#   - name: zone1
#     cameras:
#       - id: camA
#         uri: rtsp://192.168.1.10:554/stream
#       - id: camB
#         uri: rtsp://192.168.1.11:554/stream
#     transitions:
#       - [camA, camB, 0.9]   # camA → camB with 90% likelihood
#       - [camB, camA, 0.1]   # reverse
#   - name: zone2
#     cameras:
#       - id: camC
#         uri: rtsp://192.168.1.12:554/stream
#     transitions:
#       - [camB, camC, 1.0]

# ---- Enhanced transition_graph.py ----
import random
import yaml
from collections import defaultdict

class MultiZoneCameraConfig:
    """
    Parses a multi-zone camera configuration YAML.
    Supports:
    - zone-wise camera grouping
    - weighted directional transitions
    - reverse transition auto-fill
    - camera-to-zone mapping
    - sampling next camera based on transition weights
    """
    def __init__(self, config_path='/opt/nvidia/deepstream/deepstream-7.1/MCT/app/camera_config.yaml'):
        with open(config_path, 'r') as f:
            self.cfg = yaml.safe_load(f)
        self.camera_uri_map = {}
        self.camera_zone_map = {}
        self.transitions = defaultdict(list)
        self._parse_config()
        self._build_reverse_transitions()  # Optional reverse logic

    def _parse_config(self):
        for zone in self.cfg['zones']:
            for cam in zone['cameras']:
                self.camera_uri_map[cam['id']] = cam['uri']
                self.camera_zone_map[cam['id']] = zone['name']
            for transition in zone.get('transitions', []):
                src, dst, weight = transition
                self.transitions[src].append({'to': dst, 'weight': weight})

    def _build_reverse_transitions(self):
        for src, dst_list in list(self.transitions.items()):
            for entry in dst_list:
                dst = entry['to']
                weight = entry['weight']
                reverse_exists = any(t['to'] == src for t in self.transitions[dst])
                if not reverse_exists:
                    self.transitions[dst].append({'to': src, 'weight': round(1 - weight, 2)})

    def get_camera_uri(self, cam_id):
        return self.camera_uri_map.get(cam_id)

    def get_possible_transitions(self, cam_id):
        return self.transitions.get(cam_id, [])

    def get_all_cameras(self):
        return list(self.camera_uri_map.keys())

    def get_zone_of_camera(self, cam_id):
        """Returns the zone name a camera belongs to."""
        return self.camera_zone_map.get(cam_id)

    def sample_next_camera(self, cam_id):
        """Randomly selects next camera based on transition weights."""
        choices = self.get_possible_transitions(cam_id)
        if not choices:
            return None
        return random.choices(
            population=[t['to'] for t in choices],
            weights=[t['weight'] for t in choices]
        )[0]


# Example usage:
# config = MultiZoneCameraConfig()
# print(config.get_camera_uri('camA'))
# print(config.get_zone_of_camera('camA'))
# print(config.get_possible_transitions('camA'))
# print(config.sample_next_camera('camA'))
