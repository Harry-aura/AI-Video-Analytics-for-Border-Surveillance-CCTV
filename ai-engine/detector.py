import os
import cv2
from ultralytics import YOLO

# Locate video using absolute path
script_dir = os.path.dirname(os.path.abspath(__file__))
video_path = os.path.join(script_dir, "test_feeds", "test_video.mp4")

model = YOLO('yolov8n.pt')
cap = cv2.VideoCapture(video_path)

window_title = "IBVAP - Live AI Detection Feed"

while True:
    ret, frame = cap.read()
    
    # Loop video continuously
    if not ret:
        cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
        continue

    # Track people (0), cars (2), and trucks (7)
    results = model.track(frame, persist=True, classes=[0, 2, 7], verbose=False)

    annotated_frame = results[0].plot()
    cv2.imshow(window_title, annotated_frame)

    # Allow closing via 'q' key OR the 'X' window button
    if cv2.waitKey(30) & 0xFF == ord('q'):
        break
    if cv2.getWindowProperty(window_title, cv2.WND_PROP_VISIBLE) < 1:
        break

cap.release()
cv2.destroyAllWindows()