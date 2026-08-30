"""
IBVAP Defense-Grade V2 - Freeform Desktop Cursor Calibration Tool
Direct native OpenCV GUI running on the OS main thread with zero web latency.
Usage:
    python calibrate_fence.py --cam CAM-01
"""
import os
import sys
import cv2
import json
import time
import math
import sqlite3
import argparse
import urllib.request
import numpy as np

def fetch_live_frame(camera_id: str, config: dict, script_dir: str):
    """
    Attempts to fetch a live frame from the running stream server snapshot endpoint,
    or falls back to opening the capture source directly.
    """
    # 1. Try HTTP Snapshot from running Stream Engine
    snapshot_url = f"http://127.0.0.1:8000/snapshot/{camera_id}"
    try:
        req = urllib.request.Request(snapshot_url, headers={'User-Agent': 'IBVAP-Calibrator'})
        with urllib.request.urlopen(req, timeout=1.5) as resp:
            if resp.status == 200:
                img_data = resp.read()
                arr = np.frombuffer(img_data, np.uint8)
                frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
                if frame is not None:
                    return frame
    except Exception:
        pass

    # 2. Fallback to direct VideoCapture
    cam_cfg = config.get("cameras", {}).get(camera_id, {})
    source = cam_cfg.get("source", 0)
    
    if isinstance(source, int) or (isinstance(source, str) and source.isdigit()):
        dev_idx = int(source)
        cap = cv2.VideoCapture(dev_idx, cv2.CAP_DSHOW)
        if not cap.isOpened():
            cap = cv2.VideoCapture(dev_idx, cv2.CAP_ANY)
    else:
        video_path = source if os.path.isabs(source) else os.path.join(script_dir, source)
        cap = cv2.VideoCapture(video_path)

    if cap.isOpened():
        ret, frame = cap.read()
        cap.release()
        if ret and frame is not None:
            return cv2.resize(frame, (640, 480))

    # 3. Last fallback: tactical blank frame
    blank = np.zeros((480, 640, 3), dtype=np.uint8)
    cv2.putText(blank, f"CALIBRATING: {camera_id}", (180, 240),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 200, 255), 2)
    return blank

def save_calibration(camera_id: str, points: list, mode: str, orientation: str, config_path: str, db_path: str):
    """
    Persists calibrated perimeter to camera_config.json and SQLite database.
    """
    cfg = {}
    if os.path.exists(config_path):
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                cfg = json.load(f)
        except Exception as e:
            print(f"[CALIBRATOR] Error reading config: {e}")

    if "cameras" not in cfg:
        cfg["cameras"] = {}
    if camera_id not in cfg["cameras"]:
        cfg["cameras"][camera_id] = {}

    cfg["cameras"][camera_id]["fence_points"] = points
    cfg["cameras"][camera_id]["boundary_mode"] = mode
    cfg["cameras"][camera_id]["zone_orientation"] = orientation

    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)

    # 2. Update SQLite database
    try:
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        if points and len(points) >= 2:
            p1 = points[0]
            p2 = points[-1]
            cam_name = cfg["cameras"][camera_id].get("name", camera_id)
            source = str(cfg["cameras"][camera_id].get("source", 0))
            cur.execute("""
            INSERT OR REPLACE INTO camera_fence_configs (camera_id, camera_name, source, x1, y1, x2, y2, zone_orientation)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (camera_id, cam_name, source, p1[0], p1[1], p2[0], p2[1], orientation))
        else:
            cur.execute("DELETE FROM camera_fence_configs WHERE camera_id = ?", (camera_id,))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[CALIBRATOR] SQLite update notice: {e}")

    print(f"[CALIBRATOR] ✅ Successfully saved {len(points)} vertices for {camera_id} ({mode}, {orientation}).")

def main():
    parser = argparse.ArgumentParser(description="IBVAP Freeform Desktop Cursor Calibration Tool")
    parser.add_argument("--cam", type=str, default="CAM-01", help="Camera ID to calibrate (e.g. CAM-01)")
    args = parser.parse_args()

    camera_id = args.cam
    script_dir = os.path.dirname(os.path.abspath(__file__))
    config_path = os.path.join(script_dir, "camera_config.json")
    db_path = os.path.join(script_dir, "ibvap_surveillance.db")

    # Load initial points & settings from disk (defaults to clean [])
    points = []
    mode = "OPEN_LINE"
    orientation = "INWARD"
    config = {}

    if os.path.exists(config_path):
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                config = json.load(f)
                cam_cfg = config.get("cameras", {}).get(camera_id, {})
                points = [list(p) for p in cam_cfg.get("fence_points", [])]
                mode = cam_cfg.get("boundary_mode", "OPEN_LINE")
                orientation = cam_cfg.get("zone_orientation", "INWARD")
        except Exception as e:
            print(f"[CALIBRATOR] Error reading config: {e}")

    cursor_pos = [0, 0]

    def mouse_callback(event, x, y, flags, param):
        nonlocal points, cursor_pos
        cursor_pos = [x, y]
        if event == cv2.EVENT_LBUTTONDOWN:
            points.append([x, y])
            print(f"[CALIBRATOR] Click -> Added Vertex P{len(points)}: ({x}, {y})")

    window_name = f"IBVAP V2 Desktop Calibrator: {camera_id} (Click to draw fence)"
    cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(window_name, 960, 720)
    cv2.setMouseCallback(window_name, mouse_callback)

    print("=" * 75)
    print(f"  🎯 IBVAP FREEFORM CURSOR CALIBRATION — {camera_id}")
    print("  [LEFT CLICK]: Place vertex | [d]: Save & Apply | [r]: Reset (Clear canvas)")
    print("  [m]: Toggle Open/Closed Mode | [q/ESC]: Exit")
    print("=" * 75)

    try:
        while True:
            frame = fetch_live_frame(camera_id, config, script_dir)
            display_frame = frame.copy()
            n_pts = len(points)
            pts_np = np.array(points, dtype=np.int32).reshape((-1, 1, 2)) if n_pts >= 1 else None

            # 1. Render Multi-Segment / Polygon Fence
            if mode == "CLOSED_POLYGON" and n_pts >= 3:
                overlay = display_frame.copy()
                cv2.fillPoly(overlay, [pts_np], (0, 0, 180))
                cv2.addWeighted(overlay, 0.25, display_frame, 0.75, 0, display_frame)
                cv2.polylines(display_frame, [pts_np], isClosed=True, color=(0, 140, 255), thickness=3, lineType=cv2.LINE_AA)
                cv2.polylines(display_frame, [pts_np], isClosed=True, color=(0, 255, 255), thickness=1, lineType=cv2.LINE_AA)
            else:
                for i in range(n_pts - 1):
                    p1 = tuple(points[i])
                    p2 = tuple(points[i + 1])
                    cv2.line(display_frame, p1, p2, (0, 140, 255), 4, cv2.LINE_AA)
                    cv2.line(display_frame, p1, p2, (0, 255, 255), 2, cv2.LINE_AA)

            # 2. Elastic Rubber-Band Cursor Line to current mouse position
            if n_pts >= 1:
                last_pt = tuple(points[-1])
                cv2.line(display_frame, last_pt, tuple(cursor_pos), (0, 255, 100), 2, cv2.LINE_AA)
                cv2.circle(display_frame, tuple(cursor_pos), 4, (0, 255, 100), -1)

            # 3. Draw Numbered Vertex Markers
            for idx, pt in enumerate(points):
                color = (0, 255, 0) if idx == 0 else ((0, 0, 255) if idx == n_pts - 1 else (0, 255, 255))
                cv2.circle(display_frame, tuple(pt), 7, color, -1)
                cv2.circle(display_frame, tuple(pt), 9, (255, 255, 255), 1)
                cv2.putText(display_frame, f"P{idx+1}", (pt[0] - 8, pt[1] - 12),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1)

            # 4. Directional Normal Arrow
            if n_pts >= 2:
                mid_idx = (n_pts - 1) // 2
                p_start, p_end = points[mid_idx], points[min(mid_idx + 1, n_pts - 1)]
                mid_x = (p_start[0] + p_end[0]) // 2
                mid_y = (p_start[1] + p_end[1]) // 2
                dx = p_end[0] - p_start[0]
                dy = p_end[1] - p_start[1]
                length = math.hypot(dx, dy) + 1e-5
                nx, ny = -dy / length, dx / length
                if orientation == 'OUTWARD':
                    nx, ny = -nx, -ny
                arrow_end = (int(mid_x + nx * 40), int(mid_y + ny * 40))
                cv2.arrowedLine(display_frame, (mid_x, mid_y), arrow_end, (0, 255, 255), 2, tipLength=0.35)
                cv2.putText(display_frame, f"RESTRICTED [{mode}]", (arrow_end[0] - 40, arrow_end[1] + 15),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.40, (0, 255, 255), 1)

            # 5. Header / HUD Instructions
            cv2.rectangle(display_frame, (0, 0), (640, 36), (15, 20, 28), -1)
            hud_text = f"{camera_id} | Vertices: {n_pts} | Mode: {mode} [m] | Save: [d] | Clear/Reset: [r] | Exit: [q]"
            cv2.putText(display_frame, hud_text, (10, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.36, (0, 255, 200), 1)

            cv2.imshow(window_name, display_frame)
            key = cv2.waitKey(30) & 0xFF

            if key == ord('q') or key == 27:  # Exit
                break
            elif key == ord('r'):  # Reset & Clear
                points = []
                print(f"[CALIBRATOR] Canvas cleared for {camera_id}")
            elif key == ord('m'):  # Toggle Mode
                mode = "CLOSED_POLYGON" if mode == "OPEN_LINE" else "OPEN_LINE"
                print(f"[CALIBRATOR] Mode toggled to: {mode}")
            elif key == ord('d'):  # Save & Apply
                if len(points) >= 2 or len(points) == 0:
                    save_calibration(camera_id, points, mode, orientation, config_path, db_path)
                    break
                else:
                    print("[CALIBRATOR] ⚠️ Please place at least 2 vertices (or press 'r' then 'd' to clear).")

    finally:
        cv2.destroyWindow(window_name)

if __name__ == "__main__":
    main()
