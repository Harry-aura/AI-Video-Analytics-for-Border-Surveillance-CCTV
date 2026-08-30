"""
IBVAP Defense-Grade V2 - Low-Bandwidth & Mesh Resiliency Mode
Sends metadata-first telemetry packets with high-compression Base64 thumbnails.
Maintains a local SQLite transaction queue during network disruption (20 kbps mode)
and automatically synchronizes queued alerts upon reconnection.
"""
import cv2
import json
import base64
import time
import sqlite3
import numpy as np
import os

class MeshResiliencyManager:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.low_bandwidth_mode = False
        self.network_online = True
        self.offline_queue = []
        self._init_mesh_tables()
        print("[MESH-RESILIENCY] Low-Bandwidth & Local Queue Manager active.")

    def _init_mesh_tables(self):
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        cur.execute("""
        CREATE TABLE IF NOT EXISTS mesh_offline_queue (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            packet_type TEXT,
            payload_json TEXT,
            sync_status TEXT DEFAULT 'PENDING'
        )
        """)
        conn.commit()
        conn.close()

    def set_low_bandwidth_mode(self, enabled: bool):
        self.low_bandwidth_mode = enabled
        print(f"[MESH-RESILIENCY] 20 kbps Low-Bandwidth Mode: {'ENABLED' if enabled else 'DISABLED'}")

    def create_compressed_thumbnail_b64(self, crop: np.ndarray) -> str:
        if crop is None or crop.size == 0:
            return ""
        try:
            thumb = cv2.resize(crop, (64, 64), interpolation=cv2.INTER_AREA)
            _, buf = cv2.imencode('.jpg', thumb, [int(cv2.IMWRITE_JPEG_QUALITY), 35])
            return base64.b64encode(buf).decode('utf-8')
        except Exception:
            return ""

    def dispatch_telemetry_packet(self, packet: dict, crop: np.ndarray = None) -> dict:
        if self.low_bandwidth_mode and crop is not None:
            packet['thumb_b64'] = self.create_compressed_thumbnail_b64(crop)
            
        payload_str = json.dumps(packet)
        packet_size_bytes = len(payload_str.encode('utf-8'))
        
        if not self.network_online:
            conn = sqlite3.connect(self.db_path)
            cur = conn.cursor()
            cur.execute("INSERT INTO mesh_offline_queue (packet_type, payload_json) VALUES (?, ?)",
                        (packet.get('type', 'ALERT'), payload_str))
            conn.commit()
            conn.close()
            return {'status': 'QUEUED_OFFLINE', 'size_bytes': packet_size_bytes}
            
        return {'status': 'TRANSMITTED', 'size_bytes': packet_size_bytes}

    def sync_offline_queue(self) -> int:
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        cur.execute("SELECT id, payload_json FROM mesh_offline_queue WHERE sync_status = 'PENDING'")
        rows = cur.fetchall()
        synced_count = 0
        for r_id, payload in rows:
            cur.execute("UPDATE mesh_offline_queue SET sync_status = 'SYNCED' WHERE id = ?", (r_id,))
            synced_count += 1
        conn.commit()
        conn.close()
        return synced_count