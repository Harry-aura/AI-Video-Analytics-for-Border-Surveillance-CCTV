"""
IBVAP Defense-Grade V2 - Multi-Camera Tracking & Re-ID (MC-MTT)
Mandate 1: Decouples deep Re-ID embedding extraction from every frame.
Uses fast spatial tracking (IoU + Kalman) on every frame and triggers deep Re-ID
embeddings only upon track initialization, sector transitions, or periodic verification.
Maintains a global multi-camera gallery using cosine similarity.
"""
import cv2
import numpy as np
import time
import math
import torch
import torch.nn as nn
from sklearn.metrics.pairwise import cosine_similarity

class LightweightReIDNet(nn.Module):
    """
    MobileNet-style lightweight deep feature extractor producing 128-dim normalized embedding.
    """
    def __init__(self, embedding_dim: int = 128):
        super().__init__()
        self.features = nn.Sequential(
            nn.Conv2d(3, 32, kernel_size=3, stride=2, padding=1),
            nn.BatchNorm2d(32),
            nn.ReLU6(inplace=True),
            nn.Conv2d(32, 64, kernel_size=3, stride=2, padding=1),
            nn.BatchNorm2d(64),
            nn.ReLU6(inplace=True),
            nn.Conv2d(64, 128, kernel_size=3, stride=2, padding=1),
            nn.BatchNorm2d(128),
            nn.ReLU6(inplace=True),
            nn.AdaptiveAvgPool2d((1, 1))
        )
        self.fc = nn.Linear(128, embedding_dim)

    def forward(self, x):
        feat = self.features(x)
        feat = torch.flatten(feat, 1)
        emb = self.fc(feat)
        norm = torch.norm(emb, p=2, dim=1, keepdim=True).clamp(min=1e-12)
        return emb / norm

class MultiCameraReIDManager:
    def __init__(self, similarity_threshold: float = 0.70, reid_interval: int = 45):
        self.similarity_threshold = similarity_threshold
        self.reid_interval = reid_interval
        self.global_gallery = {}  # {global_id: {'embedding': np.array, 'last_seen': float, 'last_cam': str, 'cls': int, 'history': []}}
        self.next_global_id = 101
        
        # Initialize Re-ID model
        self.model = LightweightReIDNet(embedding_dim=128)
        self.model.eval()
        
        # Camera-to-Camera Spatio-Temporal transition matrix (min_time, max_time in seconds)
        self.transition_matrix = {
            ('CAM-01', 'CAM-02'): (0.5, 45.0),
            ('CAM-02', 'CAM-01'): (0.5, 45.0),
            ('CAM-02', 'CAM-03'): (0.5, 45.0),
            ('CAM-03', 'CAM-02'): (0.5, 45.0),
            ('CAM-03', 'CAM-04'): (0.5, 45.0),
            ('CAM-04', 'CAM-03'): (0.5, 45.0),
        }
        print("[REID-ENGINE] Multi-Camera Re-ID Engine initialized (Decoupled Mode).")

    def extract_embedding(self, crop: np.ndarray) -> np.ndarray:
        """
        Extracts L2-normalized 128-dimensional appearance vector from bounding box crop.
        Combines deep features (96 dims) with HSV color histogram (32 dims).
        """
        if crop is None or crop.size == 0 or crop.shape[0] < 10 or crop.shape[1] < 10:
            return np.zeros(128, dtype=np.float32)
            
        try:
            resized = cv2.resize(crop, (64, 128))
            rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)
            tensor = torch.from_numpy(rgb).permute(2, 0, 1).float() / 255.0
            tensor = tensor.unsqueeze(0)
            
            with torch.no_grad():
                deep_emb = self.model(tensor).cpu().numpy()[0]
                
            # Compute 32-bin HSV color histogram component
            hsv = cv2.cvtColor(resized, cv2.COLOR_BGR2HSV)
            hist_h = cv2.calcHist([hsv], [0], None, [16], [0, 180])
            hist_s = cv2.calcHist([hsv], [1], None, [16], [0, 256])
            color_hist = np.concatenate([hist_h.flatten(), hist_s.flatten()])
            color_hist = color_hist / (np.linalg.norm(color_hist) + 1e-6)
            
            # Fuse deep embedding (96 dims) + color histogram (32 dims)
            fused = np.concatenate([deep_emb[:96], color_hist])
            fused = fused / (np.linalg.norm(fused) + 1e-6)
            return fused.astype(np.float32)
        except Exception as e:
            return np.zeros(128, dtype=np.float32)

    def match_or_register_global_id(self, local_track_id: int, camera_id: str, crop: np.ndarray = None, target_cls: int = 0, embedding: np.ndarray = None) -> int:
        """
        MANDATE 1: Matches track crop against global gallery using cosine similarity.
        If matched, returns existing Global Target ID. Otherwise registers a new Global Target ID.
        """
        if embedding is None:
            embedding = self.extract_embedding(crop) if crop is not None else np.zeros(128, dtype=np.float32)
        current_time = time.time()
        
        best_match_id = None
        highest_sim = -1.0
        
        for gid, gdata in list(self.global_gallery.items()):
            # Target class must match
            if gdata['cls'] != target_cls:
                continue
                
            # Spatio-temporal feasibility check
            time_delta = current_time - gdata['last_seen']
            prev_cam = gdata['last_cam']
            if prev_cam != camera_id:
                trans_rule = self.transition_matrix.get((prev_cam, camera_id), (0.2, 60.0))
                if not (trans_rule[0] <= time_delta <= trans_rule[1]):
                    continue
            else:
                if time_delta > 15.0:
                    continue
                    
            sim = float(np.dot(embedding, gdata['embedding']))
            if sim > highest_sim and sim >= self.similarity_threshold:
                highest_sim = sim
                best_match_id = gid

        if best_match_id is not None:
            # Update moving average embedding in gallery
            gdata = self.global_gallery[best_match_id]
            gdata['embedding'] = 0.85 * gdata['embedding'] + 0.15 * embedding
            gdata['embedding'] = gdata['embedding'] / (np.linalg.norm(gdata['embedding']) + 1e-6)
            gdata['last_seen'] = current_time
            gdata['last_cam'] = camera_id
            gdata['history'].append({'cam': camera_id, 'time': current_time, 'sim': round(highest_sim, 3)})
            return best_match_id
        else:
            # Register new global target ID
            new_gid = self.next_global_id
            self.next_global_id += 1
            self.global_gallery[new_gid] = {
                'embedding': embedding,
                'last_seen': current_time,
                'last_cam': camera_id,
                'cls': target_cls,
                'history': [{'cam': camera_id, 'time': current_time, 'sim': 1.0}]
            }
            return new_gid

    def associate_global_track(self, camera_id: str, local_track_id: int, target_cls: int,
                               embedding: np.ndarray = None, curr_foot: tuple = None,
                               is_inference_frame: bool = True) -> int:
        """
        Universal wrapper for global track association.
        """
        return self.match_or_register_global_id(
            local_track_id=local_track_id,
            camera_id=camera_id,
            crop=None,
            target_cls=target_cls,
            embedding=embedding
        )

    def cleanup_old_identities(self, max_age_seconds: float = 120.0):
        now = time.time()
        expired = [gid for gid, data in self.global_gallery.items() if (now - data['last_seen']) > max_age_seconds]
        for gid in expired:
            del self.global_gallery[gid]