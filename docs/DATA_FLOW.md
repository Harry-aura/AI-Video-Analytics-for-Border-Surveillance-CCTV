# Video Analytics Data Flow & Frame Lifecycle

~~~text
[RTSP IP Camera Video Stream]
               │
               ▼
  [Thread 1: Frame Acquisition & Circular Queue]
               │
               ▼
  [Thread 2: Tensor Quantization (FP16)]
               │
               ▼
  [YOLO Detection: Coordinates (x1, y1, x2, y2)]
               │
               ▼
  [Thread 3: DeepSORT Hungarian Matching & Kalman Prediction]
               │
     {Polygon Geofence Intersection?}
     ├── Yes ──> [Issue Priority Intrusion Alert + JSON Payload]
     └── No ───> [Update Track Trajectory State]
~~~
