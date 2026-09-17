# Architecture Specification: AI Border Surveillance Analytics

## 1. Pipeline Decoupling
Computer vision pipelines frequently bottleneck when video decoding, deep neural inference, and UI rendering share a single thread. This architecture decouples execution across 3 dedicated thread pools:
1. **Ingress Thread**: Grabs frames from RTSP streams into a bounded circular ring buffer.
2. **Inference Thread**: Batches frames and dispatches tensor forward passes on hardware accelerators.
3. **Tracker & Alert Thread**: Executes Kalman filter updates, geofence evaluations, and alert dispatches.
