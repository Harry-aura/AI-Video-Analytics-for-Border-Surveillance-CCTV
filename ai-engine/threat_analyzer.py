"""
IBVAP Defense-Grade V2 - Multi-Class Tactical Threat Analyzer, Posture Recognition & Animal Bypass Engine
Features:
1. Target Class Categorization:
   - Mechanized & Aerial: CAR, TRUCK, BUS, MOTORCYCLE, BICYCLE, DRONE_UAV.
   - Human Targets: PERSON, DISGUISED_HUMAN, CRAWLING_INFILTRATOR.
   - Wildlife & Livestock: BIRD, CAT, DOG, HORSE, SHEEP, COW, ELEPHANT, BEAR, ANIMAL.
2. Human Posture & Kinematic Velocity Analysis (Aspect Ratio + Speed km/h):
   - AR >= 1.30 and V > 0.5 km/h -> [CRAWLING / PRONE]
   - AR < 1.30 and V > 12.0 km/h -> [RUNNING / SPRINT]
   - AR < 1.30 and V <= 12.0 km/h -> [WALKING / PATROL]
3. Animal Fence-Crossing Bypass (Zero-False-Alarm Rule):
   - Suppresses DEFCON 1 siren latch for biological animals (dog, cat, cow, sheep, horse, bird, etc.).
   - Renders in Yellow/Gray as NON-THREAT. Logs silently as INFO_WILDLIFE_TRANSIT.
4. Optical Shadow & Noise Elimination via Laplacian Texture Variance.
"""
import cv2
import math
import numpy as np

VEHICLE_CLASSES = {
    1: "BICYCLE",
    2: "CAR",
    3: "MOTORCYCLE",
    5: "BUS",
    7: "TRUCK"
}

AERIAL_CLASSES = {
    4: "DRONE_UAV"  # Airplane / Drone
}

WILDLIFE_CLASSES = {
    14: "BIRD",
    15: "CAT",
    16: "DOG",
    17: "HORSE",
    18: "SHEEP",
    19: "COW",
    20: "ELEPHANT",
    21: "BEAR"
}

CLASS_TAXONOMY = {
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

class ThreatAnalyzer:
    def __init__(self):
        print("[THREAT-ANALYZER] Multi-Class Tactical Threat & Posture Engine online.")

    def classify_threat(self, crop: np.ndarray, cls_id: int, camera_id: str = None,
                        bbox: list = None, velocity_mag: float = 0.0) -> dict:
        return self.analyze_target_threat(crop=crop, cls_id=cls_id, bbox=bbox, velocity_mag=velocity_mag)

    def classify(self, crop: np.ndarray, cls_id: int, camera_id: str = None) -> dict:
        return self.analyze_target_threat(crop=crop, cls_id=cls_id)

    def analyze(self, crop: np.ndarray, cls_id: int, camera_id: str = None) -> dict:
        return self.analyze_target_threat(crop=crop, cls_id=cls_id)

    def get_threat_level(self, crop: np.ndarray, cls_id: int) -> dict:
        return self.analyze_target_threat(crop=crop, cls_id=cls_id)

    def is_planar_shadow(self, crop: np.ndarray) -> bool:
        """
        Detects if a detected bounding box is merely a planar optical ground shadow.
        Shadows lack internal high-frequency edge texture and color saturation.
        """
        if crop is None or crop.size == 0 or crop.shape[0] < 8 or crop.shape[1] < 8:
            return True

        gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
        laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()

        hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
        sat_mean = np.mean(hsv[:, :, 1])
        val_mean = np.mean(hsv[:, :, 2])

        # Planar shadow heuristic: low texture energy (< 30.0) with low saturation and low luminance
        if laplacian_var < 30.0 and sat_mean < 35.0 and val_mean < 80.0:
            return True
        return False

    def estimate_human_posture(self, aspect_ratio: float, velocity_kmh: float, crop: np.ndarray = None) -> str:
        """
        Calculates human posture classification based on Aspect Ratio (W/H) and Velocity (km/h):
        - AR >= 1.30 and V > 0.5 km/h -> CRAWLING / PRONE
        - AR < 1.30 and V > 12.0 km/h -> RUNNING / SPRINT
        - AR < 1.30 and V <= 12.0 km/h -> WALKING / PATROL
        """
        if aspect_ratio >= 1.30:
            if velocity_kmh > 0.5:
                return "CRAWLING / PRONE"
            else:
                return "PRONE / STATIONARY"
        elif velocity_kmh > 12.0:
            return "RUNNING / SPRINT"
        elif velocity_kmh > 0.8:
            return "WALKING / PATROL"
        else:
            return "STANDING / LOITERING"

    def analyze_target_threat(self, crop: np.ndarray, cls_id: int, bbox: list = None,
                              velocity_mag: float = 0.0) -> dict:
        """
        Comprehensive Multi-Class Tactical Threat & Posture Evaluation.
        """
        w = max(1, bbox[2] - bbox[0]) if bbox else 64
        h = max(1, bbox[3] - bbox[1]) if bbox else 128
        aspect_ratio = float(w) / float(h)
        
        # Velocity in km/h (normalized pixel velocity mapped to real-world velocity)
        # e.g., 1.0 px/frame at 30 fps ~= 3.6 km/h
        velocity_kmh = round(max(0.0, velocity_mag * 3.6), 1)

        # 1. Shadow Verification
        if self.is_planar_shadow(crop):
            return {
                'target_category': 'OPTICAL_SHADOW',
                'raw_class': 'SHADOW',
                'posture': 'NONE',
                'velocity_kmh': velocity_kmh,
                'iff_status': 'NOISE_SUPPRESSED',
                'uniform_type': 'SHADOW',
                'weapon_posture': 'NONE',
                'threat_score': 0.05,
                'is_threat': False,
                'is_animal': False,
                'defcon_level': 3,
                'hud_posture_label': '[SHADOW]'
            }

        # 2. Aerial Drone / UAV Threat
        if cls_id in AERIAL_CLASSES or (cls_id == 0 and bbox and bbox[1] < 100 and aspect_ratio > 1.4 and velocity_kmh > 15.0):
            return {
                'target_category': 'DRONE_UAV',
                'raw_class': 'DRONE_UAV',
                'posture': 'AERIAL RECON',
                'velocity_kmh': velocity_kmh,
                'iff_status': 'HOSTILE',
                'uniform_type': 'AERIAL_DRONE',
                'weapon_posture': 'AIRBORNE_SURVEILLANCE',
                'threat_score': 0.95,
                'is_threat': True,
                'is_animal': False,
                'defcon_level': 1,
                'hud_posture_label': '[AERIAL RECON]'
            }

        # 3. Mechanized Vehicles (Cars, Trucks, Buses)
        if cls_id in [2, 5, 7]:
            vtype = VEHICLE_CLASSES.get(cls_id, "VEHICLE")
            posture = "IN MOTION (RAPID)" if velocity_kmh > 20.0 else ("APPROACHING" if velocity_kmh > 1.0 else "STATIONARY")
            return {
                'target_category': vtype,
                'raw_class': vtype,
                'posture': posture,
                'velocity_kmh': velocity_kmh,
                'iff_status': 'HOSTILE',
                'uniform_type': f'HEAVY_{vtype}',
                'weapon_posture': 'VEHICULAR_APPROACH',
                'threat_score': 0.90,
                'is_threat': True,
                'is_animal': False,
                'defcon_level': 1,
                'hud_posture_label': f'[{posture}]'
            }

        # 4. Light Vehicles (Motorcycles, Scooters, Bicycles)
        if cls_id == 3:  # Motorcycle
            posture = "FAST APPROACH" if velocity_kmh > 15.0 else "IN TRANSIT"
            return {
                'target_category': 'MOTORCYCLE',
                'raw_class': 'MOTORCYCLE',
                'posture': posture,
                'velocity_kmh': velocity_kmh,
                'iff_status': 'HOSTILE',
                'uniform_type': 'RAPID_TRANSIT_VEHICLE',
                'weapon_posture': 'FAST_APPROACH',
                'threat_score': 0.88,
                'is_threat': True,
                'is_animal': False,
                'defcon_level': 1,
                'hud_posture_label': f'[{posture}]'
            }

        if cls_id == 1:  # Bicycle
            posture = "PEDALING / MOVING" if velocity_kmh > 2.0 else "STATIONARY"
            return {
                'target_category': 'BICYCLE',
                'raw_class': 'BICYCLE',
                'posture': posture,
                'velocity_kmh': velocity_kmh,
                'iff_status': 'SUSPICIOUS',
                'uniform_type': 'LIGHT_TRANSIT',
                'weapon_posture': 'BUFFER_ZONE_APPROACH',
                'threat_score': 0.65,
                'is_threat': True,
                'is_animal': False,
                'defcon_level': 2,
                'hud_posture_label': f'[{posture}]'
            }

        # 5. Wildlife & Livestock (Harmless Animals - Zero False Alarm Rule)
        if cls_id in WILDLIFE_CLASSES:
            animal_name = WILDLIFE_CLASSES[cls_id]
            posture = "GRAZING / MOVING" if velocity_kmh > 1.0 else "STATIONARY"
            return {
                'target_category': f'ANIMAL_{animal_name}',
                'raw_class': animal_name,
                'posture': posture,
                'velocity_kmh': velocity_kmh,
                'iff_status': 'NEUTRAL_WILDLIFE',
                'uniform_type': 'BIOLOGICAL_ANIMAL',
                'weapon_posture': 'NONE',
                'threat_score': 0.12,
                'is_threat': False,
                'is_animal': True,
                'defcon_level': 3,
                'hud_posture_label': f'[{animal_name} - NON-THREAT]'
            }

        # 6. Human Targets / Infiltrators (cls_id == 0 or unknown human entity)
        human_posture = self.estimate_human_posture(aspect_ratio, velocity_kmh, crop)
        
        # Check tactical uniform appearance
        uniform_type = "STANDARD_PERSONNEL"
        threat_score = 0.85
        if crop is not None and crop.size > 0:
            hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
            val_mean = np.mean(hsv[:, :, 2])
            sat_mean = np.mean(hsv[:, :, 1])
            if val_mean < 85 and sat_mean < 70:
                uniform_type = "TACTICAL_DARK_GEAR"
                threat_score = 0.95
            elif sat_mean > 90:
                uniform_type = "CIVILIAN_HIGH_VIS"
                threat_score = 0.75

        # If prone/crawling, elevate threat
        if "CRAWLING" in human_posture or "PRONE" in human_posture:
            target_category = "CRAWLING_INFILTRATOR"
            threat_score = 0.96
        else:
            target_category = "PERSON"

        return {
            'target_category': target_category,
            'raw_class': 'PERSON',
            'posture': human_posture,
            'velocity_kmh': velocity_kmh,
            'iff_status': 'HOSTILE',
            'uniform_type': uniform_type,
            'weapon_posture': 'PERIMETER_PROXIMITY',
            'threat_score': threat_score,
            'is_threat': True,
            'is_animal': False,
            'defcon_level': 1,
            'hud_posture_label': f'[{human_posture}]'
        }