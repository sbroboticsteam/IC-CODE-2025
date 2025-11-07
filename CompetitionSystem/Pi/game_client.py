#!/usr/bin/env python3
"""
Game Client - PROTECTED FILE - DO NOT MODIFY
Handles communication with Game Viewer
"""

import json
import socket
import time
import threading
from typing import Dict, Callable, Optional

class GameClient:
    """Handles bidirectional communication with Game Viewer"""
    
    def __init__(self, config: Dict):
        self.team_id = config['team']['team_id']
        self.team_name = config['team']['team_name']
        self.robot_name = config['team']['robot_name']
        
        self.gv_ip = config['network']['game_viewer_ip']
        self.gv_control_port = config['network']['game_viewer_control_port']
        self.listen_port = self.gv_control_port + self.team_id  # Unique port per team
        
        self.heartbeat_interval = config['safety']['heartbeat_interval_s']
        
        # Network
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.settimeout(0.1)  # Non-blocking with timeout
        
        # State
        self.connected = False
        self.game_active = False
        self.is_ready = False
        self.points = 0
        self.deaths = 0
        self.kills = 0
        
        # Callbacks
        self.on_game_start: Optional[Callable] = None
        self.on_game_end: Optional[Callable] = None
        self.on_ready_check: Optional[Callable] = None
        self.on_points_update: Optional[Callable[[int], None]] = None
        
        # Threading
        self.running = False
        self.listen_thread: Optional[threading.Thread] = None
        self.heartbeat_thread: Optional[threading.Thread] = None
        self.registration_thread: Optional[threading.Thread] = None
        
        # Connection tracking
        self.last_gv_contact = 0  # Track last contact with GV
    
    def start(self):
        """Start game client"""
        print("[GameClient] Starting...")
        print(f"[GameClient] Team: {self.team_name} (ID: {self.team_id})")
        print(f"[GameClient] Game Viewer: {self.gv_ip}:{self.gv_control_port}")
        print(f"[GameClient] Listening on port: {self.listen_port}")
        
        try:
            self.sock.bind(('0.0.0.0', self.listen_port))
        except Exception as e:
            print(f"[GameClient] ❌ Failed to bind to port {self.listen_port}: {e}")
            return False
        
        self.running = True
        
        # Start listener thread
        self.listen_thread = threading.Thread(target=self._listen_loop, daemon=True)
        self.listen_thread.start()
        
        # Start heartbeat thread
        self.heartbeat_thread = threading.Thread(target=self._heartbeat_loop, daemon=True)
        self.heartbeat_thread.start()
        
        # Start periodic registration thread
        self.registration_thread = threading.Thread(target=self._registration_loop, daemon=True)
        self.registration_thread.start()
        
        # Send initial registration
        self.send_registration()
        
        print("[GameClient] ✅ Started")
        return True
    
    def send_registration(self):
        """Register with Game Viewer"""
        message = {
            "type": "REGISTER",
            "team_id": self.team_id,
            "team_name": self.team_name,
            "robot_name": self.robot_name,
            "listen_port": self.listen_port,
            "timestamp": time.time()
        }
        self._send_to_gv(message)
        print(f"[GameClient] Sent registration")
    
    def _registration_loop(self):
        """Periodic registration loop"""
        while self.running:
            try:
                # Re-register every 30 seconds
                time.sleep(30.0)
                
                if self.running:  # Check again after sleep
                    self.send_registration()
                    
                    # Also check if we've lost contact with GV
                    current_time = time.time()
                    if self.last_gv_contact > 0 and (current_time - self.last_gv_contact) > 10.0:
                        print("[GameClient] ⚠️ Lost contact with Game Viewer - re-registering")
                        self.send_registration()
                        
            except Exception as e:
                if self.running:
                    print(f"[GameClient] Registration loop error: {e}")
                time.sleep(30.0)
    
    def send_ready(self, ready: bool = True):
        """Send ready status"""
        self.is_ready = ready
        message = {
            "type": "READY_STATUS",
            "team_id": self.team_id,
            "ready": ready,
            "timestamp": time.time()
        }
        self._send_to_gv(message)
        print(f"[GameClient] Sent ready status: {ready}")
    
    def send_hit_report(self, hit_data: Dict):
        """Send hit report to Game Viewer"""
        message = {
            "type": "HIT_REPORT",
            "team_id": self.team_id,
            "data": hit_data,
            "timestamp": time.time()
        }
        self._send_to_gv(message)
    
    def send_heartbeat(self):
        """Send heartbeat to Game Viewer"""
        message = {
            "type": "HEARTBEAT",
            "team_id": self.team_id,
            "game_active": self.game_active,
            "points": self.points,
            "timestamp": time.time()
        }
        self._send_to_gv(message)
    
    def _send_to_gv(self, message: Dict):
        """Send message to Game Viewer"""
        try:
            data = json.dumps(message).encode('utf-8')
            self.sock.sendto(data, (self.gv_ip, self.gv_control_port))
        except Exception as e:
            print(f"[GameClient] Failed to send to GV: {e}")
    
    def _listen_loop(self):
        """Listen for messages from Game Viewer"""
        print("[GameClient] Listening for GV messages...")
        
        while self.running:
            try:
                data, addr = self.sock.recvfrom(4096)
                message = json.loads(data.decode('utf-8'))
                self._handle_message(message)
            
            except socket.timeout:
                continue
            except json.JSONDecodeError:
                continue
            except Exception as e:
                if self.running:
                    print(f"[GameClient] Listen error: {e}")
    
    def _handle_message(self, message: Dict):
        """Handle incoming message from Game Viewer"""
        msg_type = message.get('type')
        
        # Update last contact time for any message from GV
        self.last_gv_contact = time.time()
        
        if msg_type == 'DISCOVERY':
            # Game Viewer is looking for robots - respond with registration
            print("[GameClient] 📡 Discovery received - sending registration")
            response = {
                "type": "DISCOVERY_RESPONSE",
                "team_id": self.team_id,
                "team_name": self.team_name,
                "robot_name": self.robot_name,
                "listen_port": self.listen_port,
                "timestamp": time.time()
            }
            self._send_to_gv(response)
        
        elif msg_type == 'HEARTBEAT':
            # GV heartbeat - respond to keep connection alive
            self.last_gv_contact = time.time()
        
        elif msg_type == 'REGISTER_ACK':
            print("[GameClient] ✅ Registration acknowledged")
            self.connected = True
        
        elif msg_type == 'READY_CHECK':
            print("[GameClient] 📢 Ready check received")
            if self.on_ready_check:
                self.on_ready_check()
        
        elif msg_type == 'GAME_START':
            print("[GameClient] 🎮 GAME START!")
            self.game_active = True
            if self.on_game_start:
                self.on_game_start()
        
        elif msg_type == 'GAME_END':
            print("[GameClient] 🏁 GAME END!")
            self.game_active = False
            if self.on_game_end:
                self.on_game_end()
        
        elif msg_type == 'POINTS_UPDATE':
            new_points = message.get('points', 0)
            kills = message.get('kills', 0)
            deaths = message.get('deaths', 0)
            
            self.points = new_points
            self.kills = kills
            self.deaths = deaths
            
            print(f"[GameClient] Points update: {new_points} (K:{kills} D:{deaths})")
            
            if self.on_points_update:
                self.on_points_update(new_points)
        
        elif msg_type == 'PING':
            # Respond to ping
            response = {
                "type": "PONG",
                "team_id": self.team_id,
                "timestamp": time.time()
            }
            self._send_to_gv(response)
    
    def _heartbeat_loop(self):
        """Send periodic heartbeat"""
        while self.running:
            self.send_heartbeat()
            time.sleep(self.heartbeat_interval)
    
    def get_status(self) -> Dict:
        """Get current game status"""
        return {
            "game_active": self.game_active,
            "is_ready": self.is_ready,
            "points": self.points,
            "kills": self.kills,
            "deaths": self.deaths
        }
    
    def stop(self):
        """Stop game client"""
        print("[GameClient] Stopping...")
        self.running = False
        
        if self.listen_thread:
            self.listen_thread.join(timeout=1)
        if self.heartbeat_thread:
            self.heartbeat_thread.join(timeout=1)
        if self.registration_thread:
            self.registration_thread.join(timeout=1)
    
    def cleanup(self):
        """Clean up resources"""
        print("[GameClient] Cleaning up...")
        self.stop()
        self.sock.close()
