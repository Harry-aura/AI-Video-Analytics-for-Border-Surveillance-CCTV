"""
IBVAP Defense-Grade V2 - Dedicated Latched Defense Audio Engine & Military Klaxon Generator
Features:
1. Acoustic Waveform Profile: Military Warble / Klaxon (800 Hz <-> 1200 Hz at 2.5 Hz FM sweep):
   f(t) = 800 + 400 * (1 + sin(2 * pi * 2.5 * t)) / 2  [Hz]
   y(t) = 0.65 * sin(phi(t)) + 0.35 * sin(2 * phi(t))  [with -6 dB harmonic overtone]
2. High-fidelity 44.1 kHz 16-bit PCM WAV generation saved to assets/military_alarm.wav
   and cached as Base64 data URI for zero-latency client browser playback.
3. Pure HTML5 Audio Persistent Looping with Zero Legacy Beeps.
4. Latched Alarm State Management with Zero Auto-Timeout:
   Remains active in an unyielding loop until explicitly silenced by operator interaction.
"""
import os
import io
import math
import wave
import struct
import base64
import threading
import time
import numpy as np

class DefenseAudioEngine:
    _instance = None
    _cached_wav_bytes = None
    _cached_b64 = None

    def __init__(self, sample_rate: int = 44100, duration_seconds: float = 2.0):
        self.sample_rate = sample_rate
        self.duration_seconds = duration_seconds
        self.alarm_active = False
        self.lock = threading.Lock()
        
        # Ensure assets directory exists
        self.script_dir = os.path.dirname(os.path.abspath(__file__))
        self.assets_dir = os.path.join(self.script_dir, "assets")
        os.makedirs(self.assets_dir, exist_ok=True)
        self.wav_file_path = os.path.join(self.assets_dir, "military_alarm.wav")
        
        # Pre-generate and cache synthetic military alarm WAV
        self._ensure_alarm_file()

    def _ensure_alarm_file(self):
        """Generates synthetic military warble WAV file if not already present on disk."""
        if DefenseAudioEngine._cached_b64 is not None:
            return

        total_samples = int(self.sample_rate * self.duration_seconds)
        t = np.linspace(0.0, self.duration_seconds, total_samples, endpoint=False)
        
        # Instantaneous Phase integral of f(t) = 800 + 200 * (1 + sin(2 * pi * 2.5 * t))
        # f(t) = 1000 + 200 * sin(5 * pi * t)
        # phi(t) = 2 * pi * 1000 * t - (200 / 2.5) * cos(5 * pi * t)
        fm_mod = 2.5
        phi = 2.0 * np.pi * 1000.0 * t - (200.0 / fm_mod) * np.cos(2.0 * np.pi * fm_mod * t)
        
        # Fundamental wave (0.65) + First harmonic overtone (0.35 at -6 dB)
        waveform = 0.65 * np.sin(phi) + 0.35 * np.sin(2.0 * phi)
        
        # Sharp attack envelope to simulate tactical horn pulse
        attack_len = int(self.sample_rate * 0.05)
        envelope = np.ones(total_samples, dtype=np.float32)
        envelope[:attack_len] = np.linspace(0.0, 1.0, attack_len)
        envelope[-attack_len:] = np.linspace(1.0, 0.0, attack_len)
        waveform = waveform * envelope

        # Convert to 16-bit PCM integer samples
        pcm_samples = (waveform * 30000.0).astype(np.int16)
        
        buf = io.BytesIO()
        with wave.open(buf, 'wb') as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(self.sample_rate)
            wf.writeframes(pcm_samples.tobytes())
            
        wav_bytes = buf.getvalue()
        DefenseAudioEngine._cached_wav_bytes = wav_bytes
        DefenseAudioEngine._cached_b64 = base64.b64encode(wav_bytes).decode('utf-8')
        
        # Save to assets on disk
        try:
            with open(self.wav_file_path, 'wb') as f:
                f.write(wav_bytes)
            print(f"[AUDIO-ENGINE] 🔊 Military warble audio synthesized: {self.wav_file_path}")
        except Exception as e:
            print(f"[AUDIO-ENGINE] Notice saving WAV: {e}")

    @classmethod
    def get_military_alarm_base64(cls) -> str:
        """Returns base64 encoded military alarm WAV data URI."""
        if cls._cached_b64 is None:
            engine = DefenseAudioEngine()
            return engine._cached_b64
        return cls._cached_b64

    def trigger_alarm(self):
        """Activates unyielding defense alarm latch."""
        with self.lock:
            self.alarm_active = True
            print("[AUDIO-ENGINE] 🚨 Latched Defense Siren ACTIVE (Military Klaxon 800-1200Hz).")

    def silence_alarm(self):
        """Silences alarm and releases the latch upon operator acknowledgment."""
        with self.lock:
            self.alarm_active = False
            print("[AUDIO-ENGINE] 🔕 Defense Siren silenced and latch cleared.")

    def is_alarm_active(self) -> bool:
        """Returns True if the defense alarm is actively latched."""
        with self.lock:
            return self.alarm_active

    def get_audio_html(self) -> str:
        """
        Returns clean, dedicated, persistent HTML5 audio injection with autoplay and loop.
        """
        b64 = self.get_military_alarm_base64()
        return f"""
        <audio id="defense_siren" autoplay loop style="display:none;">
            <source src="data:audio/wav;base64,{b64}" type="audio/wav">
        </audio>
        <script>
            var audio = document.getElementById("defense_siren");
            if (audio) {{
                audio.currentTime = 0;
                audio.play().catch(function(e) {{
                    console.log("Audio autoplay prevented: ", e);
                }});
            }}
        </script>
        """

    def get_silence_html(self) -> str:
        """
        Returns JavaScript to immediately terminate any playing defense siren audio.
        """
        return """
        <script>
            var audio = document.getElementById("defense_siren");
            if (audio) {
                audio.pause();
                audio.currentTime = 0;
            }
        </script>
        """
