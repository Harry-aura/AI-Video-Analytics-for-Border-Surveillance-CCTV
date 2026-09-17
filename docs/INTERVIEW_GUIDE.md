# Computer Vision Technical Interview Defense Guide

### Q1: Why use DeepSORT over standard ByteTrack or simple IoU tracking for border surveillance?
> **Answer**: Simple IoU tracking fails when targets cross paths or become occluded by terrain. DeepSORT incorporates a deep appearance descriptor (Re-ID network) that computes cosine visual distances, enabling accurate trajectory recovery even when targets move non-linearly.

### Q2: How is environmental noise (wildlife, rain, swaying branches) filtered out?
> **Answer**: Through a two-stage filter: first, confidence thresholds (> 0.70) and non-human class suppression; second, a minimum temporal trajectory threshold where an alert is only triggered if an intrusion vector persists across at least 3 consecutive frames.

### Q3: How do you achieve 30+ FPS throughput on edge hardware?
> **Answer**: By quantizing model weights from FP32 to FP16, decoupling RTSP decoding into a dedicated background process, and resizing frames strictly to standard inference resolutions.
