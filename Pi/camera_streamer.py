#!/usr/bin/env python3
"""
Camera Streamer - Dual GStreamer output to Laptop and Game Viewer
"""

import subprocess
import os
import signal
from typing import Dict, Optional

class CameraStreamer:
    def __init__(self, config: Dict):
        self.camera_config = config['camera']
        self.network_config = config['network']
        self.team_id = config['team']['team_id']
        
        self.width = self.camera_config.get('width', 1280)
        self.height = self.camera_config.get('height', 720)
        self.framerate = self.camera_config.get('framerate', 30)
        self.bitrate = self.camera_config.get('bitrate', 4000000)
        
        # Laptop IP will be set when laptop connects
        self.laptop_ip = None
        self.laptop_port = self.network_config['laptop_video_port']
        
        # GV video port is calculated: 5000 + team_id
        self.gv_ip = self.network_config['game_viewer_ip']
        self.gv_port = 5000 + self.team_id
        
        self.process: Optional[subprocess.Popen] = None
        self.is_streaming = False
    
    def start_stream(self) -> bool:
        """Start camera stream to both laptop and game viewer"""
        if self.is_streaming:
            print("[Camera] Already streaming")
            return False
        
        if not self.camera_config.get('enabled', True):
            print("[Camera] Camera disabled in config")
            return False
        
        if not self.laptop_ip:
            print("[Camera] ⚠️ No laptop IP set - waiting for laptop connection")
            return False
        
        print("[Camera] Starting dual video stream...")
        print(f"[Camera] → Laptop: {self.laptop_ip}:{self.laptop_port}")
        print(f"[Camera] → Game Viewer: {self.gv_ip}:{self.gv_port}")
        
        # Build GStreamer pipeline with tee element for dual output
        cmd = (
            f"rpicam-vid -t 0 "
            f"--width {self.width} --height {self.height} --framerate {self.framerate} "
            f"--codec h264 --bitrate {self.bitrate} --profile baseline "
            f"--intra 30 --inline --nopreview -o - | "
            f"gst-launch-1.0 -v fdsrc ! h264parse ! "
            f"tee name=t "
            f"t. ! queue ! rtph264pay config-interval=1 pt=96 ! "
            f"udpsink host={self.laptop_ip} port={self.laptop_port} sync=false async=false "
            f"t. ! queue ! rtph264pay config-interval=1 pt=96 ! "
            f"udpsink host={self.gv_ip} port={self.gv_port} sync=false async=false"
        )
        
        try:
            self.process = subprocess.Popen(
                cmd,
                shell=True,
                preexec_fn=os.setsid,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            
            self.is_streaming = True
            print("[Camera] ✅ Streaming started")
            return True
        
        except Exception as e:
            print(f"[Camera] ❌ Failed to start stream: {e}")
            return False
    
    def stop_stream(self):
        """Stop camera stream"""
        if not self.is_streaming:
            return
        
        print("[Camera] Stopping stream...")
        
        if self.process and self.process.poll() is None:
            try:
                # Kill entire process group
                os.killpg(os.getpgid(self.process.pid), signal.SIGTERM)
                self.process.wait(timeout=2)
            except Exception as e:
                print(f"[Camera] Error stopping stream: {e}")
                try:
                    os.killpg(os.getpgid(self.process.pid), signal.SIGKILL)
                except:
                    pass
        
        self.process = None
        self.is_streaming = False
        print("[Camera] Stream stopped")
    
    def restart_stream(self):
        """Restart camera stream"""
        self.stop_stream()
        import time
        time.sleep(1)
        return self.start_stream()
    
    def update_destinations(self, laptop_ip: str = None, laptop_port: int = None,
                           gv_ip: str = None, gv_port: int = None):
        """Update stream destinations (requires restart)"""
        if laptop_ip:
            self.laptop_ip = laptop_ip
        if laptop_port:
            self.laptop_port = laptop_port
        if gv_ip:
            self.gv_ip = gv_ip
        if gv_port:
            self.gv_port = gv_port
        
        if self.is_streaming:
            print("[Camera] Restarting stream with new destinations...")
            self.restart_stream()
    
    def is_alive(self) -> bool:
        """Check if stream is running"""
        if not self.is_streaming or not self.process:
            return False
        return self.process.poll() is None
    
    def cleanup(self):
        """Clean up camera resources"""
        print("[Camera] Cleaning up...")
        self.stop_stream()
