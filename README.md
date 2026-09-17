<div align="center">
  <img src="https://capsule-render.vercel.app/api?type=waving&color=gradient&customColorList=1,13,25,33&height=240&section=header&text=%F0%9F%9B%A1%EF%B8%8F%20SENTINEL-AI%3A%20Border%20Perimeter%20Defense&fontSize=32&fontColor=ffffff&animation=fadeIn&fontAlignY=36&desc=Autonomous%20Multi-Spectral%20Surveillance%20%7C%20Deep%20SORT%20%7C%20Tactical%20Edge%20Intelligence&descFontSize=15&descAlignY=58" width="100%" />
  <br/>
  <p align="center">
    <a href="https://harry-aura.github.io/AI-Video-Analytics-for-Border-Surveillance-CCTV/"><img src="https://img.shields.io/badge/%F0%9F%9A%80%20LIVE%20TACTICAL%20HUD-LAUNCH%20WEB%20PORTAL-00C853?style=for-the-badge&labelColor=0d1117" alt="Live Demo" /></a>
    <a href="https://github.com/Harry-aura/AI-Video-Analytics-for-Border-Surveillance-CCTV/blob/main/docs/ARCHITECTURE.md"><img src="https://img.shields.io/badge/%F0%9F%9B%A1%EF%B8%8F%20SYSTEM%20SPEC-DEFENSE%20GRADE-2563EB?style=for-the-badge&labelColor=0d1117" alt="Architecture" /></a>
    <a href="https://github.com/Harry-aura/AI-Video-Analytics-for-Border-Surveillance-CCTV/blob/main/docs/INTERVIEW_GUIDE.md"><img src="https://img.shields.io/badge/%F0%9F%8F%86%20SIH%20DEFENSE-EVALUATION%20GUIDE-9333EA?style=for-the-badge&labelColor=0d1117" alt="SIH Guide" /></a>
  </p>
  <p align="center">
    <a href="#-sih-problem-statement--operational-alignment"><img src="https://img.shields.io/badge/SIH-National%20Hackathon%20Grade-FF6F00?style=flat-square&logo=target&logoColor=white" alt="SIH Ready" /></a>
    <a href="#-edge-hardware-target-matrix"><img src="https://img.shields.io/badge/Edge%20Hardware-NVIDIA%20Jetson%20Orin-76B900?style=flat-square&logo=nvidia&logoColor=white" alt="NVIDIA Jetson" /></a>
    <a href="https://github.com/Harry-aura/AI-Video-Analytics-for-Border-Surveillance-CCTV/blob/main/main.py"><img src="https://img.shields.io/badge/Engine-Multi--Threaded%20Python%20Core-3776AB?style=flat-square&logo=python&logoColor=white" alt="Python Core" /></a>
    <a href="https://github.com/Harry-aura/AI-Video-Analytics-for-Border-Surveillance-CCTV/blob/main/LICENSE"><img src="https://img.shields.io/badge/License-MIT-F59E0B?style=flat-square" alt="License" /></a>
  </p>
</div>

---

## 🇮🇳 SIH Problem Statement & Operational Alignment

> **Target Domain**: Defense & Border Management (Ministry of Home Affairs / Border Guarding Forces)
> **Core Challenge**: High false-alarm rates in remote border sectors due to adverse weather, wildlife, optical occlusion, and severe bandwidth constraints preventing full HD video backhauling to central command.
> **SENTINEL Solution**: Edge-native AI computing pipeline performing on-device real-time multi-spectral classification, persistent object tracking via Kalman-filtering, polygon geofence penetration detection via ray-casting algorithms, and ultra-low-bandwidth telemetry dispatch (< 200 bytes alert packets via satellite/mesh radio).

---

## 🖥️ Interactive Tactical Web HUD (Live Demo Available)

Experience the live simulation interface deployed via GitHub Pages:  
👉 **[Launch Live Sentinel Command HUD](https://harry-aura.github.io/AI-Video-Analytics-for-Border-Surveillance-CCTV/)**

- Real-time Canvas simulation of multi-spectral camera tracking.
- Simulated optical stream with active dynamic geofence tripwire.
- Instant MQTT event log dispatch and manual deterrent triggers (IR Strobe / Siren Relays).

---

## 🎯 Complete System Architecture

```mermaid
flowchart TB
    subgraph Edge_Sensors [Remote Edge Sensor Array]
        ThermalCam[Thermal IR Camera / RTSP] --> Ingress[Dual-Stream Buffer & Ring Queue]
        OpticalCam[Low-Light 4K PTZ / RTSP] --> Ingress
        Radar[Micro-Doppler Radar / Serial NMEA] --> SensorFusion[Early Fusion Arbiter]
        Ingress --> SensorFusion
    end

    subgraph Neural_Core [Jetson Edge Neural Engine]
        SensorFusion --> Preprocessing[CLAHE Contrast Equalizer & Resolution Normalizer]
        Preprocessing --> YOLOv8[YOLOv8-Nano / TensorRT FP16 Engine]
        YOLOv8 --> BoundingBox[Bounding Box Tensor & Class Probabilities]
        BoundingBox --> ReID[Deep Appearance Re-ID Feature Extractor]
    end

    subgraph Spatial_Tracking [Spatial Tracking & Verification]
        ReID --> Kalman[8-State Kalman Velocity Filter]
        Kalman --> Hungarian[Hungarian Data Association Matrix]
        Hungarian --> GeofenceEngine{Ray-Casting Polygon Breach?}
        GeofenceEngine -->|Wildlife or Noise| Suppress[False-Positive Suppressor Filter]
        GeofenceEngine -->|Hostile Breach| ThreatScore[Threat Scoring & Vector Calc]
    end

    subgraph Tactical_Dispatch [Zero-Bandwidth Tactical Ingress]
        ThreatScore --> Encrypt[AES-256 Compact Telemetry Packager]
        Encrypt --> MQTT[MQTT Mesh Broker / LoRa / SatCom]
        Encrypt --> LocalRelay[Edge GPIO: Strobe & Siren Actuator]
        MQTT --> BaseCommand[Tactical Command Center Dashboard]
    end

    classDef sensor fill:#1e293b,stroke:#3b82f6,stroke-width:2px,color:#fff;
    classDef neural fill:#0f172a,stroke:#10b981,stroke-width:2px,color:#fff;
    classDef spatial fill:#1e1b4b,stroke:#a855f7,stroke-width:2px,color:#fff;
    classDef dispatch fill:#14532d,stroke:#22c55e,stroke-width:2px,color:#fff;
    class ThermalCam,OpticalCam,Radar,Ingress,SensorFusion sensor;
    class Preprocessing,YOLOv8,BoundingBox,ReID neural;
    class Kalman,Hungarian,GeofenceEngine,Suppress,ThreatScore spatial;
    class Encrypt,MQTT,LocalRelay,BaseCommand dispatch;
```

---

## ⚡ Edge Hardware Target Matrix

| Target Deployment Tier | Processing Unit | Inference Model | Frame Rate (FPS) | Power Consumption | Operating Range |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Ultra-Edge (Solar/Pole)** | NVIDIA Jetson Orin Nano (8GB) | YOLOv8n (FP16 TensorRT) | **34.2 FPS** | 7W – 15W | -25°C to +65°C |
| **Bunker / Base Outpost** | NVIDIA Jetson AGX Orin (64GB) | YOLOv8x + Multi-Camera (8 streams) | **120+ FPS total** | 30W – 60W | MIL-STD-810H |
| **Tactical Rapid Deployment** | Raspberry Pi 5 + Hailo-8 NPU | YOLOv8s (INT8 Quantized) | **28.0 FPS** | 12W total | Field-swappable battery |

---

## 🚀 Fast Local Execution Guide

```bash
git clone [https://github.com/Harry-aura/AI-Video-Analytics-for-Border-Surveillance-CCTV.git](https://github.com/Harry-aura/AI-Video-Analytics-for-Border-Surveillance-CCTV.git)
cd AI-Video-Analytics-for-Border-Surveillance-CCTV

# Run the Python surveillance engine with geofence arbitration:
python main.py
```

---

## 📚 Technical Defense Hub

- [📘 Defense System Architecture Specification](https://github.com/Harry-aura/AI-Video-Analytics-for-Border-Surveillance-CCTV/blob/main/docs/ARCHITECTURE.md)
- [🔄 Multi-Spectral Video Ingestion Data Flow](https://github.com/Harry-aura/AI-Video-Analytics-for-Border-Surveillance-CCTV/blob/main/docs/DATA_FLOW.md)
- [📐 Real-Time Edge Video Analytics Design](https://github.com/Harry-aura/AI-Video-Analytics-for-Border-Surveillance-CCTV/blob/main/docs/SYSTEM_DESIGN.md)
- [🎓 SIH / Defense Hackathon Evaluation Guide](https://github.com/Harry-aura/AI-Video-Analytics-for-Border-Surveillance-CCTV/blob/main/docs/INTERVIEW_GUIDE.md)

---

## 👨‍💻 Engineer & Author

**Harivikash Katta**
- **GitHub**: [@Harry-aura](https://github.com/Harry-aura)
- **Initiative**: Smart India Hackathon (SIH) Defense Tech Track
