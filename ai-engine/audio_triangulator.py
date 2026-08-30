"""
IBVAP Defense-Grade V2 - Auxiliary Audio Triangulation Engine
Simulates and detects acoustic threat signatures (Gunshots, Engine Revs, Fence Cut Vibe)
using acoustic sensor arrays. Computes bearing angle and triggers automated PTZ camera refocus.
"""
import time
import math
import random

class AudioTriangulator:
    def __init__(self):
        self.sensor_locations = [
            {'id': 'MIC-A', 'pos': (100, 100)},
            {'id': 'MIC-B', 'pos': (700, 100)},
            {'id': 'MIC-C', 'pos': (400, 500)}
        ]
        self.last_event = None
        self.last_event_time = 0
        print("[AUDIO-TRIANGULATOR] Acoustic Sensor Array listening.")

    def trigger_synthetic_anomaly(self, threat_type: str = "GUNSHOT", azimuth: float = None) -> dict:
        if azimuth is None:
            azimuth = random.uniform(30.0, 150.0)
            
        freq_profiles = {
            'GUNSHOT': {'peak_hz': 2400, 'spl_db': 142, 'priority': 'CRITICAL'},
            'ENGINE_ACCEL': {'peak_hz': 180, 'spl_db': 98, 'priority': 'ELEVATED'},
            'FENCE_VIBRATION': {'peak_hz': 850, 'spl_db': 105, 'priority': 'HIGH'},
            'DRONE_ROTOR': {'peak_hz': 4200, 'spl_db': 88, 'priority': 'WARNING'}
        }
        profile = freq_profiles.get(threat_type, freq_profiles['GUNSHOT'])
        
        if azimuth < 70:
            slew_cam = 'CAM-01'
        elif azimuth < 110:
            slew_cam = 'CAM-02'
        else:
            slew_cam = 'CAM-03'
            
        event = {
            'timestamp': time.strftime("%H:%M:%S"),
            'type': threat_type,
            'azimuth': round(azimuth, 1),
            'peak_hz': profile['peak_hz'],
            'spl_db': profile['spl_db'],
            'priority': profile['priority'],
            'ptz_cue_camera': slew_cam,
            'ptz_pan_angle': round(azimuth - 90.0, 1)
        }
        self.last_event = event
        self.last_event_time = time.time()
        return event

    def get_recent_vectors(self) -> list:
        if self.last_event and (time.time() - self.last_event_time) < 15.0:
            return [{
                'source_pos': (400, 250),
                'azimuth': self.last_event['azimuth'],
                'type': self.last_event['type']
            }]
        return []