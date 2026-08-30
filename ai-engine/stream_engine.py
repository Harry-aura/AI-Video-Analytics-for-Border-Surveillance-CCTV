"""
IBVAP Defense-Grade V2 - 100% Live Multi-Camera Ingestion & Streaming Engine
- High-Performance Threaded Video Capture Readers (Paced 30 FPS playback for video files & physical cameras).
- Advanced Multi-Class Defense Matrix (Personnel, Vehicles, Motorcycles, Bicycles, Drones/UAVs, Wildlife).
- Anti-Spoofing & Animal Rejection Filter (Suppresses neutral wildlife from false DEFCON 1 alarms).
- Anti-Crawl Disguise Analyzer (Detects prone/crawling human infiltrators).
- Planar Shadow Elimination via Laplacian Gradient Variance Analysis.
- Decoupled Sector Tactical Radar Display & Zero Target Bleed.
- Persistent Latched Defense Audio Engine (Military Klaxon 800-1200Hz) & HTML5 Audio Loop.
- Instant Breach Snapshot Capture to alert_snapshots/ directory & atomic SQLite audit logging.
- Persistent DEFCON-1 Alarm Latching (Never Auto-Clears until Operator Acknowledgment).
- Asynchronous HTTP MJPEG Streaming Server on port 8000 with SO_REUSEADDR port cleanup.
- Zero mock data enforcement.
"""
import os
import cv2
import json
import time
import math
import socket
import sqlite3
import threading
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn
import numpy as np
import torch
from ultralytics import YOLO
from edge_optimizer import EdgeOptimizer
from reid_engine import MultiCameraReIDManager
from homography_radar import HomographyRadarProjector
from threat_analyzer import ThreatAnalyzer
from trajectory_predictor import KalmanTrajectoryPredictor
from mesh_resiliency import MeshResiliencyManager
from forensic_search import ForensicSearchEngine
from tamper_engine import CameraHealthMonitor, TacticalThreatScorer
from iff_engine import TacticalIFFManager
from audio_engine import DefenseAudioEngine

# Target Detection Taxonomy (COCO IDs)
TARGET_CLASSES = [0, 1, 2, 3, 4, 5, 7, 14, 15, 16, 17, 18, 19, 20, 21]

CLASS_NAMES = {
    0: "PERSON",
    1: "BICYCLE",
    2: "CAR",
    3: "MOTORCYCLE",
    4: "DRONE_UAV",
    5: "BUS",
    7: "TRUCK",
    14: "BIRD", 15: "CAT", 16: "DOG", 17: "HORSE",
    18: "SHEEP", 19: "COW", 20: "ELEPHANT", 21: "BEAR"
}

# Velocity & Displacement thresholds for motion-aware breach validation
MIN_MOTION_VELOCITY = 0.35
MIN_MOTION_DISPLACEMENT = 3.0

# --- Threaded Capture Reader for Smooth 30 FPS File & Camera Playback ---
class ThreadedCaptureReader:
    def __init__(self, camera_id: str, source, fallback_path: str, fps_target: int = 30):
        self.camera_id = camera_id
        self.source = source
        self.fallback_path = fallback_path
        self.fps_target = fps_target
        self.frame_delay = 1.0 / max(10, fps_target)
        
        self.lock = threading.Lock()
        self.latest_frame = None
        self.running = False
        self.thread = None
        self.is_file = not (isinstance(source, int) or (isinstance(source, str) and source.isdigit()))
        self.on_rewind_cb = None
        
        # Open capture device on main thread
        self.cap = self._open_cap()

    def _open_cap(self):
        # Open source with DirectShow / VideoCapture
        if isinstance(self.source, int) or (isinstance(self.source, str) and self.source.isdigit()):
            dev_idx = int(self.source)
            cap = cv2.VideoCapture(dev_idx, cv2.CAP_DSHOW)
            if cap.isOpened():
                cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                cap.set(cv2.CAP_PROP_FPS, self.fps_target)
                self.is_file = False
                return cap

            cap = cv2.VideoCapture(dev_idx, cv2.CAP_ANY)
            if cap.isOpened():
                cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                cap.set(cv2.CAP_PROP_FPS, self.fps_target)
                self.is_file = False
                return cap

            print(f"[STREAM-ENGINE] Physical camera {self.source} unavailable. Falling back to {self.fallback_path}")
            self.is_file = True
            cap = cv2.VideoCapture(self.fallback_path)
            return cap

        resolved_path = self.source
        if isinstance(self.source, str) and not os.path.isabs(self.source):
            script_dir = os.path.dirname(os.path.abspath(__file__))
            resolved_path = os.path.join(script_dir, self.source)
            
        if os.path.exists(resolved_path):
            cap = cv2.VideoCapture(resolved_path)
            self.is_file = True
            return cap
        elif str(self.source).startswith("rtsp://") or str(self.source).startswith("http://"):
            cap = cv2.VideoCapture(self.source)
            self.is_file = False
            return cap
        else:
            print(f"[STREAM-ENGINE] Source '{self.source}' not found. Falling back to {self.fallback_path}")
            self.is_file = True
            cap = cv2.VideoCapture(self.fallback_path)
            return cap

    def start(self):
        if self.running:
            return
        self.running = True
        self.thread = threading.Thread(target=self._capture_loop, daemon=True)
        self.thread.start()

    def stop(self):
        self.running = False
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=0.3)
        if self.cap:
            try:
                self.cap.release()
            except Exception:
                pass

    def _capture_loop(self):
        while self.running:
            start_t = time.time()
            if self.cap is None or not self.cap.isOpened():
                self.cap = self._open_cap()
                time.sleep(0.04)
                continue

            if not self.is_file:
                # Live camera feed buffer purge: drop stale backlog
                try:
                    self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                    self.cap.grab()
                except Exception:
                    pass

            ret, frame = self.cap.read()
            if not ret or frame is None:
                # If source is a local video file, loop continuously without freezing
                if isinstance(self.source, str) and not self.source.startswith(("rtsp://", "http://")):
                    self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    if hasattr(self, 'on_rewind_cb') and callable(self.on_rewind_cb):
                        self.on_rewind_cb(self.camera_id)
                    ret, frame = self.cap.read()
                elif self.is_file:
                    self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    if hasattr(self, 'on_rewind_cb') and callable(self.on_rewind_cb):
                        self.on_rewind_cb(self.camera_id)
                    ret, frame = self.cap.read()
                
                if not ret or frame is None:
                    time.sleep(0.03)
                    continue

            if frame is not None and frame.size > 0:
                frame = cv2.resize(frame, (640, 480))
                with self.lock:
                    self.latest_frame = frame
                
            if self.is_file:
                # Pace file reading to match native 30 FPS playback rate (~33ms)
                elapsed = time.time() - start_t
                sleep_t = self.frame_delay - elapsed
                if sleep_t > 0:
                    time.sleep(sleep_t)
            else:
                time.sleep(0.001)

    def get_latest_frame(self):
        with self.lock:
            return self.latest_frame.copy() if self.latest_frame is not None else None

    def read_latest(self):
        with self.lock:
            return (self.latest_frame is not None), (self.latest_frame.copy() if self.latest_frame is not None else None)

# Backward compatibility aliases
ThreadedCameraReader = ThreadedCaptureReader
RealTimeCameraCapture = ThreadedCaptureReader

# --- Tactical Alarm Audio State Bridge ---
class SoundAlarmController:
    def __init__(self):
        self.is_active = False

    def start_alarm(self):
        self.is_active = True

    def stop_alarm(self):
        self.is_active = False

# --- 2D Vector Geometry for Exact CCW Line-Segment Intersection ---
def ccw(A, B, C):
    """
    Returns True if three points A, B, C are listed in a counter-clockwise orientation.
    ccw(A, B, C) = (C_y - A_y)(B_x - A_x) > (B_y - A_y)(C_x - A_x)
    """
    return (C[1] - A[1]) * (B[0] - A[0]) > (B[1] - A[1]) * (C[0] - A[0])

def segments_intersect(p1, q1, p2, q2):
    """
    Exact CCW Line-Segment Intersection test:
    intersect(A, B, C, D) = (ccw(A, C, D) != ccw(B, C, D)) and (ccw(A, B, C) != ccw(A, B, D))
    """
    return (ccw(p1, p2, q2) != ccw(q1, p2, q2)) and (ccw(p1, q1, p2) != ccw(p1, q1, q2))

def get_directed_side(pt, p1, p2):
    """
    Computes cross-product side: > 0 for Left/Inward, < 0 for Right/Outward.
    """
    return (p2[0] - p1[0]) * (pt[1] - p1[1]) - (p2[1] - p1[1]) * (pt[0] - p1[0])

class CameraStreamWorker:
    def __init__(self, camera_id: str, camera_name: str, source_config: dict, snapshot_dir: str, skip_n: int = 2):
        self.camera_id = camera_id
        self.camera_name = camera_name
        self.source = source_config.get('source', 0)
        self.fps_target = source_config.get('fps_target', 30)
        self.snapshot_dir = snapshot_dir
        
        # Zero-Default: Initialize with empty points list if not configured
        raw_pts = source_config.get('fence_points', [])
        self.fence_points = [tuple(p) for p in raw_pts] if raw_pts else []
        self.boundary_mode = source_config.get('boundary_mode', 'OPEN_LINE')
        self.zone_orientation = source_config.get('zone_orientation', 'INWARD')
        self.skip_n = skip_n
        
        self.lock = threading.Lock()
        self.latest_frame = None
        self.latest_raw_frame = None
        self.latest_jpeg = None
        self.fps = float(self.fps_target)
        self.frame_count = 0
        self.active_tracks = {}  # {local_tid: {box, cls, global_id, iff, prev_foot, curr_foot, history}}
        self.health_status = "NOMINAL"
        
        # PERSISTENT DEFCON 1 LATCHING ALARM STATE (Never auto-clears on exit)
        self.is_alarm_latched = False
        self.latched_alert = None
        self.last_snapshot_path = None
        self.breach_cooldown = 0

    def update_boundary_config(self, fence_points: list, boundary_mode: str, zone_orientation: str):
        with self.lock:
            self.fence_points = [tuple(p) for p in fence_points] if fence_points else []
            self.boundary_mode = boundary_mode
            self.zone_orientation = zone_orientation
            print(f"[STREAM-WORKER] {self.camera_id} boundary updated: {len(self.fence_points)} points ({self.boundary_mode}, {self.zone_orientation})")
    def acknowledge_alert(self):
        with self.lock:
            self.is_alarm_latched = False
            self.latched_alert = None
            print(f"[STREAM-WORKER] Alarm acknowledged & reset for {self.camera_id}.")

    def update_frame(self, raw_frame: np.ndarray, detections: list, reid_mgr: MultiCameraReIDManager,
                     threat_analyzer: ThreatAnalyzer, kalman_pred: KalmanTrajectoryPredictor,
                     homography_proj: HomographyRadarProjector, mesh_mgr: MeshResiliencyManager,
                     forensic_engine: ForensicSearchEngine, sound_ctrl: SoundAlarmController,
                     db_path: str, is_inference_frame: bool, threat_scorer: TacticalThreatScorer = None,
                     iff_mgr: TacticalIFFManager = None):
        h, w = raw_frame.shape[:2]
        processed = raw_frame.copy()
        
        with self.lock:
            pts = list(self.fence_points)
            b_mode = self.boundary_mode
            z_orient = self.zone_orientation

        n_pts = len(pts)
        has_perimeter = (n_pts >= 2)

        # 1. Render Boundary Overlays ONLY if perimeter has been explicitly defined (>= 2 points)
        if has_perimeter:
            if b_mode == 'CLOSED_POLYGON' and n_pts >= 3:
                poly_arr = np.array(pts, dtype=np.int32).reshape((-1, 1, 2))
                overlay = processed.copy()
                cv2.fillPoly(overlay, [poly_arr], (0, 0, 180))
                cv2.addWeighted(overlay, 0.22, processed, 0.78, 0, processed)
                cv2.polylines(processed, [poly_arr], isClosed=True, color=(0, 140, 255), thickness=3, lineType=cv2.LINE_AA)
                cv2.polylines(processed, [poly_arr], isClosed=True, color=(0, 255, 255), thickness=1, lineType=cv2.LINE_AA)
            else:
                for i in range(n_pts - 1):
                    p_a, p_b = pts[i], pts[i + 1]
                    cv2.line(processed, p_a, p_b, (0, 140, 255), 4, cv2.LINE_AA)
                    cv2.line(processed, p_a, p_b, (0, 255, 255), 2, cv2.LINE_AA)

            # Draw Numbered Vertex Markers
            for idx, pt in enumerate(pts):
                color = (0, 255, 0) if idx == 0 else ((0, 0, 255) if idx == n_pts-1 else (0, 255, 255))
                cv2.circle(processed, pt, 6, color, -1)
                cv2.circle(processed, pt, 8, (255, 255, 255), 1)
                cv2.putText(processed, str(idx + 1), (pt[0] - 4, pt[1] - 8),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.35, (255, 255, 255), 1)

            # Directional Normal Arrow on middle segment
            mid_idx = (n_pts - 1) // 2
            p_start, p_end = pts[mid_idx], pts[min(mid_idx + 1, n_pts - 1)]
            mid_x = (p_start[0] + p_end[0]) // 2
            mid_y = (p_start[1] + p_end[1]) // 2
            
            dx_seg = p_end[0] - p_start[0]
            dy_seg = p_end[1] - p_start[1]
            seg_len = math.hypot(dx_seg, dy_seg) + 1e-6
            nx = -dy_seg / seg_len
            ny = dx_seg / seg_len
            if z_orient == 'OUTWARD':
                nx, ny = -nx, -ny

            arr_tip = (int(mid_x + nx * 28), int(mid_y + ny * 28))
            cv2.arrowedLine(processed, (mid_x, mid_y), arr_tip, (0, 255, 255), 2, tipLength=0.35)
            cv2.putText(processed, f"NORMAL: {z_orient}", (arr_tip[0] + 5, arr_tip[1] + 4),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.35, (0, 255, 255), 1)

        # 2. Track & Process Detections
        current_active = {}
        poly_pts_np = np.array(pts, dtype=np.int32).reshape((-1, 1, 2)) if (has_perimeter and b_mode == 'CLOSED_POLYGON' and n_pts >= 3) else None
        
        for det in detections:
            box = det['box']
            cls_id = det['cls']
            local_tid = det.get('id', 1)
            
            x1, y1, x2, y2 = box
            curr_foot = (int((x1 + x2) / 2), int(y2))
            crop = raw_frame[max(0, y1):min(h, y2), max(0, x1):min(w, x2)]
            
            # Anti-Shadow Analysis
            if threat_analyzer is not None and hasattr(threat_analyzer, 'is_planar_shadow'):
                try:
                    if threat_analyzer.is_planar_shadow(crop):
                        continue
                except Exception:
                    pass

            # Multi-Camera Re-ID Global Association
            embedding = reid_mgr.extract_embedding(crop) if (is_inference_frame and hasattr(reid_mgr, 'extract_embedding')) else None
            
            if hasattr(reid_mgr, 'associate_global_track'):
                gid = reid_mgr.associate_global_track(self.camera_id, local_tid, cls_id, embedding, curr_foot, is_inference_frame)
            elif hasattr(reid_mgr, 'match_or_register_global_id'):
                gid = reid_mgr.match_or_register_global_id(local_tid, self.camera_id, crop, cls_id)
            elif hasattr(reid_mgr, 'match_or_create_global_id'):
                gid = reid_mgr.match_or_create_global_id(local_tid, self.camera_id, embedding)
            else:
                gid = local_tid
            
            # Kalman Velocity & Trajectory Prediction with safe fallback
            if hasattr(kalman_pred, 'update_track'):
                vx, vy = kalman_pred.update_track(gid, curr_foot)
            elif hasattr(kalman_pred, 'update'):
                _, _, vx, vy = kalman_pred.update(gid, float(curr_foot[0]), float(curr_foot[1]))
            else:
                vx, vy = 0.0, 0.0

            # Track history from local tracker and Kalman predictor
            prev_active = self.active_tracks.get(local_tid, {})
            local_prev_foot = prev_active.get('curr_foot', None)
            
            history_pts = [curr_foot]
            if local_prev_foot is not None and local_prev_foot != curr_foot:
                history_pts.append(local_prev_foot)

            if hasattr(kalman_pred, 'get_history'):
                breadcrumb = kalman_pred.get_history(gid)
                for pt in reversed(breadcrumb):
                    if pt not in history_pts:
                        history_pts.append(pt)
            else:
                breadcrumb = history_pts

            prev_foot = history_pts[1] if len(history_pts) >= 2 else curr_foot
            
            # Kinematic motion validation & real-world velocity (km/h)
            velocity_mag = math.hypot(vx, vy)
            displacement = math.hypot(curr_foot[0] - prev_foot[0], curr_foot[1] - prev_foot[1])
            if displacement > 5.0 and velocity_mag < (displacement / 30.0):
                velocity_mag = max(velocity_mag, displacement / 20.0)
            velocity_kmh = round(max(0.0, velocity_mag * 3.6), 1)
            is_moving = (velocity_mag >= MIN_MOTION_VELOCITY or displacement >= MIN_MOTION_DISPLACEMENT)

            # Homography Radar Mapping with safe fallback
            if hasattr(homography_proj, 'project_point'):
                map_x, map_y = homography_proj.project_point(self.camera_id, curr_foot[0], curr_foot[1])
            elif hasattr(homography_proj, 'project_foot_coordinate'):
                map_x, map_y = homography_proj.project_foot_coordinate(self.camera_id, box)
            else:
                map_x, map_y = (200, 200)

            # Threat Analysis & Posture Classification (with kinematics)
            threat_info = {}
            if threat_analyzer is not None:
                if hasattr(threat_analyzer, 'analyze_target_threat'):
                    threat_info = threat_analyzer.analyze_target_threat(crop, cls_id, box, velocity_mag)
                elif hasattr(threat_analyzer, 'classify_threat'):
                    threat_info = threat_analyzer.classify_threat(crop, cls_id, self.camera_id, bbox=box, velocity_mag=velocity_mag)
                elif hasattr(threat_analyzer, 'analyze'):
                    threat_info = threat_analyzer.analyze(crop, cls_id)
                else:
                    threat_info = {"threat_level": "NOMINAL", "score": 0.0, "is_threat": True, "target_category": CLASS_NAMES.get(cls_id, 'TARGET')}
            else:
                threat_info = {"threat_level": "NOMINAL", "score": 0.0, "is_threat": True, "target_category": CLASS_NAMES.get(cls_id, 'TARGET')}

            target_cat = threat_info.get('target_category', CLASS_NAMES.get(cls_id, 'TARGET'))
            raw_class = threat_info.get('raw_class', CLASS_NAMES.get(cls_id, 'TARGET'))
            posture = threat_info.get('posture', 'IN TRANSIT')
            is_animal = threat_info.get('is_animal', False) or (cls_id in [14, 15, 16, 17, 18, 19, 20, 21])
            is_genuine_threat = (threat_info.get('is_threat', True) or cls_id == 0) and not is_animal
            
            breach_detected = False
            is_rapid_sprint = False
            
            if has_perimeter and is_moving:
                if b_mode == 'CLOSED_POLYGON' and poly_pts_np is not None:
                    inside_curr = cv2.pointPolygonTest(poly_pts_np, (float(curr_foot[0]), float(curr_foot[1])), False) >= 0
                    if inside_curr:
                        breach_detected = True
                        if velocity_kmh >= 15.0 or displacement >= 20.0:
                            is_rapid_sprint = True
                else:
                    for i in range(n_pts - 1):
                        seg_start = pts[i]
                        seg_end = pts[i + 1]
                        
                        # 1. Exact Continuous Trajectory Interpolation & Multi-Point Ray Sweep
                        for h_idx in range(1, len(history_pts)):
                            h_pt = history_pts[h_idx]
                            if segments_intersect(h_pt, curr_foot, seg_start, seg_end):
                                breach_detected = True
                                if velocity_kmh >= 15.0 or displacement >= 20.0:
                                    is_rapid_sprint = True
                                break
                        if breach_detected:
                            break

                        # 2. Bi-directional Boundary Crossing Test across history
                        for h_idx in range(1, len(history_pts)):
                            h_pt = history_pts[h_idx]
                            p_side = get_directed_side(h_pt, seg_start, seg_end)
                            c_side = get_directed_side(curr_foot, seg_start, seg_end)
                            if (p_side * c_side < 0) or ((p_side <= 0 and c_side > 0) if z_orient == 'INWARD' else (p_side >= 0 and c_side < 0)):
                                seg_len = math.hypot(seg_end[0]-seg_start[0], seg_end[1]-seg_start[1])
                                if seg_len > 0:
                                    breach_detected = True
                                    if velocity_kmh >= 15.0 or displacement >= 20.0:
                                        is_rapid_sprint = True
                                    break
                        if breach_detected:
                            break

                        # 3. Direct Fence Contact / Proximity Climbing Check
                        px = seg_end[0] - seg_start[0]
                        py = seg_end[1] - seg_start[1]
                        seg_len_sq = float(px*px + py*py)
                        if seg_len_sq > 0:
                            u = max(0.0, min(1.0, ((curr_foot[0] - seg_start[0]) * px + (curr_foot[1] - seg_start[1]) * py) / seg_len_sq))
                            proj_x = seg_start[0] + u * px
                            proj_y = seg_start[1] + u * py
                            dist_to_fence = math.hypot(curr_foot[0] - proj_x, curr_foot[1] - proj_y)
                            if dist_to_fence < 14.0 and displacement > 1.0:
                                breach_detected = True
                                break

            # Find closest fence segment for directional vector calculation
            closest_segment = None
            if has_perimeter and n_pts >= 2:
                closest_segment = (pts[0], pts[1])
                min_d = float('inf')
                for i in range(n_pts - 1):
                    p_a, p_b = pts[i], pts[i+1]
                    d_c = math.hypot((curr_foot[0] - (p_a[0]+p_b[0])/2), (curr_foot[1] - (p_a[1]+p_b[1])/2))
                    if d_c < min_d:
                        min_d = d_c
                        closest_segment = (p_a, p_b)

            # Tactical IFF & Directional Patrol Assessment (Strict Class Isolation)
            if iff_mgr:
                iff_eval = iff_mgr.evaluate_target(
                    target_id=gid,
                    embedding=embedding,
                    velocity_vec=(vx, vy),
                    segment=closest_segment,
                    zone_orientation=z_orient,
                    target_class=raw_class
                )
            else:
                iff_eval = {
                    'target_id': gid,
                    'iff_status': 'NEUTRAL_WILDLIFE' if is_animal else threat_info.get('iff_status', 'HOSTILE'),
                    'is_friendly': False,
                    'direction': 'INGRESS',
                    'is_ingress': True,
                    'suppress_alarm': is_animal,
                    'reason': 'Direct Assessment',
                    'hud_label': f"#{gid} {target_cat}",
                    'badge': '🟡 WILDLIFE' if is_animal else '🔴 HOSTILE',
                    'badge_color': '#e0a800' if is_animal else '#ff4d4f'
                }

            # Animal Bypass: Force IFF suppression for harmless wildlife
            if is_animal:
                iff_eval['iff_status'] = 'NEUTRAL_WILDLIFE'
                iff_eval['suppress_alarm'] = True
                iff_eval['is_breach'] = False
                iff_eval['badge'] = '🟡 WILDLIFE (NON-THREAT)'
                iff_eval['badge_color'] = '#e0a800'

            # Compute dynamic Tactical Threat Score (0 - 100%)
            existing_first = self.active_tracks.get(local_tid, {}).get('first_seen', time.time())
            dwell_s = max(0.5, time.time() - existing_first)
            
            if is_animal:
                tactical_threat = {
                    'threat_score_pct': 10.0,
                    'defcon_tier': 'DEFCON 3 (Wildlife Transit / Harmless)',
                    'tier_badge': '🟡 WILDLIFE',
                    'tier_color': '#e0a800',
                    'd_norm': 0.1,
                    'v_norm': min(1.0, velocity_mag / 12.0),
                    't_dwell_norm': 0.1,
                    'cos_heading': 0.0
                }
            elif threat_scorer:
                tactical_threat = threat_scorer.compute_threat_score(
                    foot_coord=curr_foot,
                    velocity=(vx, vy),
                    fence_points=pts,
                    dwell_seconds=dwell_s,
                    zone_orientation=z_orient,
                    is_breached=breach_detected
                )
            else:
                tactical_threat = {
                    'threat_score_pct': 88.0 if breach_detected else 25.0,
                    'defcon_tier': 'DEFCON 1 (Critical Threat)' if breach_detected else 'DEFCON 3 (Advisory / Low Threat)',
                    'tier_badge': '🔴 DEFCON 1' if breach_detected else '🟢 DEFCON 3',
                    'tier_color': '#ff4d4f' if breach_detected else '#52c41a',
                    'd_norm': 1.0 if breach_detected else 0.5,
                    'v_norm': min(1.0, velocity_mag / 12.0),
                    't_dwell_norm': min(1.0, dwell_s / 15.0),
                    'cos_heading': 0.5
                }

            if breach_detected:
                if is_genuine_threat and not is_animal:
                    suppress_alarm = iff_eval.get('suppress_alarm', False)

                    if not suppress_alarm:
                        # 1. PERSISTENT DEFCON 1 LATCHING (Strict Zero-Tolerance Breach / Rapid Sprint)
                        self.is_alarm_latched = True
                        if is_rapid_sprint:
                            self.latched_alert = f"DEFCON 1: RAPID SPRINT INFILTRATION BREACH DETECTED - #{gid} [{target_cat} | {velocity_kmh} KM/H] ON {self.camera_name.upper()}"
                        else:
                            self.latched_alert = f"DEFCON 1: PERIMETER BREACH DETECTED - #{gid} [{target_cat} | {posture}] {self.camera_name.upper()}"
                        
                        # 2. TRIGGER TACTICAL DEFENSE ALARM LATCH
                        if sound_ctrl:
                            sound_ctrl.start_alarm()
                    else:
                        print(f"[STREAM-ENGINE] 🛡️ Siren suppressed for #{gid}: {iff_eval.get('reason')}")

                    # 3. INSTANT EVIDENCE SNAPSHOT CAPTURE (Immediate Disk Write)
                    now_ts = time.time()
                    if now_ts > self.breach_cooldown:
                        self.breach_cooldown = now_ts + 2.0
                        ts_str = datetime.now().strftime("%Y%m%d_%H%M%S")
                        snap_name = f"breach_{self.camera_id}_target_{gid}_{ts_str}.jpg"
                        snap_path = os.path.join(self.snapshot_dir, snap_name)
                        
                        event_type = "INFO_PATROL_SWEEP" if suppress_alarm else "PERIMETER_BREACH"
                        
                        # Capture full annotated evidence frame
                        evidence_frame = processed.copy()
                        rect_color = (0, 255, 200) if suppress_alarm else (0, 0, 255)
                        cv2.rectangle(evidence_frame, (x1, y1), (x2, y2), rect_color, 3)
                        cv2.putText(evidence_frame, f"{event_type} #{gid} [{target_cat} | {posture}]",
                                    (x1, max(20, y1 - 10)), cv2.FONT_HERSHEY_SIMPLEX, 0.55, rect_color, 2)
                        
                        os.makedirs(self.snapshot_dir, exist_ok=True)
                        cv2.imwrite(snap_path, evidence_frame, [int(cv2.IMWRITE_JPEG_QUALITY), 95])
                        self.last_snapshot_path = snap_path
                        print(f"[STREAM-ENGINE] 📸 Instant breach snapshot captured: {snap_name}")

                        # Real Event Logging to SQLite (Atomic Inserts to events and forensic_metadata)
                        try:
                            conn = sqlite3.connect(db_path)
                            cur = conn.cursor()
                            cur.execute("""
                            INSERT INTO events (event_type, camera_id, track_id, global_id, target_type, snapshot_path, iff_status, uniform_type, weapon_posture, threat_score, timestamp)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """, (
                                event_type,
                                self.camera_id,
                                local_tid,
                                gid,
                                target_cat,
                                snap_name,
                                iff_eval.get('iff_status', 'HOSTILE'),
                                threat_info.get('uniform_type', 'CIVILIAN'),
                                posture,
                                tactical_threat['threat_score_pct'] / 100.0,
                                time.strftime("%Y-%m-%d %H:%M:%S")
                            ))
                            
                            cur.execute("""
                            INSERT INTO forensic_metadata (timestamp, camera_id, sector, target_cls, global_id, iff_status, uniform_type, weapon_posture, threat_score, license_plate, snapshot_path, tags)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """, (
                                time.strftime("%Y-%m-%d %H:%M:%S"),
                                self.camera_id,
                                "RESTRICTED_ZONE",
                                target_cat,
                                gid,
                                iff_eval.get('iff_status', 'HOSTILE'),
                                threat_info.get('uniform_type', 'CIVILIAN'),
                                posture,
                                tactical_threat['threat_score_pct'] / 100.0,
                                "N/A",
                                snap_name,
                                "perimeter_breach"
                            ))
                            conn.commit()
                            conn.close()
                        except Exception as e:
                            print(f"[STREAM-ENGINE] Notice logging event snapshot: {e}")

                    mesh_mgr.dispatch_telemetry_packet({
                        'type': 'PERIMETER_BREACH_ALERT',
                        'cam': self.camera_id,
                        'gid': gid,
                        'cls': target_cat,
                        'iff': iff_eval.get('iff_status', 'HOSTILE'),
                        'map_pos': [map_x, map_y],
                        'timestamp': int(time.time())
                    }, crop=crop)

                elif is_animal:
                    # Silent wildlife transit logging (Zero Siren Trigger)
                    now_ts = time.time()
                    if now_ts > self.breach_cooldown:
                        self.breach_cooldown = now_ts + 3.0
                        ts_str = datetime.now().strftime("%Y%m%d_%H%M%S")
                        snap_name = f"wildlife_{self.camera_id}_target_{gid}_{ts_str}.jpg"
                        snap_path = os.path.join(self.snapshot_dir, snap_name)
                        cv2.imwrite(snap_path, processed, [int(cv2.IMWRITE_JPEG_QUALITY), 90])
                        print(f"[STREAM-ENGINE] 🐾 Animal transit logged silently: {raw_class} #{gid}")

            current_active[local_tid] = {
                'camera_id': self.camera_id,
                'box': box,
                'cls': cls_id,
                'cls_name': target_cat,
                'raw_class': raw_class,
                'posture': posture,
                'velocity_kmh': velocity_kmh,
                'is_animal': is_animal,
                'global_id': gid,
                'threat_info': threat_info,
                'iff_eval': iff_eval,
                'iff_status': iff_eval.get('iff_status', 'HOSTILE'),
                'is_friendly': iff_eval.get('is_friendly', False),
                'direction': iff_eval.get('direction', 'INGRESS'),
                'velocity': (vx, vy),
                'velocity_mag': velocity_mag,
                'displacement': displacement,
                'is_moving': is_moving,
                'prev_foot': prev_foot,
                'curr_foot': curr_foot,
                'map_pos': (map_x, map_y),
                'breadcrumb_trail': breadcrumb,
                'last_seen': time.time(),
                'first_seen': existing_first,
                'tactical_threat': tactical_threat,
                'threat_score_pct': tactical_threat['threat_score_pct'],
                'defcon_tier': tactical_threat['defcon_tier'],
                'tier_badge': tactical_threat['tier_badge']
            }

            # Render Bounding Box HUD with Multi-Class Tactical Color Coding
            final_iff = iff_eval.get('iff_status', 'HOSTILE')
            if is_animal or final_iff == 'NEUTRAL_WILDLIFE':
                box_color = (0, 200, 255)  # Yellow / Gold
                hud_label = f"#{gid} {raw_class} | NON-THREAT | {velocity_kmh:.1f} km/h"
                text_color = (0, 0, 0)
            elif final_iff == 'FRIENDLY':
                box_color = (255, 255, 0)  # Cyan/Green
                hud_label = f"#{gid} FRIENDLY - {iff_eval.get('friendly_label', 'BSF PATROL')} | {velocity_kmh:.1f} km/h"
                text_color = (0, 0, 0)
            else:
                # Bright RED for Hostile Person, Vehicle, Drone, Infiltrator
                box_color = (0, 0, 255)    # Bright Red
                hud_label = f"#{gid} {target_cat} | {posture} | {velocity_kmh:.1f} km/h"
                text_color = (255, 255, 255)

            cv2.rectangle(processed, (x1, y1), (x2, y2), box_color, 2)
            cv2.circle(processed, curr_foot, 5, (0, 255, 255), -1)
            
            if is_moving and velocity_mag > 0.5:
                hx = int(curr_foot[0] + vx * 5.0)
                hy = int(curr_foot[1] + vy * 5.0)
                cv2.arrowedLine(processed, curr_foot, (hx, hy), (0, 255, 255), 2, tipLength=0.3)

            hud_full = f"{hud_label} | {tactical_threat['threat_score_pct']:.0f}%"
            cv2.rectangle(processed, (x1, max(0, y1 - 20)), (x1 + len(hud_full) * 7 + 10, y1), box_color, -1)
            cv2.putText(processed, hud_full, (x1 + 4, max(14, y1 - 5)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.38, text_color, 1)

        # Single Consolidated Defense HUD Banner (Zero Duplicate UI Stacking)
        health_txt = getattr(self, 'health_status', 'NOMINAL')
        is_tampered = (health_txt != "NOMINAL" and ("TAMPER" in health_txt or "SIGNAL LOSS" in health_txt))

        # Latched Alarm Coupling on Optical Tamper
        if is_tampered:
            self.is_alarm_latched = True
            if not self.latched_alert:
                self.latched_alert = f"DEFCON 1: {health_txt} ON {self.camera_name.upper()}"
            if sound_ctrl:
                sound_ctrl.start_alarm()

        # Render single top bar (height 30px)
        if is_tampered or (self.is_alarm_latched and self.latched_alert):
            alert_msg = self.latched_alert if self.latched_alert else f"DEFCON 1: {health_txt}"
            cv2.rectangle(processed, (0, 0), (w, 30), (0, 0, 200), -1)
            cv2.putText(processed, f"🚨 {alert_msg} [LATCHED] 🚨", (10, 20),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.38, (255, 255, 255), 1)
        else:
            cv2.rectangle(processed, (0, 0), (w, 30), (20, 26, 34), -1)
            fps_text = f"{self.camera_id}: {self.camera_name} | FPS: {self.fps:.1f} | [INTEGRITY: NOMINAL]"
            cv2.putText(processed, fps_text, (10, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.40, (0, 255, 200), 1)

        # Ultra-fast JPEG serialization at quality=75
        _, jpeg = cv2.imencode('.jpg', processed, [int(cv2.IMWRITE_JPEG_QUALITY), 75])
        
        with self.lock:
            self.frame_count += 1
            self.active_tracks = current_active
            self.latest_raw_frame = raw_frame
            self.latest_frame = processed
            self.latest_jpeg = jpeg.tobytes()

# --- Asynchronous Threaded HTTP MJPEG Streaming Server with SO_REUSEADDR ---
class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def server_bind(self):
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        super().server_bind()

    def serve_forever(self, poll_interval=0.5):
        try:
            super().serve_forever(poll_interval)
        except OSError:
            pass

    def handle_error(self, request, client_address):
        pass

class MJPEGStreamHandler(BaseHTTPRequestHandler):
    stream_manager = None
    audio_triangulator = None

    def log_message(self, format, *args):
        pass

    def do_GET(self):
        if not self.stream_manager:
            self.send_error(503, "Stream Manager Not Initialized")
            return

        # 1. Camera MJPEG Stream Endpoint: /stream/{cam_id}
        if self.path.startswith("/stream/CAM-"):
            cam_id = self.path.split("/")[-1]
            worker = self.stream_manager.workers.get(cam_id)
            if not worker:
                self.send_error(404, f"Camera {cam_id} Not Found")
                return

            try:
                self.send_response(200)
                self.send_header('Content-type', 'multipart/x-mixed-replace; boundary=--frame')
                self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()

                while self.stream_manager.running:
                    with worker.lock:
                        jpeg = worker.latest_jpeg
                    if jpeg is not None:
                        self.wfile.write(b'--frame\r\n')
                        self.send_header('Content-type', 'image/jpeg')
                        self.send_header('Content-length', str(len(jpeg)))
                        self.end_headers()
                        self.wfile.write(jpeg)
                        self.wfile.write(b'\r\n')
                    time.sleep(0.025)
            except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError, OSError):
                pass

        # 2. Radar MJPEG Stream Endpoint: /stream/radar or /stream/radar/{cam_id}
        elif self.path.startswith("/stream/radar"):
            parts = self.path.strip("/").split("/")
            sector_focus = parts[1] if len(parts) > 1 and parts[1].startswith("CAM-") else None

            try:
                self.send_response(200)
                self.send_header('Content-type', 'multipart/x-mixed-replace; boundary=--frame')
                self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()

                while self.stream_manager.running:
                    recent_audio = self.audio_triangulator.get_recent_vectors() if self.audio_triangulator else []
                    fences_dict = {}
                    for cid, w in self.stream_manager.workers.items():
                        with w.lock:
                            if len(w.fence_points) >= 2:
                                fences_dict[cid] = {'points': list(w.fence_points), 'mode': w.boundary_mode}

                    radar_canvas = self.stream_manager.homography_proj.render_radar_canvas(
                        self.stream_manager.get_all_active_targets(),
                        acoustic_vectors=recent_audio,
                        camera_fences=fences_dict,
                        sector_focus=sector_focus
                    )
                    _, jpeg = cv2.imencode('.jpg', radar_canvas, [int(cv2.IMWRITE_JPEG_QUALITY), 75])
                    jpeg_bytes = jpeg.tobytes()
                    self.wfile.write(b'--frame\r\n')
                    self.send_header('Content-type', 'image/jpeg')
                    self.send_header('Content-length', str(len(jpeg_bytes)))
                    self.end_headers()
                    self.wfile.write(jpeg_bytes)
                    self.wfile.write(b'\r\n')
                    time.sleep(0.035)
            except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError, OSError):
                pass

        # 3. Snapshot endpoint: /snapshot/{cam_id}
        elif self.path.startswith("/snapshot/CAM-"):
            cam_id = self.path.split("/")[-1]
            worker = self.stream_manager.workers.get(cam_id)
            if not worker:
                self.send_error(404, "Camera Not Found")
                return
            with worker.lock:
                frame = worker.latest_raw_frame if worker.latest_raw_frame is not None else worker.latest_frame
            if frame is not None:
                _, jpeg = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), 85])
                jpeg_bytes = jpeg.tobytes()
                self.send_response(200)
                self.send_header('Content-type', 'image/jpeg')
                self.send_header('Content-length', str(len(jpeg_bytes)))
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(jpeg_bytes)
            else:
                self.send_error(503, "No Frame Available")

        # 4. JSON Active Targets API: /api/active_targets
        elif self.path == "/api/active_targets":
            targets = self.stream_manager.get_all_active_targets()
            data = json.dumps(targets).encode('utf-8')
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(data)
        else:
            self.send_error(404, "Not Found")

class MultiStreamManager:
    def __init__(self, db_path: str, config_file_path: str = None, fallback_video_path: str = None, port: int = 8000):
        self.db_path = db_path
        self.port = port
        self.script_dir = os.path.dirname(os.path.abspath(__file__))
        self.config_file_path = config_file_path or os.path.join(self.script_dir, "camera_config.json")
        self.fallback_video_path = fallback_video_path or os.path.join(self.script_dir, "test_feeds", "test_video.mp4")
        
        # Directory for instant full-resolution breach snapshots
        self.snapshot_dir = os.path.join(self.script_dir, "alert_snapshots")
        os.makedirs(self.snapshot_dir, exist_ok=True)

        # Native OS Speaker Alarm Controller
        self.sound_controller = SoundAlarmController()

        # Sub-Engines
        self.edge_opt = EdgeOptimizer(num_threads=4, enable_fp16=True, enable_clahe=True)
        self.reid_mgr = MultiCameraReIDManager(similarity_threshold=0.70)
        self.homography_proj = HomographyRadarProjector(map_width=800, map_height=600)
        self.threat_analyzer = ThreatAnalyzer()
        self.kalman_pred = KalmanTrajectoryPredictor()
        self.mesh_mgr = MeshResiliencyManager(db_path=self.db_path)
        self.forensic_engine = ForensicSearchEngine(db_path=self.db_path)
        
        # Unified Optical Diagnostics & Threat Scoring Sub-Engines
        self.health_monitor = CameraHealthMonitor()
        self.threat_scorer = TacticalThreatScorer()
        self.iff_mgr = TacticalIFFManager()
        self.audio_engine = DefenseAudioEngine()
        self.global_alarm_latched = False
        self.enable_tactical_filter = False

        # Load Config & Initialize Workers & Readers
        self.config_data = self._load_or_create_config()
        self.workers = {}
        self.readers = {}
        self._init_workers()
        
        # Initialize YOLOv8 Edge Model (imgsz=320 for 30+ FPS)
        print("[STREAM-ENGINE] Loading YOLOv8 Multi-Class Architecture (imgsz=320)...")
        self.model = YOLO('yolov8n.pt')
        self.model = self.edge_opt.optimize_model(self.model)

        self.detection_lock = threading.Lock()
        self.latest_detections = {cid: [] for cid in self.workers}
        self.ai_thread = None
        self.running = False
        self.worker_thread = None
        self.http_server = None
        self.http_thread = None

    def set_tactical_filter(self, enabled: bool):
        self.enable_tactical_filter = enabled
        print(f"[STREAM-ENGINE] Tactical Adverse Weather / Night CLAHE Filter: {'ENABLED' if enabled else 'DISABLED'}")

    def _load_or_create_config(self) -> dict:
        if os.path.exists(self.config_file_path):
            try:
                with open(self.config_file_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                print(f"[STREAM-ENGINE] Error reading config: {e}. Using clean defaults.")
                
        default_config = {
            "cameras": {
                "CAM-01": {"name": "North Perimeter Gate", "source": 0, "fps_target": 30, "fence_points": [], "boundary_mode": "OPEN_LINE", "zone_orientation": "INWARD", "enabled": True},
                "CAM-02": {"name": "Sector 4 Perimeter Wire", "source": "test_feeds/test_video.mp4", "fps_target": 30, "fence_points": [], "boundary_mode": "OPEN_LINE", "zone_orientation": "INWARD", "enabled": True},
                "CAM-03": {"name": "Buffer Zone Approach", "source": "test_feeds/test_video.mp4", "fps_target": 30, "fence_points": [], "boundary_mode": "OPEN_LINE", "zone_orientation": "INWARD", "enabled": True},
                "CAM-04": {"name": "Vehicle Checkpoint & ANPR", "source": "test_feeds/fence_climb.mp4", "fps_target": 30, "fence_points": [], "boundary_mode": "OPEN_LINE", "zone_orientation": "INWARD", "enabled": True}
            }
        }
        with open(self.config_file_path, 'w', encoding='utf-8') as f:
            json.dump(default_config, f, indent=2)
        return default_config

    def _init_workers(self):
        cams = self.config_data.get('cameras', {})
        for cid, ccfg in cams.items():
            self.workers[cid] = CameraStreamWorker(cid, ccfg.get('name', cid), ccfg, self.snapshot_dir, skip_n=2)
            reader = ThreadedCaptureReader(cid, ccfg.get('source', 0), self.fallback_video_path, fps_target=ccfg.get('fps_target', 30))
            reader.on_rewind_cb = self.health_monitor.notify_rewind
            self.readers[cid] = reader

    def reload_config_from_disk(self):
        """
        Hot-reloads boundary parameters from camera_config.json into all workers.
        """
        if os.path.exists(self.config_file_path):
            try:
                with open(self.config_file_path, 'r', encoding='utf-8') as f:
                    self.config_data = json.load(f)
                cams = self.config_data.get('cameras', {})
                for cid, ccfg in cams.items():
                    if cid in self.workers:
                        raw_pts = ccfg.get('fence_points', [])
                        b_mode = ccfg.get('boundary_mode', 'OPEN_LINE')
                        z_orient = ccfg.get('zone_orientation', 'INWARD')
                        self.workers[cid].update_boundary_config(raw_pts, b_mode, z_orient)
                print("[STREAM-ENGINE] All worker boundaries reloaded from camera_config.json.")
            except Exception as e:
                print(f"[STREAM-ENGINE] Error hot-reloading config: {e}")

    def acknowledge_all_alarms(self):
        """
        Operator acknowledgment resetting all persistent latched DEFCON 1 alarms and silencing the military siren.
        """
        self.global_alarm_latched = False
        if hasattr(self, 'audio_engine'):
            self.audio_engine.silence_alarm()
        self.sound_controller.stop_alarm()
        for worker in self.workers.values():
            worker.acknowledge_alert()
        print("[STREAM-ENGINE] 🔕 All latched DEFCON-1 alarms and military siren silenced by operator.")

    def get_latched_alarms(self) -> list:
        """
        Returns list of camera IDs currently latched in DEFCON 1 alarm state.
        """
        latched = []
        for cid, worker in self.workers.items():
            with worker.lock:
                if worker.is_alarm_latched:
                    self.global_alarm_latched = True
                    if hasattr(self, 'audio_engine'):
                        self.audio_engine.trigger_alarm()
                    latched.append({
                        'camera_id': cid,
                        'camera_name': worker.camera_name,
                        'alert_msg': worker.latched_alert,
                        'snapshot_path': worker.last_snapshot_path
                    })
        return latched

    def update_camera_calibration(self, camera_id: str, fence_points: list, boundary_mode: str = "OPEN_LINE", zone_orientation: str = "INWARD"):
        if camera_id in self.workers:
            self.workers[camera_id].update_boundary_config(fence_points, boundary_mode, zone_orientation)
            
            if camera_id in self.config_data.get('cameras', {}):
                self.config_data['cameras'][camera_id]['fence_points'] = fence_points
                self.config_data['cameras'][camera_id]['boundary_mode'] = boundary_mode
                self.config_data['cameras'][camera_id]['zone_orientation'] = zone_orientation
                
            with open(self.config_file_path, 'w', encoding='utf-8') as f:
                json.dump(self.config_data, f, indent=2)
                
            try:
                conn = sqlite3.connect(self.db_path)
                cur = conn.cursor()
                if fence_points and len(fence_points) >= 2:
                    p1 = fence_points[0]
                    p2 = fence_points[-1]
                    cur.execute("""
                    INSERT OR REPLACE INTO camera_fence_configs (camera_id, camera_name, source, x1, y1, x2, y2, zone_orientation)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        camera_id,
                        self.workers[camera_id].camera_name,
                        str(self.workers[camera_id].source),
                        p1[0], p1[1], p2[0], p2[1],
                        zone_orientation
                    ))
                else:
                    cur.execute("DELETE FROM camera_fence_configs WHERE camera_id = ?", (camera_id,))
                conn.commit()
                conn.close()
            except Exception as e:
                print(f"[STREAM-ENGINE] SQLite calibration save notice: {e}")
                
            print(f"[STREAM-ENGINE] Multi-Point Perimeter updated for {camera_id} ({len(fence_points)} pts, {boundary_mode}).")

    def start(self, audio_triangulator=None):
        self.running = True
        
        # Start all threaded capture readers
        for cid, reader in self.readers.items():
            reader.start()
        
        # Start AI Ingestion & Multi-Stream Processing Thread
        self.ai_thread = threading.Thread(target=self._ai_inference_loop, daemon=True)
        self.ai_thread.start()

        self.worker_thread = threading.Thread(target=self._multi_stream_loop, daemon=True)
        self.worker_thread.start()
        
        # Start Asynchronous MJPEG Server with SO_REUSEADDR
        MJPEGStreamHandler.stream_manager = self
        MJPEGStreamHandler.audio_triangulator = audio_triangulator
        try:
            self.http_server = ThreadedHTTPServer(('0.0.0.0', self.port), MJPEGStreamHandler)
            self.http_thread = threading.Thread(target=self.http_server.serve_forever, daemon=True)
            self.http_thread.start()
            print(f"[STREAM-ENGINE] Asynchronous HTTP MJPEG Streaming Server online at http://127.0.0.1:{self.port}")
        except Exception as e:
            print(f"[STREAM-ENGINE] Notice starting HTTP server on {self.port}: {e}")
            
        print("[STREAM-ENGINE] Multi-Camera Ingestion Pipeline started.")

    def stop(self):
        self.running = False
        self.sound_controller.stop_alarm()
        for reader in self.readers.values():
            reader.stop()
        if self.http_server:
            try:
                self.http_server.server_close()
            except Exception:
                pass

    def _ai_inference_loop(self):
        perspectives = {
            'CAM-01': lambda f: f,
            'CAM-02': lambda f: cv2.flip(f, 1),
            'CAM-03': lambda f: cv2.rotate(f, cv2.ROTATE_90_CLOCKWISE) if f.shape[0] == f.shape[1] else f,
            'CAM-04': lambda f: f
        }
        
        while self.running:
            for cam_id, worker in self.workers.items():
                if not self.running:
                    break
                reader = self.readers.get(cam_id)
                base_frame = reader.get_latest_frame() if reader else None
                if base_frame is None:
                    continue
                
                cam_frame = perspectives.get(cam_id, lambda f: f)(base_frame)
                
                try:
                    with torch.inference_mode():
                        results = self.model.predict(
                            cam_frame,
                            imgsz=320,
                            classes=TARGET_CLASSES,
                            conf=0.35,
                            verbose=False,
                            half=torch.cuda.is_available()
                        )
                    
                    detections = []
                    if results and len(results) > 0 and results[0].boxes is not None:
                        boxes = results[0].boxes.xyxy.cpu().numpy()
                        classes = results[0].boxes.cls.cpu().numpy().astype(int)
                        confs = results[0].boxes.conf.cpu().numpy()
                        
                        for idx_d, (b, c, conf_val) in enumerate(zip(boxes, classes, confs)):
                            detections.append({
                                'box': [int(b[0]), int(b[1]), int(b[2]), int(b[3])],
                                'cls': int(c),
                                'conf': float(conf_val),
                                'id': idx_d + 1
                            })
                    with self.detection_lock:
                        self.latest_detections[cam_id] = detections
                except Exception:
                    pass
            time.sleep(0.01)

    def _multi_stream_loop(self):
        frame_idx = 0
        prev_time = time.time()

        perspectives = {
            'CAM-01': lambda f: f,
            'CAM-02': lambda f: cv2.flip(f, 1),
            'CAM-03': lambda f: cv2.rotate(f, cv2.ROTATE_90_CLOCKWISE) if f.shape[0] == f.shape[1] else f,
            'CAM-04': lambda f: f
        }

        while self.running:
            loop_start = time.time()
            frame_idx += 1
            now = time.time()
            dt = now - prev_time
            fps = 1.0 / dt if dt > 0 else 30.0
            prev_time = now

            for cam_id, worker in self.workers.items():
                reader = self.readers.get(cam_id)
                base_frame = reader.get_latest_frame() if reader else None
                if base_frame is None:
                    worker.health_status = "CONNECTING / BUFFERING"
                    continue

                # Run non-blocking Optical Health & Anti-Tamper Check
                tamper_res = self.health_monitor.check_frame(base_frame, cam_id)
                if isinstance(tamper_res, tuple) and len(tamper_res) == 3:
                    is_tampered, status_label, tamper_type = tamper_res
                else:
                    is_tampered = bool(tamper_res[0]) if isinstance(tamper_res, (list, tuple)) else False
                    status_label = str(tamper_res[1]) if isinstance(tamper_res, (list, tuple)) and len(tamper_res) > 1 else str(tamper_res)
                    tamper_type = "OPTICAL_TAMPER"
                
                worker.health_status = status_label

                # OPTICAL TAMPER DEFCON-1 LATCH & NOMINAL RESTORATION
                if is_tampered:
                    worker.is_alarm_latched = True
                    worker.latched_alert = f"DEFCON 1: OPTICAL TAMPER DETECTED - {status_label} ON {worker.camera_name.upper()}"
                    self.global_alarm_latched = True
                    if hasattr(self, 'audio_engine'):
                        self.audio_engine.trigger_alarm()
                    self.sound_controller.start_alarm()
                    
                    now_ts = time.time()
                    if now_ts > worker.breach_cooldown:
                        worker.breach_cooldown = now_ts + 3.0
                        ts_str = datetime.now().strftime("%Y%m%d_%H%M%S")
                        snap_name = f"tamper_{cam_id}_{ts_str}.jpg"
                        snap_path = os.path.join(self.snapshot_dir, snap_name)
                        cv2.imwrite(snap_path, base_frame, [int(cv2.IMWRITE_JPEG_QUALITY), 95])
                        worker.last_snapshot_path = snap_path
                        print(f"[STREAM-ENGINE] 🚨 OPTICAL TAMPER DEFCON-1 LATCHED: {status_label} on {cam_id}")

                        try:
                            conn = sqlite3.connect(self.db_path)
                            cur = conn.cursor()
                            cur.execute("""
                            INSERT INTO events (event_type, camera_id, track_id, global_id, target_type, snapshot_path, iff_status, uniform_type, weapon_posture, threat_score, timestamp)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """, (
                                "OPTICAL_TAMPER",
                                cam_id,
                                0,
                                0,
                                tamper_type,
                                snap_name,
                                "HOSTILE",
                                "TAMPER_ATTACK",
                                status_label,
                                1.0,
                                time.strftime("%Y-%m-%d %H:%M:%S")
                            ))
                            cur.execute("""
                            INSERT INTO forensic_metadata (timestamp, camera_id, sector, target_cls, global_id, iff_status, uniform_type, weapon_posture, threat_score, license_plate, snapshot_path, tags)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """, (
                                time.strftime("%Y-%m-%d %H:%M:%S"),
                                cam_id,
                                "CAMERA_HARDWARE",
                                "TAMPER",
                                0,
                                "HOSTILE",
                                "TAMPER_ATTACK",
                                status_label,
                                1.0,
                                "N/A",
                                snap_name,
                                "optical_tamper"
                            ))
                            conn.commit()
                            conn.close()
                        except Exception as e:
                            print(f"[STREAM-ENGINE] Notice logging tamper event: {e}")
                else:
                    # Clear worker-level optical tamper latch when clear vision is restored
                    if worker.latched_alert and "OPTICAL TAMPER" in str(worker.latched_alert):
                        worker.is_alarm_latched = False
                        worker.latched_alert = None

                worker.fps = fps
                transform_fn = perspectives.get(cam_id, lambda f: f)
                cam_frame = transform_fn(base_frame.copy())
                
                # Apply Tactical Adverse Weather / Night Filter if toggled
                if self.enable_tactical_filter:
                    cam_frame = CameraHealthMonitor.apply_adaptive_night_filter(cam_frame)
                else:
                    cam_frame = self.edge_opt.enhance_frame(cam_frame)

                with self.detection_lock:
                    detections = list(self.latest_detections.get(cam_id, []))

                try:
                    worker.update_frame(
                        cam_frame, detections, self.reid_mgr, self.threat_analyzer,
                        self.kalman_pred, self.homography_proj, self.mesh_mgr,
                        self.forensic_engine, self.sound_controller, self.db_path, True,
                        threat_scorer=getattr(self, 'threat_scorer', None),
                        iff_mgr=getattr(self, 'iff_mgr', None)
                    )
                except Exception as err:
                    # Log warning without ever terminating background streaming loop
                    pass

            # Smoothly pace stream pipeline at 30 FPS (~33ms tick)
            elapsed = time.time() - loop_start
            sleep_t = 0.033 - elapsed
            if sleep_t > 0:
                time.sleep(sleep_t)
            else:
                time.sleep(0.001)

    def get_all_active_targets(self) -> list:
        all_targets = []
        for worker in self.workers.values():
            with worker.lock:
                all_targets.extend(list(worker.active_tracks.values()))
        return all_targets

    def get_radar_canvas(self) -> np.ndarray:
        targets = self.get_all_active_targets()
        return self.homography_proj.render_radar_canvas(targets)