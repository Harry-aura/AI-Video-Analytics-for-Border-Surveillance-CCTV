"""
IBVAP Defense-Grade V2 - Tactical IFF (Identification Friend or Foe) & Multi-Class Patrol Discrimination Engine
Features:
1. Strict Class Isolation Gate:
   - Evaluates target appearance embeddings ONLY against enrolled gallery items with matching semantic class label.
   - Prevents cross-class leakage (vehicles never match humans, cars never match trucks).
2. Tightened Defense-Grade Similarity Threshold (>= 0.78):
   - Computes Cosine Similarity Sim(E_target, F_k) >= 0.78 for positive friendly verification.
3. Directional Ingress vs. Egress Vector Cross-Product Analysis.
4. Scheduled Patrol Window Bypass for authorized sweep windows.
"""
import time
import math
import numpy as np

class TacticalIFFManager:
    def __init__(self, similarity_threshold: float = 0.78):
        self.similarity_threshold = similarity_threshold
        self.friendly_gallery = {}  # {patrol_id: {'embedding': np.ndarray, 'label': str, 'class_name': str, 'enrolled_at': float}}
        self.patrol_mode_active = False
        self.next_patrol_id = 1
        print(f"[IFF-ENGINE] Tactical IFF Multi-Class Engine online (Gated Similarity Threshold: {self.similarity_threshold:.2f}).")

    def enroll_friendly(self, embedding: np.ndarray, label: str = "BSF PATROL", class_name: str = "PERSON") -> str:
        """
        Enrolls a verified feature vector into the Friendly Patrol Whitelist with strict semantic class binding.
        """
        if embedding is None or not isinstance(embedding, np.ndarray) or embedding.size == 0:
            return ""
        
        # Ensure L2 normalization
        norm = np.linalg.norm(embedding)
        if norm > 1e-6:
            norm_emb = (embedding / norm).astype(np.float32)
        else:
            norm_emb = embedding.astype(np.float32)

        c_name = class_name.strip().upper() if class_name else "PERSON"
        pid = f"PATROL-{self.next_patrol_id:03d}"
        self.next_patrol_id += 1
        self.friendly_gallery[pid] = {
            'embedding': norm_emb,
            'label': label,
            'class_name': c_name,
            'enrolled_at': time.time()
        }
        print(f"[IFF-ENGINE] 🛡️ Friendly signature enrolled: {pid} [{c_name}] ({label})")
        return pid

    def clear_whitelist(self):
        """Clears all enrolled friendly signatures."""
        self.friendly_gallery.clear()
        print("[IFF-ENGINE] Friendly Patrol Whitelist cleared.")

    def get_friendly_count(self) -> int:
        """Returns total number of enrolled friendly signatures."""
        return len(self.friendly_gallery)

    def set_patrol_mode(self, active: bool):
        """Activates or deactivates the Scheduled Friendly Patrol Window."""
        self.patrol_mode_active = bool(active)
        state = "ACTIVE (Alarms Suppressed for Sweeps)" if self.patrol_mode_active else "STANDBY (Full Enforcement)"
        print(f"[IFF-ENGINE] Scheduled Patrol Window Mode: {state}")

    def is_patrol_mode_active(self) -> bool:
        """Checks if patrol mode is currently active."""
        return self.patrol_mode_active

    def match_friendly(self, embedding: np.ndarray, target_class: str = "PERSON", threshold: float = None) -> tuple[bool, float, str]:
        """
        Calculates maximum Cosine Similarity between target embedding and enrolled friendly gallery
        ONLY for gallery items with matching semantic class label.
        
        Sim(E_target, F_k) = (E_target . F_k) / (||E_target|| * ||F_k||)
        Returns: (is_friendly: bool, max_sim: float, label: str)
        """
        thresh = threshold if threshold is not None else self.similarity_threshold
        if not self.friendly_gallery or embedding is None or not isinstance(embedding, np.ndarray) or embedding.size == 0:
            return False, 0.0, "UNVERIFIED"

        tgt_cls = target_class.strip().upper() if target_class else "PERSON"

        norm_t = np.linalg.norm(embedding)
        if norm_t < 1e-6:
            return False, 0.0, "UNVERIFIED"
        e_norm = (embedding / norm_t).astype(np.float32)

        best_sim = -1.0
        best_label = "UNVERIFIED"

        for pid, data in self.friendly_gallery.items():
            # STRICT CLASS ISOLATION GATE: Only compare against same class
            if data.get('class_name', 'PERSON') != tgt_cls:
                continue

            f_emb = data['embedding']
            sim = float(np.dot(e_norm, f_emb))
            if sim > best_sim:
                best_sim = sim
                best_label = data['label']

        is_friendly = (best_sim >= thresh)
        return is_friendly, max(0.0, round(best_sim, 3)), (best_label if is_friendly else "UNVERIFIED")

    @staticmethod
    def evaluate_directional_vector(p1: tuple, p2: tuple, velocity_vec: tuple,
                                    zone_orientation: str = "INWARD") -> dict:
        """
        Calculates 2D Cross Product between boundary line segment P1->P2 and motion vector V=(dx, dy):
        Cross Product CP = (x2 - x1)*dy - (y2 - y1)*dx
        """
        if not p1 or not p2 or not velocity_vec:
            return {'direction': 'INGRESS', 'is_ingress': True, 'cross_product': 1.0}

        x1, y1 = float(p1[0]), float(p1[1])
        x2, y2 = float(p2[0]), float(p2[1])
        dx, dy = float(velocity_vec[0]), float(velocity_vec[1])

        # Directional Cross Product
        cp = (x2 - x1) * dy - (y2 - y1) * dx

        if zone_orientation == "OUTWARD":
            cp = -cp

        speed = math.hypot(dx, dy)
        if speed < 0.25:
            is_ingress = True
            direction = "INGRESS (STATIC)"
        elif cp > 0:
            is_ingress = True
            direction = "INGRESS"
        else:
            is_ingress = False
            direction = "EGRESS (OUTBOUND)"

        return {
            'direction': direction,
            'is_ingress': is_ingress,
            'cross_product': round(cp, 2)
        }

    def evaluate_target(self, target_id: int, embedding: np.ndarray, velocity_vec: tuple,
                        segment: tuple = None, zone_orientation: str = "INWARD",
                        target_class: str = "PERSON") -> dict:
        """
        Comprehensive target assessment with Strict Class Isolation and Tightened Similarity Gating (>= 0.78).
        """
        # 1. Cosine Similarity Whitelist Match with Strict Class Gate
        is_friendly, sim_score, friendly_label = self.match_friendly(embedding, target_class=target_class)

        # 2. Directional Ingress / Egress Validation
        if segment and len(segment) == 2:
            dir_info = self.evaluate_directional_vector(segment[0], segment[1], velocity_vec, zone_orientation)
        else:
            dir_info = {'direction': 'INGRESS', 'is_ingress': True, 'cross_product': 1.0}

        # 3. Scheduled Patrol Window State
        patrol_window = self.patrol_mode_active
        tgt_cls_norm = target_class.strip().upper() if target_class else "PERSON"

        # 4. Final IFF Classification & Alarm Suppression Decision (Zero-Tolerance Enforcement)
        if is_friendly:
            iff_status = "FRIENDLY"
            suppress_alarm = True
            is_breach = False
            reason = f"Enrolled Whitelist Match [{tgt_cls_norm}] ({friendly_label}, Sim={sim_score:.2f} >= 0.78)"
            hud_label = f"#{target_id} FRIENDLY - {friendly_label}"
            badge = "🛡️ FRIENDLY"
            badge_color = "#52c41a"
        elif patrol_window and tgt_cls_norm in ["PERSON", "HUMAN", "CRAWLING_INFILTRATOR"]:
            iff_status = "FRIENDLY"
            suppress_alarm = True
            is_breach = False
            reason = "Scheduled Patrol Window Active (Authorized Human Patrol Sweep)"
            hud_label = f"#{target_id} FRIENDLY - BSF PATROL"
            badge = "🛡️ FRIENDLY (PATROL WINDOW)"
            badge_color = "#13c2c2"
        else:
            # STRICT ZERO-TOLERANCE ENFORCEMENT: Any unverified boundary crossing triggers Hostile Breach
            iff_status = "HOSTILE"
            suppress_alarm = False
            is_breach = True
            reason = f"Unverified {tgt_cls_norm} (Sim={sim_score:.2f} < 0.78)"
            hud_label = f"#{target_id} HOSTILE - BREACH"
            badge = "🔴 HOSTILE"
            badge_color = "#ff4d4f"

        return {
            'target_id': target_id,
            'target_class': tgt_cls_norm,
            'iff_status': iff_status,
            'is_friendly': is_friendly,
            'is_breach': is_breach,
            'similarity_score': sim_score,
            'friendly_label': friendly_label,
            'direction': dir_info['direction'],
            'is_ingress': dir_info['is_ingress'],
            'cross_product': dir_info['cross_product'],
            'patrol_mode_active': patrol_window,
            'suppress_alarm': suppress_alarm,
            'reason': reason,
            'hud_label': hud_label,
            'badge': badge,
            'badge_color': badge_color
        }
