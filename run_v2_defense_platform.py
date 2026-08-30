"""
IBVAP Defense-Grade V2 - Master Platform Launcher
Starts the decoupled multi-stream vision engine, asynchronous MJPEG server, and Streamlit Tactical Dashboard.
"""
import os
import sys
import time
import subprocess
import webbrowser

def main():
    root_dir = os.path.dirname(os.path.abspath(__file__))
    ai_engine_dir = os.path.join(root_dir, "ai-engine")
    dashboard_path = os.path.join(ai_engine_dir, "dashboard.py")
    python_exe = sys.executable

    print("=" * 75)
    print("  🛡️  IBVAP TACTICAL SURVEILLANCE V2 — PRODUCTION DEFENSE PLATFORM  🛡️")
    print("  Queue Decoupled (25-30+ FPS) | Cursor Calibration | CCW Intrusion | Zero-Mock")
    print("=" * 75)
    print(f"[LAUNCHER] Root Directory: {root_dir}")
    print(f"[LAUNCHER] Python Binary:  {python_exe}")
    print(f"[LAUNCHER] Launching Streamlit C2 Tactical Command Center...")

    cmd = [
        python_exe,
        "-m", "streamlit", "run",
        dashboard_path,
        "--server.port=8501",
        "--server.headless=true",
        "--theme.base=dark"
    ]

    proc = subprocess.Popen(cmd, cwd=ai_engine_dir)
    
    time.sleep(2.5)
    webbrowser.open("http://localhost:8501")
    print("[LAUNCHER] Dashboard online at http://localhost:8501")
    print("[LAUNCHER] Press Ctrl+C in this terminal to terminate all defense services.")

    try:
        proc.wait()
    except KeyboardInterrupt:
        print("\n[LAUNCHER] Terminating Defense Platform...")
        proc.terminate()
        proc.wait()
        print("[LAUNCHER] Shutdown complete.")

if __name__ == "__main__":
    main()