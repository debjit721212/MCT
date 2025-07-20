"""
zone_pipeline.py

DeepStream GStreamer pipeline for a single zone with multiple cameras.

Responsibilities:
- Build and run the DeepStream pipeline for a zone.
- Handle multiple camera streams using `nvurisrcbin` and `nvstreammux`.
- Integrate detection, tracking, and optional ReID inference.
- Extract object metadata (bbox, track_id, embedding, etc.) via pad probe.
- Assign global IDs using the GlobalIDManager.

Author: Debjit
"""

import gi
import sys
import pyds
import ctypes
import numpy as np
import configparser
import traceback
import os
import time
import asyncio
from typing import List
# from app.global_id_manager import GlobalIDManager
from global_id_service.qdrant_backend.id_manager import GlobalIDManager
from app.FPS import PERF_DATA
from datetime import datetime

gi.require_version('Gst', '1.0')
from gi.repository import GLib, Gst


class ZonePipeline:
    def __init__(self, zone_name: str, camera_ids: List[str], config, global_id_manager: GlobalIDManager,fps_log_path=None):
        self.zone_name = zone_name
        self.camera_ids = camera_ids
        self.config = config
        self.pipeline = None
        self.source_bins = {}
        self.streammux = None
        self.global_id_manager = global_id_manager
        print(" ********************************************** ", self.global_id_manager)
        self.is_built = False
        self.cuda_visible_devices =0
        self.perf_data = PERF_DATA(stream_names=camera_ids, log_path=fps_log_path)
        self.index_to_cam = {i: cam_id for i, cam_id in enumerate(camera_ids)}
        self.cam_to_index = {cam_id: i for i, cam_id in enumerate(camera_ids)}
        self.display_mode = os.getenv("Display")
    
    def _process_metadata(self, track_data):
        try:
            global_id = self.global_id_manager.assign_global_id(
                track_data["cam_id"],
                track_data["track_id"],
                track_data["embedding"],
                track_data["timestamp"],
                self.zone_name
            )
            # print("embeddings -----> ", track_data["embedding"],track_data["embedding"].shape)
            # print(f"Assigned Global ID: {global_id} → TrackID: {track_data['track_id']}")
            print(f"[GLOBAL_ID] Assigned {global_id} for camera {track_data['cam_id']} track {track_data['track_id']}")
        except Exception as e:
            print(f"[ERROR] Failed to assign global ID: {e}", file=sys.stderr)
    
    def cb_newpad(self, decodebin, decoder_src_pad, data):
        print("In cb_newpad")
        caps = decoder_src_pad.get_current_caps()
        if not caps or caps.is_empty():
            print("[cb_newpad] current_caps not ready, trying query_caps...")
            caps = decoder_src_pad.query_caps()
            if not caps or caps.is_empty():
                print("[cb_newpad] WARNING: Failed to get caps. Skipping pad.")
                return

        gststruct = caps.get_structure(0)
        gstname = gststruct.get_name()
        source_bin = data
        features = caps.get_features(0)
        print("gstname=", gstname)

        if "video" in gstname:
            print("features=", features)
            if features.contains("memory:NVMM"):
                bin_ghost_pad = source_bin.get_static_pad("src")
                if not bin_ghost_pad.set_target(decoder_src_pad):
                    sys.stderr.write("Failed to link decoder src pad to source bin ghost pad\n")
            else:
                sys.stderr.write("Error: Decodebin did not pick NVIDIA decoder plugin.\n")


    def decodebin_child_added(self,child_proxy, Object, name, user_data):
        print("Decodebin child added:", name, "\n")
        if name.find("decodebin") != -1:
            Object.connect("child-added", self.decodebin_child_added, user_data)

    def _create_source_bin(self,index, uri,file_loop=False, gpu_id=0):
        print("Creating source bin")
        bin_name = "source-bin-%02d" % index
        print(bin_name)
        nbin = Gst.Bin.new(bin_name)
        if not nbin:
            sys.stderr.write("Unable to create source bin \n")
        uri_decode_bin = Gst.ElementFactory.make("nvurisrcbin", "nvurisrcbin")
        if file_loop:
            uri_decode_bin=Gst.ElementFactory.make("nvurisrcbin", "uri-decode-bin")
            uri_decode_bin.set_property("file-loop", 1)
            uri_decode_bin.set_property("cudadec-memtype", 0)
        else:
            uri_decode_bin = Gst.ElementFactory.make("nvurisrcbin", "nvurisrcbin")
        if not uri_decode_bin:
            sys.stderr.write("Unable to create uri decode bin \n")
        uri_decode_bin.set_property("uri", uri)
        uri_decode_bin.set_property("source-id", index)
        
        uri_decode_bin.set_property("latency", 1)
        uri_decode_bin.set_property("num-extra-surfaces", 5)
        uri_decode_bin.set_property("gpu-id", gpu_id)
        uri_decode_bin.set_property("rtsp-reconnect-interval", 180)
        uri_decode_bin.connect("pad-added", self.cb_newpad, nbin)
        uri_decode_bin.connect("child-added", self.decodebin_child_added, nbin)
        Gst.Bin.add(nbin, uri_decode_bin)
        bin_pad = nbin.add_pad(Gst.GhostPad.new_no_target("src", Gst.PadDirection.SRC))
        if not bin_pad:
            sys.stderr.write("Failed to add ghost pad in source bin \n")
            return None
        return nbin

    def build(self) -> None:
        print("**********************************************************")
        print(f"[INFO] Building pipeline for zone: {self.zone_name}")
        if self.is_built:
            print("[BUILD] 🔁 Pipeline already built. Skipping re-build.")
            return
        self.pipeline = Gst.Pipeline()
        if not self.pipeline:
            raise RuntimeError("Failed to create pipeline")
        self.streammux = Gst.ElementFactory.make("nvstreammux", "streammux")
        self.streammux.set_property("batch-size", len(self.camera_ids))
        self.streammux.set_property("width", 1280)
        self.streammux.set_property("height", 720)
        self.streammux.set_property("batched-push-timeout", 25000)
        self.pipeline.add(self.streammux)

        for index, cam_id in enumerate(self.camera_ids):
            uri = self.config.get_camera_uri(cam_id)
            print("HEY BRO I COME INSIDE CAMERAS ID ------> ", index,cam_id,uri)
            bin_src = self._create_source_bin(index, uri)
            self.pipeline.add(bin_src)
            sinkpad = self.streammux.get_request_pad(f"sink_{index}")
            srcpad = bin_src.get_static_pad("src")
            srcpad.link(sinkpad)

        pgie = Gst.ElementFactory.make("nvinfer", "primary-inference")
        pgie.set_property("config-file-path", "/opt/nvidia/deepstream/deepstream-7.1/MCT/models/person/person.txt")

        tracker = Gst.ElementFactory.make("nvtracker", "tracker")
        config = configparser.ConfigParser()
        config.read("/opt/nvidia/deepstream/deepstream-7.1/MCT/models/tracker/tracker.txt")
        for key in config['tracker']:
            if key == 'tracker-width' :
                tracker_width = config.getint('tracker', key)
                tracker.set_property('tracker-width', tracker_width)
            if key == 'tracker-height' :
                tracker_height = config.getint('tracker', key)
                tracker.set_property('tracker-height', tracker_height)
            if key == 'gpu-id' :
                tracker_gpu_id = config.getint('tracker', key)
                tracker.set_property('gpu_id', self.cuda_visible_devices)
            if key == 'll-lib-file' :
                tracker_ll_lib_file = config.get('tracker', key)
                tracker.set_property('ll-lib-file', tracker_ll_lib_file)
            if key == 'll-config-file' :
                tracker_ll_config_file = config.get('tracker', key)
                tracker.set_property('ll-config-file', tracker_ll_config_file)

        sgie = Gst.ElementFactory.make("nvinfer", "reid-infer")
        sgie.set_property("config-file-path", "/opt/nvidia/deepstream/deepstream-7.1/MCT/models/bodyEmbeddingV2/bodyEmbeddingv2.txt")

        nvvidconv = Gst.ElementFactory.make("nvvideoconvert", "nvvidconv")
        for elem in [pgie, tracker, sgie, nvvidconv]:
            if not elem:
                raise RuntimeError("Failed to create pipeline element")
            self.pipeline.add(elem)
        self.streammux.link(pgie)
        pgie.link(tracker)
        tracker.link(sgie)
        sgie.link(nvvidconv)
        if self.display_mode in ["Y", "y"]:
            tiler = Gst.ElementFactory.make("nvmultistreamtiler", "nvtiler")
            tiler_rows=2
            tiler_columns=2
            tiler.set_property("rows",tiler_rows)
            tiler.set_property("columns",tiler_columns)
            tiler.set_property("width", 1280)
            tiler.set_property("height", 720)
            tiler.set_property("gpu_id", 0)

            nvosd = Gst.ElementFactory.make("nvdsosd", "onscreendisplay")
            nvosd.set_property("gpu_id", 0)

            pipeline_sink = Gst.ElementFactory.make("nveglglessink", "sink")
            pipeline_sink.set_property("gpu_id", self.cuda_visible_devices)
            pipeline_sink.set_property("sync", 0)
            pipeline_sink.set_property("qos",0)

            self.pipeline.add(tiler)
            self.pipeline.add(nvosd)
            self.pipeline.add(pipeline_sink)
            # linking elements
           
            nvvidconv.link(tiler)
            tiler.link(nvosd)
            nvosd.link(pipeline_sink)
        else:
            fakesink = Gst.ElementFactory.make("fakesink", "fakesink")
            fakesink.set_property('enable-last-sample', 0)
            fakesink.set_property('sync', 0)
            self.pipeline.add(fakesink)
            nvvidconv.link(fakesink)

        if self.display_mode in ["Y", "y"]:
            sinkpad = nvosd.get_static_pad("sink")
            if sinkpad:
                sinkpad.add_probe(Gst.PadProbeType.BUFFER, self._metadata_probe, None)
                GLib.timeout_add(1000, self.perf_data.perf_print_callback)
        else:
            sinkpad = fakesink.get_static_pad("sink")
            if sinkpad:
                sinkpad.add_probe(Gst.PadProbeType.BUFFER, self._metadata_probe, None)
                GLib.timeout_add(1000, self.perf_data.perf_print_callback)

        print(f"[SUCCESS] Pipeline for zone '{self.zone_name}' constructed.")

    def _metadata_probe(self, pad, info, user_data) -> Gst.PadProbeReturn:
        try:
            buffer = info.get_buffer()
            if not buffer:
                return Gst.PadProbeReturn.OK

            batch_meta = pyds.gst_buffer_get_nvds_batch_meta(hash(buffer))
            if not batch_meta:
                return Gst.PadProbeReturn.OK

            l_frame = batch_meta.frame_meta_list
            while l_frame:
                frame_meta = pyds.NvDsFrameMeta.cast(l_frame.data)
                l_obj = frame_meta.obj_meta_list
                while l_obj:
                    obj_meta = pyds.NvDsObjectMeta.cast(l_obj.data)
                    # print("OBJ AND TRACK_ID BRO -----> ", obj_meta.obj_label,obj_meta.object_id)
                    l_user = obj_meta.obj_user_meta_list
                    while l_user:
                        user_meta = pyds.NvDsUserMeta.cast(l_user.data)
                        if user_meta.base_meta.meta_type == pyds.NvDsMetaType.NVDSINFER_TENSOR_OUTPUT_META:
                            tensor_meta = pyds.NvDsInferTensorMeta.cast(user_meta.user_meta_data)
                            for i in range(tensor_meta.num_output_layers):
                                # layer = pyds.get_nvds_LayerInfo(tensor_meta, i)
                                # ptr = ctypes.cast(pyds.get_ptr(layer.buffer), ctypes.POINTER(ctypes.c_float))
                                # arr = np.ctypeslib.as_array(ptr, shape=(layer.dims.numElements,),copy=True)
                                layer = pyds.get_nvds_LayerInfo(tensor_meta, i)
                                ptr = ctypes.cast(pyds.get_ptr(layer.buffer), ctypes.POINTER(ctypes.c_float))
                                embedding = np.array(np.ctypeslib.as_array(ptr, shape=(layer.dims.numElements,)), copy=True)
                                # print(" embedding and shape -----> ", embedding,)
                                # Prepare the data for global ID assignment
                                track_data = {
                                    "cam_id": self.index_to_cam.get(frame_meta.pad_index, f"stream{frame_meta.pad_index}"),
                                    "track_id": obj_meta.object_id,
                                    "embedding": embedding,
                                    "timestamp": time.time()
                                }
                                
                                # Process global ID assignment in a separate thread (non-blocking)
                                self._process_metadata(track_data)

                                # global_id = self.global_id_manager.assign_global_id(
                                #     zone_name=self.zone_name,
                                #     cam_id=f"stream{frame_meta.pad_index}",
                                #     track_id=obj_meta.object_id,
                                #     embedding=embedding
                                # )
                                # print(f"Assigned Global ID: {global_id} → TrackID: {obj_meta.object_id}")
                        l_user = l_user.next
                    l_obj = l_obj.next
                # Update frame rate through this probe
                cam_id = self.index_to_cam.get(frame_meta.pad_index, f"stream{frame_meta.pad_index}")
                self.perf_data.update_fps(cam_id)
                l_frame = l_frame.next
        except Exception as e:
            print(f"[ERROR] Metadata probe failed: {e}", file=sys.stderr)
        return Gst.PadProbeReturn.OK
    

    def start(self):
        print("HEY DEB I CAME HERE FOR PRINT THIS PROPERLY ------------------------> HELP ")
        if not self.is_built:
            print("HEY I CAME INSIDE BUILD , NOW I will start building it ")
            self.build()  # build if not already
        if self.pipeline.set_state(Gst.State.PLAYING) == Gst.StateChangeReturn.FAILURE:
            raise RuntimeError("Unable to set pipeline to PLAYING")
        print(f"[INFO] Zone pipeline '{self.zone_name}' started.")

    def stop(self):
        self.pipeline.set_state(Gst.State.NULL)
        print(f"[INFO] Zone pipeline '{self.zone_name}' stopped.")
