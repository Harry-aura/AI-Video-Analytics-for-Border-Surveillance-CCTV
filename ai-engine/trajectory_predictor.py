"""
IBVAP Defense-Grade V2 - Predictive Intrusion Trajectory Engine
Uses Kalman filter state estimation (x, y, vx, vy) to compute velocity vectors,
extrapolate future perimeter breach paths (+2s, +5s, +10s), and compute Time-to-Breach (TTB).
"""
import numpy as np
import math

class KalmanTrajectoryPredictor:
    def __init__(self, dt: float = 1.0 / 30.0):
        self.dt = dt
        self.tracks = {}  # {track_id: {'kf': dict, 'history': []}}

    def init_filter(self, init_x: float, init_y: float) -> dict:
        state = np.array([[init_x], [init_y], [0.0], [0.0]], dtype=np.float32)
        F = np.array([
            [1.0, 0.0, self.dt, 0.0],
            [0.0, 1.0, 0.0, self.dt],
            [0.0, 0.0, 1.0, 0.0],
            [0.0, 0.0, 0.0, 1.0]
        ], dtype=np.float32)
        H = np.array([
            [1.0, 0.0, 0.0, 0.0],
            [0.0, 1.0, 0.0, 0.0]
        ], dtype=np.float32)
        P = np.eye(4, dtype=np.float32) * 50.0
        Q = np.eye(4, dtype=np.float32) * 2.0
        R = np.eye(2, dtype=np.float32) * 10.0
        return {'state': state, 'F': F, 'H': H, 'P': P, 'Q': Q, 'R': R}

    def update(self, track_id: int, measured_x: float, measured_y: float) -> tuple[float, float, float, float]:
        if track_id not in self.tracks:
            self.tracks[track_id] = self.init_filter(measured_x, measured_y)
            
        kf = self.tracks[track_id]
        # Predict
        kf['state'] = np.dot(kf['F'], kf['state'])
        kf['P'] = np.dot(np.dot(kf['F'], kf['P']), kf['F'].T) + kf['Q']
        
        # Update / Correct
        z = np.array([[measured_x], [measured_y]], dtype=np.float32)
        y = z - np.dot(kf['H'], kf['state'])
        S = np.dot(np.dot(kf['H'], kf['P']), kf['H'].T) + kf['R']
        K = np.dot(np.dot(kf['P'], kf['H'].T), np.linalg.inv(S))
        
        kf['state'] = kf['state'] + np.dot(K, y)
        kf['P'] = np.dot(np.eye(4) - np.dot(K, kf['H']), kf['P'])
        
        x = float(kf['state'][0, 0])
        y = float(kf['state'][1, 0])
        vx = float(kf['state'][2, 0])
        vy = float(kf['state'][3, 0])
        return x, y, vx, vy

    def update_track(self, track_id: int, curr_foot: tuple) -> tuple[float, float]:
        """Updates Kalman tracker with foot coordinate and appends history."""
        fx = float(curr_foot[0]) if isinstance(curr_foot, (tuple, list)) else 0.0
        fy = float(curr_foot[1]) if isinstance(curr_foot, (tuple, list)) else 0.0
        _, _, vx, vy = self.update(track_id, fx, fy)
        
        if track_id not in self.tracks:
            self.tracks[track_id] = {'history': []}
        if 'history' not in self.tracks[track_id]:
            self.tracks[track_id]['history'] = []
            
        self.tracks[track_id]['history'].append((int(fx), int(fy)))
        if len(self.tracks[track_id]['history']) > 25:
            self.tracks[track_id]['history'].pop(0)
        return vx, vy

    def get_history(self, track_id: int) -> list:
        """Returns coordinate breadcrumb history for a track."""
        if track_id in self.tracks and 'history' in self.tracks[track_id]:
            return self.tracks[track_id]['history']
        return []

    def predict_future_path(self, track_id: int, horizon_seconds: list = [2.0, 5.0, 10.0]) -> list:
        if track_id not in self.tracks:
            return []
        kf = self.tracks[track_id]
        cur_x = float(kf['state'][0, 0])
        cur_y = float(kf['state'][1, 0])
        vx = float(kf['state'][2, 0])
        vy = float(kf['state'][3, 0])
        
        predicted_points = []
        for t in horizon_seconds:
            pred_x = cur_x + vx * (t / self.dt) * 0.05
            pred_y = cur_y + vy * (t / self.dt) * 0.05
            predicted_points.append((int(pred_x), int(pred_y), t))
        return predicted_points

    def compute_time_to_breach(self, current_pos: tuple, velocity: tuple, fence_line: list) -> float:
        x, y = current_pos
        vx, vy = velocity
        v_speed = math.hypot(vx, vy)
        if v_speed < 0.2:
            return 999.0
            
        min_dist = 999.0
        for i in range(len(fence_line) - 1):
            p1 = fence_line[i]
            p2 = fence_line[i+1]
            px = p2[0] - p1[0]
            py = p2[1] - p1[1]
            u = max(0, min(1, ((x - p1[0]) * px + (y - p1[1]) * py) / float(px*px + py*py + 1e-6)))
            dx = p1[0] + u * px - x
            dy = p1[1] + u * py - y
            dist = math.hypot(dx, dy)
            if dist < min_dist:
                min_dist = dist
                
        ttb = min_dist / (v_speed * 15.0 + 1e-5)
        return round(max(0.1, ttb), 1)