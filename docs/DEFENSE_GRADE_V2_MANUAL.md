# IBVAP Tactical Surveillance V2 — 100% Live Operational Defense System

## 1. System Overview
IBVAP V2 is a 100% live, production-grade tactical defense perimeter surveillance platform. It eliminates all synthetic data loops and enforces real live hardware video ingestion, interactive perimeter calibration with instant hot-reloading, trajectory vector intersection math (preventing missed fast-motion breaches), bottom-center foot homography 2D radar mapping, decoupled Re-ID, IFF threat analysis, and 20 kbps mesh resiliency.

---

## 2. Live Operational Modules

### 2.1 Live Hardware Multi-Stream Pipeline (`stream_engine.py`)
- **Default Physical Webcam (`CAM-01`)**: Probes Device Index `0` via `cv2.CAP_DSHOW`, then `cv2.CAP_ANY`, and gracefully falls back to `test_feeds/test_video.mp4` only if physical hardware is unavailable.
- **Dynamic Configurable Inputs (`CAM-02` to `CAM-04`)**: Read from `camera_config.json` supporting local USB cameras, RTSP streams, or test videos.
- **Dynamic Frame Skipping (Mandate 4)**: Executes YOLOv8 inference every $N=2$ frames with tracker interpolation on intermediate frames.

### 2.2 Trajectory Vector Line Intersection (Technical Safety Rule 1)
- Evaluates line segment intersection between target footpoint at $t-1$ $(x_{t-1}, y_{t-1})$ and $t$ $(x_t, y_t)$ against calibrated boundary segment $(X_1, Y_1) \to (X_2, Y_2)$.
- Checks directed cross-product side transitions based on `INWARD` vs `OUTWARD` zone orientation.
- Guarantees zero missed breaches even during high-velocity target motion across the wire.

### 2.3 Interactive Perimeter Calibration (`dashboard.py` & `camera_config.json`)
- Interactive sidebar sliders for $X_1, Y_1, X_2, Y_2$ and restricted zone orientation toggle.
- Real-time tactical neon boundary lines and ground-normal directional arrows rendered directly on the stream.
- In-memory debounced preview with persistent commit to `camera_config.json` and SQLite table `camera_fence_configs` on clicking **"Save & Apply Perimeter Calibration"**.

### 2.4 Ground Footpoint Homography 2D Radar (`homography_radar.py`)
- Projects ground contact point $((x_1+x_2)/2, y_2)$ via calibrated homography matrices onto a top-down 2D GIS Radar Map displaying camera FOV cones, active radar dots, velocity vectors, and breadcrumbs.

### 2.5 Zero-Mock Database & Telemetry (`ibvap_surveillance.db`)
- Purged of all synthetic records.
- Database logs, forensic search vector indexing, and 20 kbps Base64 telemetry packets are generated **strictly** upon real live detections.

---

## 3. How to Launch

```powershell
& "C:\Users\Harivikash katta\AppData\Local\Python\pythoncore-3.14-64\python.exe" "C:\Users\Harivikash katta\.gemini\antigravity\scratch\IBVAP-Tactical-Surveillance-V2-DefenseGrade\run_v2_defense_platform.py"
```
Dashboard opens automatically at `http://localhost:8501`.