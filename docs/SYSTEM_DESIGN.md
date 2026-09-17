# System Design: Edge CV Inference & Latency Budget

## 1. Frame Dropping Prevention
At 30 FPS, each frame budget is 33.3 milliseconds. If an inference model takes 40ms, a naive sequential loop will continuously accumulate latency lag. This system solves this via a bounded drop-oldest buffer strategy: the frame consumer always processes the freshest available frame, ensuring real-time alert immediacy.

## 2. Occlusion Handling via DeepSORT
When a target passes behind obstacles (posts, trees, barriers), bounding box detection temporarily vanishes. The Kalman filter predicts position based on historical velocity vectors for up to 30 frames, seamlessly reconnecting the target once it re-emerges.
