import os
import cv2
import time
import requests
from ultralytics import YOLO

# ================= CONFIGURATION =================
USE_WEBCAM = True   # Set to True for live camera, False for video feed
ALERT_COOLDOWN = 5   # Seconds between alerts
WEBHOOK_URL = "http://localhost:5678/webhook/detection-alert"
# =================================================

script_dir = os.path.dirname(os.path.abspath(__file__))
video_path = os.path.join(script_dir, "test_feeds", "test_video.mp4")

# Select source: 0 for laptop webcam, file path for video
source = 0 if USE_WEBCAM else video_path

model = YOLO('yolov8n.pt')
cap = cv2.VideoCapture(source)
window_title = "IBVAP - Live AI Detection Feed"
last_alert_time = 0

print(f"AI Engine active! Source: {'LIVE WEBCAM' if USE_WEBCAM else 'VIDEO FILE'}")

while True:
    ret, frame = cap.read()
    if not ret:
        if not USE_WEBCAM:
            cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            continue
        else:
            print("Webcam disconnected.")
            break

    # Track people (0), cars (2), trucks (7)
    results = model.track(frame, persist=True, classes=[0, 2, 7], verbose=False)
    current_time = time.time()

    for box in results[0].boxes:
        cls_id = int(box.cls[0])
        confidence = float(box.conf[0])

        if cls_id == 0 and confidence > 0.50:
            if current_time - last_alert_time > ALERT_COOLDOWN:
                last_alert_time = current_time
                print(f"[ALERT] Target detected! Confidence: {confidence:.2f}. Sending payload...")
                try:
                    payload = {"event": "PERSON_DETECTED", "confidence": confidence, "timestamp": time.time()}
                    requests.post(WEBHOOK_URL, json=payload, timeout=0.5)
                except Exception:
                    pass

    annotated_frame = results[0].plot()
    cv2.imshow(window_title, annotated_frame)

    if cv2.waitKey(30) & 0xFF == ord('q'):
        break
    if cv2.getWindowProperty(window_title, cv2.WND_PROP_VISIBLE) < 1:
        break

cap.release()
cv2.destroyAllWindows()