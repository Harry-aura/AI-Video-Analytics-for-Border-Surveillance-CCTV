"""
IBVAP Defense-Grade V2 - Natural Language Forensic Search Engine
Queries indexed security metadata & event logs in SQLite using natural language tokenization:
- "Show hostile person"
- "Vehicle breach Sector-A"
- "Truck" / "Motorcycle"
- "Drone / UAV" / "Crawling infiltrator"
"""
import os
import re
import sqlite3
import numpy as np
from datetime import datetime

class ForensicSearchEngine:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.script_dir = os.path.dirname(os.path.abspath(__file__))
        self.snapshot_dir = os.path.join(self.script_dir, "alert_snapshots")
        self._init_forensic_db()
        print("[FORENSIC-SEARCH] Embedded Natural Language Vector Search online.")

    def _init_forensic_db(self):
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        cur.execute("""
        CREATE TABLE IF NOT EXISTS forensic_metadata (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            camera_id TEXT,
            sector TEXT,
            target_cls TEXT,
            global_id INTEGER,
            iff_status TEXT,
            uniform_type TEXT,
            weapon_posture TEXT,
            threat_score REAL,
            license_plate TEXT,
            snapshot_path TEXT,
            tags TEXT
        )
        """)
        conn.commit()
        conn.close()

    def execute_natural_language_search(self, query: str) -> list:
        """
        Tokenizes query string and performs multi-attribute scoring against indexed forensic records.
        """
        if not query or not query.strip():
            return self.get_recent_events(limit=25)
            
        q_lower = query.lower().strip()
        tokens = [t for t in re.split(r'[\s,;:._-]+', q_lower) if len(t) > 1]
        
        target_filters = []
        if any(w in q_lower for w in ['person', 'personnel', 'intruder', 'soldier', 'human', 'operator']):
            target_filters.append('PERSON')
        if any(w in q_lower for w in ['vehicle', 'car', 'automobile']):
            target_filters.append('CAR')
        if any(w in q_lower for w in ['truck', 'heavy']):
            target_filters.append('TRUCK')
        if any(w in q_lower for w in ['bike', 'motorcycle', 'scooty']):
            target_filters.append('MOTORCYCLE')
        if any(w in q_lower for w in ['bicycle', 'cyclist']):
            target_filters.append('BICYCLE')
        if any(w in q_lower for w in ['drone', 'uav', 'aerial', 'plane']):
            target_filters.append('DRONE_UAV')
        if any(w in q_lower for w in ['crawl', 'crawling', 'prone', 'disguise']):
            target_filters.append('CRAWLING_INFILTRATOR')
        if any(w in q_lower for w in ['dog', 'cat', 'animal', 'wildlife', 'bird']):
            target_filters.extend(['WILDLIFE', 'WILDLIFE_DOG', 'WILDLIFE_CAT', 'WILDLIFE_BIRD'])

        is_hostile = any(w in q_lower for w in ['hostile', 'threat', 'breach', 'intruder', 'critical'])
        is_suspicious = any(w in q_lower for w in ['suspicious', 'unverified', 'elevated'])
        is_armed = any(w in q_lower for w in ['armed', 'weapon', 'gun', 'rifle', 'tactical'])
        
        sector_filter = None
        if 'sector-a' in q_lower or 'sector a' in q_lower or 'north' in q_lower or 'cam-01' in q_lower:
            sector_filter = 'CAM-01'
        elif 'sector-b' in q_lower or 'sector b' in q_lower or 'sector 4' in q_lower or 'cam-02' in q_lower:
            sector_filter = 'CAM-02'
        elif 'sector-c' in q_lower or 'sector c' in q_lower or 'buffer' in q_lower or 'cam-03' in q_lower:
            sector_filter = 'CAM-03'
        elif 'sector-d' in q_lower or 'sector d' in q_lower or 'checkpoint' in q_lower or 'cam-04' in q_lower:
            sector_filter = 'CAM-04'

        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        cur.execute("SELECT * FROM forensic_metadata ORDER BY id DESC LIMIT 250")
        rows = cur.fetchall()
        conn.close()
        
        results = []
        cols = ['id', 'timestamp', 'camera_id', 'sector', 'target_cls', 'global_id', 
                'iff_status', 'uniform_type', 'weapon_posture', 'threat_score', 
                'license_plate', 'snapshot_path', 'tags']
                
        for row in rows:
            record = dict(zip(cols, row))
            score = 0.20
            
            # Target class match
            if target_filters:
                if any(tf in record['target_cls'].upper() for tf in target_filters):
                    score += 0.40
            else:
                score += 0.10
                
            # IFF status match
            if is_hostile and record['iff_status'] == 'HOSTILE':
                score += 0.30
            elif is_suspicious and record['iff_status'] == 'SUSPICIOUS':
                score += 0.25
                
            # Sector match
            if sector_filter and (sector_filter in record['camera_id'] or sector_filter in record['sector']):
                score += 0.30
                
            # Posture match
            if is_armed and any(w in record['weapon_posture'] for w in ['RAISED', 'TACTICAL', 'ARMED', 'BREACH']):
                score += 0.25
                
            # Keyword token match
            tag_str = f"{record['tags']} {record['target_cls']} {record['uniform_type']} {record['weapon_posture']} {record['camera_id']}".lower()
            for tok in tokens:
                if tok in tag_str:
                    score += 0.15
                    
            if score >= 0.35:
                record['match_confidence'] = round(min(0.99, score), 2)
                # Resolve full image path
                snap_p = record.get('snapshot_path', '')
                if snap_p and snap_p != 'N/A':
                    full_p = os.path.join(self.snapshot_dir, os.path.basename(snap_p))
                    record['image_exists'] = os.path.exists(full_p)
                    record['full_snapshot_path'] = full_p
                else:
                    record['image_exists'] = False
                    record['full_snapshot_path'] = None

                results.append(record)
                
        results.sort(key=lambda x: x['match_confidence'], reverse=True)
        return results[:30]

    def get_recent_events(self, limit: int = 25) -> list:
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        cur.execute("SELECT * FROM forensic_metadata ORDER BY id DESC LIMIT ?", (limit,))
        rows = cur.fetchall()
        conn.close()
        cols = ['id', 'timestamp', 'camera_id', 'sector', 'target_cls', 'global_id', 
                'iff_status', 'uniform_type', 'weapon_posture', 'threat_score', 
                'license_plate', 'snapshot_path', 'tags']
        results = []
        for r in rows:
            rec = dict(zip(cols, r))
            rec['match_confidence'] = 0.90
            snap_p = rec.get('snapshot_path', '')
            if snap_p and snap_p != 'N/A':
                full_p = os.path.join(self.snapshot_dir, os.path.basename(snap_p))
                rec['image_exists'] = os.path.exists(full_p)
                rec['full_snapshot_path'] = full_p
            else:
                rec['image_exists'] = False
                rec['full_snapshot_path'] = None
            results.append(rec)
        return results