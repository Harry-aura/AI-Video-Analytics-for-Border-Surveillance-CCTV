"""
IBVAP Defense-Grade V2 - Interactive Cursor-Click Calibration Module
Launches a responsive OpenCV window allowing operators to click directly on physical
landmarks (gates, fence posts, doorframes) on the camera frame to place sequential vertices,
preview the neon fence with elastic rubber-band cursor feedback, and lock/save with hotkey 'd'.
"""
import cv2
import json
import time
import math
import os
import sqlite3
import numpy as np

def run_cursor_calibration(camera_id: str, stream_manager=None, config_path: str = None, db_path: str = None):
    script_dir = os.path.dirname(os.path.abspath(__file__))
    config_path = config_path or os.path.join(script_dir, "camera_config.json")
    db_path = db_path or os.path.join(script_dir, "ibvap_surveillance.db")

    # Load initial config
    points = []
    mode = "OPEN_LINE"
    orientation = "INWARD"
    
    if os.path.exists(config_path):
        try:
            with open(config_path, "r") as f:
                cfg = json.load(f)
                cam_cfg = cfg.get("cameras", {}).get(camera_id, {})
                points = [list(p) for p in cam_cfg.get("fence_points", [[0, 460], [640, 460]])]
                mode = cam_cfg.get("boundary_mode", "OPEN_LINE")
                orientation = cam_cfg.get("zone_orientation", "INWARD")
        except Exception as e:
            print(f"[CALIBRATOR] Error reading config: {e}")

    if not points:
        points = [[0, 460], [640, 460]]

    cursor_pos = [0, 0]
    is_drawing = False

    def mouse_callback(event, x, y, flags, param):
        nonlocal points, cursor_pos
        cursor_pos = [x, y]
        if event == cv2.EVENT_LBUTTONDOWN:
            points.append([x, y])
            print(f"[CALIBRATOR] Added Vertex P{len(points)}: ({x}, {y})")

    window_name = f"IBVAP V2 — Cursor Calibration: {camera_id} (Click to place waypoints)"
    cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(window_name, 960, 720)
    cv2.setMouseCallback(window_name, mouse_callback)

    print("=" * 70)
    print(f"  🎯 INTERACTIVE CURSOR CALIBRATION — {camera_id}")
    print("  [LEFT CLICK]: Place vertex | [d]: Save & Apply | [r]: Reset")
    print("  [m]: Toggle Open/Closed Polygon | [o]: Toggle Orientation | [q/ESC]: Exit")
    print("=" * 70)

    saved = False

    try:
        while True:
            # Fetch latest frame from worker if stream_manager provided
            frame = None
            if stream_manager and camera_id in stream_manager.workers:
                worker = stream_manager.workers[camera_id]
                with worker.lock:
                    frame = worker.latest_raw_frame if worker.latest_raw_frame is not None else worker.latest_frame
                    
            if frame is None:
                frame = np.zeros((480, 640, 3), dtype=np.uint8)
                cv2.putText(frame, f"CALIBRATING: {camera_id}", (180, 240),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 200, 255), 2)

            display_frame = frame.copy()
            n_pts = len(points)
            pts_np = np.array(points, dtype=np.int32).reshape((-1, 1, 2)) if n_pts >= 1 else None

            # 1. Render Existing Perimeter Segments
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

            # 2. Elastic Rubber-Band Cursor Line from last vertex to current mouse position
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
                cv2.putText(display_frame, f"RESTRICTED [{mode} - {orientation}]", (arrow_end[0] - 40, arrow_end[1] + 15),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.40, (0, 255, 255), 1)

            # 5. Header / HUD Instructions
            cv2.rectangle(display_frame, (0, 0), (640, 36), (15, 20, 28), -1)
            hud_text = f"{camera_id} | Vertices: {n_pts} | Mode: {mode} [m] | Orient: {orientation} [o] | Save: [d] | Reset: [r] | Exit: [q]"
            cv2.putText(display_frame, hud_text, (10, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.36, (0, 255, 200), 1)

            cv2.imshow(window_name, display_frame)
            key = cv2.waitKey(20) & 0xFF

            if key == ord('q') or key == 27:  # Exit
                break
            elif key == ord('r'):  # Reset
                points = []
                print(f"[CALIBRATOR] Points reset for {camera_id}")
            elif key == ord('m'):  # Toggle Mode
                mode = "CLOSED_POLYGON" if mode == "OPEN_LINE" else "OPEN_LINE"
                print(f"[CALIBRATOR] Mode toggled to: {mode}")
            elif key == ord('o'):  # Toggle Orientation
                orientation = "OUTWARD" if orientation == "INWARD" else "INWARD"
                print(f"[CALIBRATOR] Orientation toggled to: {orientation}")
            elif key == ord('d'):  # Save & Apply
                if len(points) >= 2:
                    # Update active worker in memory
                    if stream_manager:
                        stream_manager.update_camera_calibration(camera_id, points, mode, orientation)
                    else:
                        # Direct file update fallback
                        if os.path.exists(config_path):
                            with open(config_path, "r") as f:
                                cfg = json.load(f)
                            if "cameras" in cfg and camera_id in cfg["cameras"]:
                                cfg["cameras"][camera_id]["fence_points"] = points
                                cfg["cameras"][camera_id]["boundary_mode"] = mode
                                cfg["cameras"][camera_id]["zone_orientation"] = orientation
                            with open(config_path, "w") as f:
                                json.dump(cfg, f, indent=2)
                    saved = True
                    print(f"[CALIBRATOR] ✅ Calibration locked and saved for {camera_id}: {len(points)} vertices ({mode}, {orientation})")
                    break
                else:
                    print("[CALIBRATOR] ⚠️ Please place at least 2 vertices before saving.")

    finally:
        cv2.destroyWindow(window_name)

    return saved, points, mode, orientation

if __name__ == "__main__":
    run_cursor_calibration("CAM-01")
