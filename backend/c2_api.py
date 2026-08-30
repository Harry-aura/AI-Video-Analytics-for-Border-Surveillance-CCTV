"""
IBVAP Defense-Grade V2 - Backend C2 Server & Streaming Gateway
Provides low-latency MJPEG endpoints for all 4 camera quadrants and the 2D GIS Radar Map,
as well as WebSocket real-time telemetry and REST endpoints for external C2 command systems.
"""
import os
import sys
import time
import asyncio
import json
import cv2
import numpy as np
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query, Response
from fastapi.responses import StreamingResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "ai-engine")))

from stream_engine import MultiStreamManager
from audio_triangulator import AudioTriangulator
from forensic_search import ForensicSearchEngine

script_dir = os.path.dirname(os.path.abspath(__file__))
ai_engine_dir = os.path.abspath(os.path.join(script_dir, "..", "ai-engine"))
db_path = os.path.join(ai_engine_dir, "ibvap_surveillance.db")
config_path = os.path.join(ai_engine_dir, "camera_config.json")
test_video_path = os.path.join(ai_engine_dir, "test_feeds", "test_video.mp4")

app = FastAPI(title="IBVAP V2 Tactical Defense C2 Gateway")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

stream_manager = MultiStreamManager(
    db_path=db_path,
    config_file_path=config_path,
    fallback_video_path=test_video_path
)
audio_triangulator = AudioTriangulator()
forensic_engine = ForensicSearchEngine(db_path=db_path)

@app.on_event("startup")
def startup_event():
    stream_manager.start()
    print("[C2-GATEWAY] Multi-Stream Pipeline started.")

@app.on_event("shutdown")
def shutdown_event():
    stream_manager.stop()
    print("[C2-GATEWAY] Multi-Stream Pipeline stopped.")

async def frame_generator(cam_id: str):
    worker = stream_manager.workers.get(cam_id)
    if not worker:
        return
    while True:
        with worker.lock:
            jpeg = worker.latest_jpeg
        if jpeg is not None:
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + jpeg + b'\r\n')
        await asyncio.sleep(0.033)

async def radar_generator():
    while True:
        recent_audio = audio_triangulator.get_recent_vectors()
        radar_img = stream_manager.homography_proj.render_radar_canvas(
            stream_manager.get_all_active_targets(),
            acoustic_vectors=recent_audio
        )
        _, jpeg = cv2.imencode('.jpg', radar_img, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + jpeg.tobytes() + b'\r\n')
        await asyncio.sleep(0.05)

@app.get("/feed/{cam_id}")
async def get_camera_feed(cam_id: str):
    if cam_id not in stream_manager.workers:
        return Response(content="Camera ID not found", status_code=404)
    return StreamingResponse(frame_generator(cam_id), media_type="multipart/x-mixed-replace; boundary=frame")

@app.get("/feed/radar/live")
async def get_radar_feed():
    return StreamingResponse(radar_generator(), media_type="multipart/x-mixed-replace; boundary=frame")

@app.get("/api/targets")
def get_active_targets():
    return stream_manager.get_all_active_targets()

@app.get("/api/forensic_search")
def api_forensic_search(q: str = Query("", description="Natural language search query")):
    return forensic_engine.execute_natural_language_search(q)

@app.post("/api/calibrate_boundary")
def api_calibrate_boundary(cam_id: str, x1: int, y1: int, x2: int, y2: int, zone_orientation: str = "INWARD"):
    stream_manager.update_camera_calibration(cam_id, [x1, y1], [x2, y2], zone_orientation)
    return {"status": "SUCCESS", "camera_id": cam_id, "boundary": [[x1, y1], [x2, y2]], "orientation": zone_orientation}

@app.post("/api/audio_trigger")
def api_audio_trigger(threat_type: str = "GUNSHOT"):
    event = audio_triangulator.trigger_synthetic_anomaly(threat_type)
    return event

@app.websocket("/ws/telemetry")
async def websocket_telemetry(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            targets = stream_manager.get_all_active_targets()
            telemetry = {
                "timestamp": int(time.time()),
                "low_bandwidth_mode": stream_manager.mesh_mgr.low_bandwidth_mode,
                "target_count": len(targets),
                "targets": [
                    {
                        "gid": t.get('global_id'),
                        "cls": t.get('cls_name'),
                        "iff": t.get('iff_status'),
                        "map_pos": t.get('map_pos'),
                        "velocity": t.get('velocity')
                    } for t in targets
                ]
            }
            await websocket.send_text(json.dumps(telemetry))
            await asyncio.sleep(0.1)
    except WebSocketDisconnect:
        pass

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("c2_api:app", host="127.0.0.1", port=8000, reload=False)