#!/usr/bin/env python3
"""
Laptop Control Interface - WASD Keyboard Edition
GUI for robot control with keyboard input, debug mode, and game integration
"""

import json
import os
import socket
import subprocess
import sys
import threading
import time
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from typing import Optional, Dict

# ============ DEFAULT CONFIG ============
DEFAULT_CONFIG = {
    "robot_ip": "192.168.50.147",
    "robot_port": 5005,
    "gv_ip": "192.168.50.143",
    "gv_port": 6000,
    "video_port": 5100,
    "team_id": 1,
    "team_name": "Admin",
    "robot_name": "Admin_Robot",
    "controls": {
        "base_speed": 0.6,
        "boost_speed": 1.0,
        # Customizable key bindings
        "forward": "w",
        "backward": "s",
        "left": "a",
        "right": "d",
        "boost": "shift_l",
        "fire": "space",
        "servo1_up": "q",
        "servo1_down": "z",
        "servo2_up": "e",
        "servo2_down": "c",
        "gpio1_toggle": "1",
        "gpio2_toggle": "2",
        "gpio3_toggle": "3",
        "gpio4_toggle": "4",
        "lights_toggle": "l"
    }
}

CONFIG_FILE = "laptop_config.json"
SEND_HZ = 30

GST_RECEIVER_CMD_TEMPLATE = (
    'gst-launch-1.0 -v udpsrc port={port} caps='
    '"application/x-rtp,media=video,encoding-name=H264,payload=96,clock-rate=90000,packetization-mode=1" '
    '! rtpjitterbuffer latency=50 ! rtph264depay ! h264parse ! d3d11h264dec ! autovideosink sync=false'
)


class Config:
    """Configuration manager"""
    
    def __init__(self):
        self.data = self.load_config()
    
    def load_config(self):
        """Load configuration from file"""
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r') as f:
                    config = json.load(f)
                    print(f"[Config] Loaded from {CONFIG_FILE}")
                    return config
            except Exception as e:
                print(f"[Config] Error loading: {e}")
        
        print("[Config] Using defaults")
        return DEFAULT_CONFIG.copy()
    
    def save_config(self):
        """Save configuration to file"""
        try:
            with open(CONFIG_FILE, 'w') as f:
                json.dump(self.data, f, indent=2)
            print(f"[Config] Saved to {CONFIG_FILE}")
            return True
        except Exception as e:
            print(f"[Config] Error saving: {e}")
            return False
    
    def get(self, *keys):
        """Get nested value"""
        value = self.data
        for key in keys:
            value = value.get(key)
            if value is None:
                return None
        return value
    
    def set(self, value, *keys):
        """Set nested value"""
        d = self.data
        for key in keys[:-1]:
            d = d.setdefault(key, {})
        d[keys[-1]] = value


class KeyboardController:
    """Keyboard input handler for WASD controls"""
    
    def __init__(self, config: Config):
        self.config = config
        
        # Current key states
        self.keys_pressed = set()
        
        # Movement state
        self.vx = 0.0
        self.vy = 0.0
        self.vr = 0.0
        self.boost = False
        
        # Servo positions (0.0 to 1.0)
        self.servo1_pos = 0.5
        self.servo2_pos = 0.5
        
        # GPIO states
        self.gpio_states = [False, False, False, False]
        self.lights_on = False
        
        # Servo control timing
        self.servo_step = 0.05
        self.servo_last_update = 0
        self.servo_update_interval = 0.1  # 100ms
        
        # Fire cooldown
        self.last_fire_time = 0
        self.fire_cooldown = 0.5  # 500ms between shots
        
    def on_key_press(self, event):
        """Handle key press"""
        key = self.normalize_key(event.keysym.lower())
        if key not in self.keys_pressed:
            self.keys_pressed.add(key)
            
            # Handle toggle keys immediately
            self._handle_toggle_key(key)
    
    def on_key_release(self, event):
        """Handle key release"""
        key = self.normalize_key(event.keysym.lower())
        if key in self.keys_pressed:
            self.keys_pressed.remove(key)
    
    def normalize_key(self, key):
        """Normalize key names"""
        # Handle shift variations
        if key in ['shift_l', 'shift_r']:
            return 'shift_l'
        return key
    
    def _handle_toggle_key(self, key):
        """Handle toggle keys (GPIO and lights)"""
        controls = self.config.get('controls')
        
        # GPIO toggles
        for i in range(4):
            if key == controls.get(f'gpio{i+1}_toggle', ''):
                self.gpio_states[i] = not self.gpio_states[i]
                print(f"[Keyboard] GPIO{i+1} = {self.gpio_states[i]}")
        
        # Lights toggle
        if key == controls.get('lights_toggle', ''):
            self.lights_on = not self.lights_on
            print(f"[Keyboard] Lights = {self.lights_on}")
    
    def update(self):
        """Update control state based on pressed keys"""
        controls = self.config.get('controls')
        
        # Reset movement
        self.vx = 0.0
        self.vy = 0.0
        self.vr = 0.0
        self.boost = False
        
        # Check for boost
        if controls.get('boost', 'shift_l') in self.keys_pressed:
            self.boost = True
        
        # Calculate movement
        if controls.get('forward', 'w') in self.keys_pressed:
            self.vy += 1.0
        if controls.get('backward', 's') in self.keys_pressed:
            self.vy -= 1.0
        if controls.get('left', 'a') in self.keys_pressed:
            self.vx -= 1.0
        if controls.get('right', 'd') in self.keys_pressed:
            self.vx += 1.0
        
        # Apply speed multiplier
        speed = self.config.get('controls', 'boost_speed') if self.boost else self.config.get('controls', 'base_speed')
        self.vx *= speed
        self.vy *= speed
        self.vr *= speed
        
        # Update servos (continuous while held)
        current_time = time.time()
        if current_time - self.servo_last_update >= self.servo_update_interval:
            servo_changed = False
            
            # Servo 1
            if controls.get('servo1_up', 'q') in self.keys_pressed:
                self.servo1_pos = min(1.0, self.servo1_pos + self.servo_step)
                servo_changed = True
            if controls.get('servo1_down', 'z') in self.keys_pressed:
                self.servo1_pos = max(0.0, self.servo1_pos - self.servo_step)
                servo_changed = True
            
            # Servo 2
            if controls.get('servo2_up', 'e') in self.keys_pressed:
                self.servo2_pos = min(1.0, self.servo2_pos + self.servo_step)
                servo_changed = True
            if controls.get('servo2_down', 'c') in self.keys_pressed:
                self.servo2_pos = max(0.0, self.servo2_pos - self.servo_step)
                servo_changed = True
            
            if servo_changed:
                self.servo_last_update = current_time
        
        # Fire handling
        fire_pressed = controls.get('fire', 'space') in self.keys_pressed
        
        return {
            'vx': self.vx,
            'vy': self.vy,
            'vr': self.vr,
            'boost': self.boost,
            'fire': fire_pressed,
            'servo1': self.servo1_pos,
            'servo2': self.servo2_pos,
            'gpio': self.gpio_states,
            'lights': self.lights_on
        }
    
    def can_fire(self):
        """Check if enough time has passed to fire again"""
        return time.time() - self.last_fire_time >= self.fire_cooldown
    
    def fire_executed(self):
        """Mark that a fire command was executed"""
        self.last_fire_time = time.time()


class RobotControlGUI:
    """Main GUI application"""
    
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("🤖 Robot Control - WASD Edition")
        self.root.geometry("800x700")
        self.root.configure(bg='#1a1a1a')
        
        # Config
        self.config = Config()
        
        # Keyboard controller
        self.keyboard = KeyboardController(self.config)
        
        # Game state
        self.game_mode = False  # False = Debug mode, True = Game mode
        self.ready_status = False
        self.game_active = False
        self.game_time_remaining = 0
        
        # Network
        self.robot_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.gv_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        
        # Stats
        self.robot_connected = False
        self.gv_connected = False
        self.last_heartbeat = 0
        self.points = 0
        self.hits_taken = 0
        self.shots_fired = 0
        
        # Video stream
        self.video_process: Optional[subprocess.Popen] = None
        
        # Threading
        self.running = True
        self.control_thread = None
        self.gv_listener_thread = None
        
        # Setup GUI
        self.setup_gui()
        
        # Bind keyboard
        self.root.bind('<KeyPress>', self.keyboard.on_key_press)
        self.root.bind('<KeyRelease>', self.keyboard.on_key_release)
        
        # Start control loop
        self.start_control_thread()
        self.start_gv_listener()
        
        # Update GUI
        self.update_gui()
        
        # Cleanup handler
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
    
    def setup_gui(self):
        """Create GUI"""
        # Title
        title = tk.Label(self.root, text="🤖 ROBOT CONTROL STATION",
                        font=('Arial', 20, 'bold'), bg='#1a1a1a', fg='#00ff00')
        title.pack(pady=10)
        
        # Main container
        main_frame = tk.Frame(self.root, bg='#1a1a1a')
        main_frame.pack(fill='both', expand=True, padx=10, pady=5)
        
        # Left side - Info and status
        left_frame = tk.Frame(main_frame, bg='#1a1a1a')
        left_frame.pack(side='left', fill='both', expand=True, padx=5)
        
        # Right side - Controls
        right_frame = tk.Frame(main_frame, bg='#1a1a1a')
        right_frame.pack(side='right', fill='both', padx=5)
        
        # Create sections
        self.create_mode_frame(left_frame)
        self.create_team_info_frame(left_frame)
        self.create_game_status_frame(left_frame)
        self.create_connection_frame(left_frame)
        self.create_stats_frame(left_frame)
        
        self.create_controls_info_frame(right_frame)
        self.create_video_frame(right_frame)
        self.create_settings_button(right_frame)
    
    def create_mode_frame(self, parent):
        """Mode selection frame"""
        frame = tk.LabelFrame(parent, text="🎮 MODE", font=('Arial', 12, 'bold'),
                             bg='#2a2a2a', fg='white', padx=10, pady=10)
        frame.pack(fill='x', pady=5)
        
        self.mode_label = tk.Label(frame, text="DEBUG MODE",
                                   font=('Arial', 16, 'bold'), bg='#2a2a2a', fg='#ffaa00')
        self.mode_label.pack()
        
        mode_info = tk.Label(frame, text="Test your robot freely\nReady up to join the game",
                           font=('Arial', 9), bg='#2a2a2a', fg='#aaaaaa')
        mode_info.pack(pady=5)
        
        btn_frame = tk.Frame(frame, bg='#2a2a2a')
        btn_frame.pack()
        
        self.ready_btn = tk.Button(btn_frame, text="✓ READY UP",
                                   command=self.toggle_ready,
                                   font=('Arial', 12, 'bold'),
                                   bg='#00aa00', fg='white',
                                   width=15, height=2)
        self.ready_btn.pack(side='left', padx=5)
        
        self.unready_btn = tk.Button(btn_frame, text="✗ NOT READY",
                                     command=self.toggle_ready,
                                     font=('Arial', 12, 'bold'),
                                     bg='#aa0000', fg='white',
                                     width=15, height=2,
                                     state='disabled')
        self.unready_btn.pack(side='left', padx=5)
    
    def create_team_info_frame(self, parent):
        """Team info frame"""
        frame = tk.LabelFrame(parent, text="👥 TEAM INFO", font=('Arial', 12, 'bold'),
                             bg='#2a2a2a', fg='white', padx=10, pady=10)
        frame.pack(fill='x', pady=5)
        
        self.team_name_label = tk.Label(frame, text=self.config.get('team_name'),
                                        font=('Arial', 14, 'bold'), bg='#2a2a2a', fg='#00ffff')
        self.team_name_label.pack()
        
        robot_label = tk.Label(frame, text=f"Robot: {self.config.get('robot_name')}",
                              font=('Arial', 10), bg='#2a2a2a', fg='#aaaaaa')
        robot_label.pack()
        
        team_id_label = tk.Label(frame, text=f"Team ID: {self.config.get('team_id')}",
                                font=('Arial', 10), bg='#2a2a2a', fg='#aaaaaa')
        team_id_label.pack()
    
    def create_game_status_frame(self, parent):
        """Game status frame"""
        frame = tk.LabelFrame(parent, text="🎯 GAME STATUS", font=('Arial', 12, 'bold'),
                             bg='#2a2a2a', fg='white', padx=10, pady=10)
        frame.pack(fill='x', pady=5)
        
        self.game_status_label = tk.Label(frame, text="WAITING FOR GAME",
                                          font=('Arial', 14, 'bold'), bg='#2a2a2a', fg='#888888')
        self.game_status_label.pack()
        
        self.timer_label = tk.Label(frame, text="--:--",
                                    font=('Arial', 24, 'bold'), bg='#2a2a2a', fg='#ffffff')
        self.timer_label.pack(pady=5)
        
        self.points_label = tk.Label(frame, text="Points: 0",
                                     font=('Arial', 16, 'bold'), bg='#2a2a2a', fg='#ffff00')
        self.points_label.pack()
    
    def create_connection_frame(self, parent):
        """Connection status frame"""
        frame = tk.LabelFrame(parent, text="🔌 CONNECTION", font=('Arial', 12, 'bold'),
                             bg='#2a2a2a', fg='white', padx=10, pady=10)
        frame.pack(fill='x', pady=5)
        
        self.robot_status = tk.Label(frame, text="🔴 Robot: Disconnected",
                                     font=('Arial', 10), bg='#2a2a2a', fg='#ff0000')
        self.robot_status.pack(anchor='w')
        
        self.gv_status = tk.Label(frame, text="🔴 Game Viewer: Disconnected",
                                 font=('Arial', 10), bg='#2a2a2a', fg='#ff0000')
        self.gv_status.pack(anchor='w')
    
    def create_stats_frame(self, parent):
        """Stats frame"""
        frame = tk.LabelFrame(parent, text="📊 STATISTICS", font=('Arial', 12, 'bold'),
                             bg='#2a2a2a', fg='white', padx=10, pady=10)
        frame.pack(fill='x', pady=5)
        
        self.shots_label = tk.Label(frame, text="Shots Fired: 0",
                                    font=('Arial', 10), bg='#2a2a2a', fg='#aaaaaa')
        self.shots_label.pack(anchor='w')
        
        self.hits_label = tk.Label(frame, text="Hits Taken: 0",
                                   font=('Arial', 10), bg='#2a2a2a', fg='#aaaaaa')
        self.hits_label.pack(anchor='w')
    
    def create_controls_info_frame(self, parent):
        """Controls reference frame"""
        frame = tk.LabelFrame(parent, text="⌨️ KEYBOARD CONTROLS", font=('Arial', 12, 'bold'),
                             bg='#2a2a2a', fg='white', padx=10, pady=10)
        frame.pack(fill='x', pady=5)
        
        controls_text = """
MOVEMENT:
  W - Forward    S - Backward
  A - Left       D - Right
  Shift - Boost

COMBAT:
  Space - Fire Laser

SERVOS:
  Q/Z - Servo 1 Up/Down
  E/C - Servo 2 Up/Down

GPIO:
  1/2/3/4 - Toggle GPIO 1-4
  L - Toggle Lights
        """
        
        controls_label = tk.Label(frame, text=controls_text,
                                 font=('Courier', 9), bg='#2a2a2a', fg='#00ff00',
                                 justify='left')
        controls_label.pack()
        
        # Servo positions
        servo_frame = tk.Frame(frame, bg='#2a2a2a')
        servo_frame.pack(fill='x', pady=5)
        
        tk.Label(servo_frame, text="Servo 1:", font=('Arial', 9),
                bg='#2a2a2a', fg='#aaaaaa').grid(row=0, column=0, sticky='w')
        self.servo1_label = tk.Label(servo_frame, text="50%", font=('Arial', 9, 'bold'),
                                     bg='#2a2a2a', fg='#00ff00')
        self.servo1_label.grid(row=0, column=1, sticky='w', padx=5)
        
        tk.Label(servo_frame, text="Servo 2:", font=('Arial', 9),
                bg='#2a2a2a', fg='#aaaaaa').grid(row=1, column=0, sticky='w')
        self.servo2_label = tk.Label(servo_frame, text="50%", font=('Arial', 9, 'bold'),
                                     bg='#2a2a2a', fg='#00ff00')
        self.servo2_label.grid(row=1, column=1, sticky='w', padx=5)
    
    def create_video_frame(self, parent):
        """Video control frame"""
        frame = tk.LabelFrame(parent, text="📹 VIDEO STREAM", font=('Arial', 12, 'bold'),
                             bg='#2a2a2a', fg='white', padx=10, pady=10)
        frame.pack(fill='x', pady=5)
        
        self.video_status_label = tk.Label(frame, text="Stream: Stopped",
                                           font=('Arial', 10), bg='#2a2a2a', fg='#888888')
        self.video_status_label.pack()
        
        btn_frame = tk.Frame(frame, bg='#2a2a2a')
        btn_frame.pack(pady=5)
        
        self.start_video_btn = tk.Button(btn_frame, text="▶ Start Stream",
                                         command=self.start_video,
                                         bg='#00aa00', fg='white', width=12)
        self.start_video_btn.pack(side='left', padx=2)
        
        self.stop_video_btn = tk.Button(btn_frame, text="⬛ Stop Stream",
                                        command=self.stop_video,
                                        bg='#aa0000', fg='white', width=12,
                                        state='disabled')
        self.stop_video_btn.pack(side='left', padx=2)
    
    def create_settings_button(self, parent):
        """Settings button"""
        settings_btn = tk.Button(parent, text="⚙️ Settings",
                                command=self.open_settings,
                                font=('Arial', 11),
                                bg='#555555', fg='white',
                                width=20, height=2)
        settings_btn.pack(pady=10)
    
    # ============ CONTROL LOGIC ============
    
    def start_control_thread(self):
        """Start control sending thread"""
        self.control_thread = threading.Thread(target=self.control_loop, daemon=True)
        self.control_thread.start()
    
    def control_loop(self):
        """Main control loop - sends commands to robot"""
        rate = 1.0 / SEND_HZ
        
        while self.running:
            start_time = time.time()
            
            try:
                # Get current control state
                state = self.keyboard.update()
                
                # Only send controls in debug mode or during active game
                if not self.game_mode or (self.game_mode and self.game_active):
                    # Build command
                    cmd = {
                        'type': 'CONTROL',
                        'vx': state['vx'],
                        'vy': state['vy'],
                        'vr': state['vr'],
                        'servo1': state['servo1'],
                        'servo2': state['servo2'],
                        'gpio': state['gpio'],
                        'lights': state['lights']
                    }
                    
                    # Handle fire with cooldown
                    if state['fire'] and self.keyboard.can_fire():
                        if not self.game_mode or (self.game_mode and self.game_active):
                            cmd['fire'] = True
                            self.keyboard.fire_executed()
                            self.shots_fired += 1
                    
                    # Send to robot
                    self.send_to_robot(cmd)
                    
                    # Update heartbeat
                    if time.time() - self.last_heartbeat > 1.0:
                        self.send_heartbeat()
                        self.last_heartbeat = time.time()
            
            except Exception as e:
                print(f"[Control] Error: {e}")
            
            # Sleep to maintain rate
            elapsed = time.time() - start_time
            sleep_time = max(0, rate - elapsed)
            time.sleep(sleep_time)
    
    def send_to_robot(self, message):
        """Send message to robot"""
        try:
            data = json.dumps(message).encode('utf-8')
            robot_ip = self.config.get('robot_ip')
            robot_port = self.config.get('robot_port')
            self.robot_sock.sendto(data, (robot_ip, robot_port))
            
            # Debug: Print first message of each type
            msg_type = message.get('type', 'UNKNOWN')
            if not hasattr(self, '_debug_sent_types'):
                self._debug_sent_types = set()
            if msg_type not in self._debug_sent_types:
                self._debug_sent_types.add(msg_type)
                print(f"[Network] First {msg_type} sent to {robot_ip}:{robot_port}")
                
        except Exception as e:
            print(f"[Network] Failed to send to robot: {e}")
    
    def send_heartbeat(self):
        """Send heartbeat to robot"""
        self.send_to_robot({'type': 'HEARTBEAT'})
    
    # ============ GAME VIEWER COMMUNICATION ============
    
    def start_gv_listener(self):
        """Start Game Viewer listener thread"""
        self.gv_listener_thread = threading.Thread(target=self.gv_listener_loop, daemon=True)
        self.gv_listener_thread.start()
    
    def gv_listener_loop(self):
        """Listen for messages from Game Viewer"""
        # Bind to a local port for receiving GV messages
        listen_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        listen_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        listen_sock.settimeout(1.0)
        
        try:
            # Listen on any available port (teams don't need fixed ports)
            listen_sock.bind(('0.0.0.0', 0))
            local_port = listen_sock.getsockname()[1]
            print(f"[GV] Listening on port {local_port}")
            
            # Register with Game Viewer
            self.register_with_gv(local_port)
        except Exception as e:
            print(f"[GV] Failed to bind listener: {e}")
            return
        
        while self.running:
            try:
                data, addr = listen_sock.recvfrom(4096)
                message = json.loads(data.decode('utf-8'))
                self.handle_gv_message(message)
            except socket.timeout:
                continue
            except Exception as e:
                print(f"[GV] Listener error: {e}")
    
    def register_with_gv(self, listen_port):
        """Register this laptop with Game Viewer"""
        message = {
            'type': 'REGISTER',
            'team_id': self.config.get('team_id'),
            'team_name': self.config.get('team_name'),
            'robot_name': self.config.get('robot_name'),
            'listen_port': listen_port
        }
        self.send_to_gv(message)
        print(f"[GV] Sent registration")
    
    def send_to_gv(self, message):
        """Send message to Game Viewer"""
        try:
            data = json.dumps(message).encode('utf-8')
            gv_ip = self.config.get('gv_ip')
            gv_port = self.config.get('gv_port')
            self.gv_sock.sendto(data, (gv_ip, gv_port))
        except Exception as e:
            print(f"[Network] Failed to send to GV: {e}")
    
    def handle_gv_message(self, message):
        """Handle message from Game Viewer"""
        msg_type = message.get('type')
        
        if msg_type == 'READY_CHECK':
            print("[GV] Received ready check")
            # GV is asking if we're ready
            
        elif msg_type == 'GAME_START':
            print("[GV] GAME STARTING!")
            self.game_mode = True
            self.game_active = True
            self.game_time_remaining = message.get('duration', 120)  # Default 2 minutes
            self.points = 0
            self.hits_taken = 0
            self.shots_fired = 0
            
        elif msg_type == 'GAME_END':
            print("[GV] Game ended")
            self.game_active = False
            final_points = message.get('points', self.points)
            self.points = final_points
            
        elif msg_type == 'POINTS_UPDATE':
            self.points = message.get('points', self.points)
            
        elif msg_type == 'HIT_NOTIFICATION':
            self.hits_taken += 1
            print(f"[GV] Hit taken! Total: {self.hits_taken}")
    
    def toggle_ready(self):
        """Toggle ready status"""
        self.ready_status = not self.ready_status
        
        # Send to Game Viewer
        message = {
            'type': 'READY_STATUS',
            'team_id': self.config.get('team_id'),
            'ready': self.ready_status
        }
        self.send_to_gv(message)
        
        # Update UI
        if self.ready_status:
            self.ready_btn.config(state='disabled')
            self.unready_btn.config(state='normal')
            print("[GV] Marked as READY")
        else:
            self.ready_btn.config(state='normal')
            self.unready_btn.config(state='disabled')
            self.game_mode = False
            print("[GV] Marked as NOT READY")
    
    # ============ VIDEO ============
    
    def start_video(self):
        """Start video stream"""
        if self.video_process:
            return
        
        try:
            port = self.config.get('video_port')
            cmd = GST_RECEIVER_CMD_TEMPLATE.format(port=port)
            self.video_process = subprocess.Popen(cmd, shell=True)
            
            self.video_status_label.config(text="Stream: Running", fg='#00ff00')
            self.start_video_btn.config(state='disabled')
            self.stop_video_btn.config(state='normal')
            print(f"[Video] Started stream on port {port}")
        except Exception as e:
            messagebox.showerror("Video Error", f"Failed to start video: {e}")
    
    def stop_video(self):
        """Stop video stream"""
        if self.video_process:
            self.video_process.terminate()
            self.video_process.wait()
            self.video_process = None
            
            self.video_status_label.config(text="Stream: Stopped", fg='#888888')
            self.start_video_btn.config(state='normal')
            self.stop_video_btn.config(state='disabled')
            print("[Video] Stopped stream")
    
    # ============ GUI UPDATE ============
    
    def update_gui(self):
        """Update GUI periodically"""
        if not self.running:
            return
        
        # Update mode
        if self.game_active:
            self.mode_label.config(text="GAME ACTIVE", fg='#ff0000')
            self.game_status_label.config(text="🔥 IN GAME", fg='#ff0000')
        elif self.game_mode:
            self.mode_label.config(text="GAME MODE", fg='#ffaa00')
            self.game_status_label.config(text="⏳ WAITING", fg='#ffaa00')
        else:
            self.mode_label.config(text="DEBUG MODE", fg='#00ff00')
            self.game_status_label.config(text="🛠️ TESTING", fg='#00ff00')
        
        # Update timer
        if self.game_active and self.game_time_remaining > 0:
            self.game_time_remaining -= 0.1
            minutes = int(self.game_time_remaining // 60)
            seconds = int(self.game_time_remaining % 60)
            self.timer_label.config(text=f"{minutes:02d}:{seconds:02d}")
        else:
            self.timer_label.config(text="--:--")
        
        # Update points
        self.points_label.config(text=f"Points: {self.points}")
        
        # Update stats
        self.shots_label.config(text=f"Shots Fired: {self.shots_fired}")
        self.hits_label.config(text=f"Hits Taken: {self.hits_taken}")
        
        # Update servo positions
        servo1_pct = int(self.keyboard.servo1_pos * 100)
        servo2_pct = int(self.keyboard.servo2_pos * 100)
        self.servo1_label.config(text=f"{servo1_pct}%")
        self.servo2_label.config(text=f"{servo2_pct}%")
        
        # Schedule next update
        self.root.after(100, self.update_gui)
    
    # ============ SETTINGS ============
    
    def open_settings(self):
        """Open settings dialog"""
        dialog = SettingsDialog(self.root, self.config)
        if dialog.result:
            # Reload config
            self.config.data = self.config.load_config()
            self.team_name_label.config(text=self.config.get('team_name'))
            print("[Config] Settings updated")
    
    # ============ CLEANUP ============
    
    def on_closing(self):
        """Cleanup on exit"""
        print("[App] Shutting down...")
        self.running = False
        
        # Stop video
        self.stop_video()
        
        # Close sockets
        self.robot_sock.close()
        self.gv_sock.close()
        
        # Wait for threads
        if self.control_thread:
            self.control_thread.join(timeout=1)
        if self.gv_listener_thread:
            self.gv_listener_thread.join(timeout=1)
        
        self.root.destroy()
    
    def run(self):
        """Run the application"""
        self.root.mainloop()


class SettingsDialog:
    """Settings dialog"""
    
    def __init__(self, parent, config: Config):
        self.config = config
        self.result = False
        
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("⚙️ Settings")
        self.dialog.geometry("500x600")
        self.dialog.configure(bg='#2a2a2a')
        self.dialog.transient(parent)
        self.dialog.grab_set()
        
        # Create form
        self.create_form()
        
        # Wait for dialog
        self.dialog.wait_window()
    
    def create_form(self):
        """Create settings form"""
        # Main frame
        main_frame = tk.Frame(self.dialog, bg='#2a2a2a')
        main_frame.pack(fill='both', expand=True, padx=20, pady=20)
        
        # Team settings
        team_frame = tk.LabelFrame(main_frame, text="Team Settings",
                                   bg='#2a2a2a', fg='white', font=('Arial', 11, 'bold'))
        team_frame.pack(fill='x', pady=5)
        
        self.create_field(team_frame, "Team Name:", 'team_name')
        self.create_field(team_frame, "Robot Name:", 'robot_name')
        self.create_field(team_frame, "Team ID:", 'team_id')
        
        # Network settings
        net_frame = tk.LabelFrame(main_frame, text="Network Settings",
                                 bg='#2a2a2a', fg='white', font=('Arial', 11, 'bold'))
        net_frame.pack(fill='x', pady=5)
        
        self.create_field(net_frame, "Robot IP:", 'robot_ip')
        self.create_field(net_frame, "Robot Port:", 'robot_port')
        self.create_field(net_frame, "GV IP:", 'gv_ip')
        self.create_field(net_frame, "GV Port:", 'gv_port')
        self.create_field(net_frame, "Video Port:", 'video_port')
        
        # Speed settings
        speed_frame = tk.LabelFrame(main_frame, text="Speed Settings",
                                   bg='#2a2a2a', fg='white', font=('Arial', 11, 'bold'))
        speed_frame.pack(fill='x', pady=5)
        
        self.create_field(speed_frame, "Base Speed:", ('controls', 'base_speed'))
        self.create_field(speed_frame, "Boost Speed:", ('controls', 'boost_speed'))
        
        # Buttons
        btn_frame = tk.Frame(main_frame, bg='#2a2a2a')
        btn_frame.pack(pady=10)
        
        save_btn = tk.Button(btn_frame, text="💾 Save", command=self.save,
                            bg='#00aa00', fg='white', width=12, height=2)
        save_btn.pack(side='left', padx=5)
        
        cancel_btn = tk.Button(btn_frame, text="✗ Cancel", command=self.cancel,
                              bg='#aa0000', fg='white', width=12, height=2)
        cancel_btn.pack(side='left', padx=5)
    
    def create_field(self, parent, label, config_key):
        """Create a form field"""
        frame = tk.Frame(parent, bg='#2a2a2a')
        frame.pack(fill='x', pady=2, padx=5)
        
        tk.Label(frame, text=label, bg='#2a2a2a', fg='white',
                width=15, anchor='w').pack(side='left')
        
        # Get current value
        if isinstance(config_key, tuple):
            value = self.config.get(*config_key)
        else:
            value = self.config.get(config_key)
        
        entry = tk.Entry(frame, bg='#3a3a3a', fg='white', insertbackground='white')
        entry.insert(0, str(value))
        entry.pack(side='left', fill='x', expand=True)
        
        # Store reference
        if not hasattr(self, 'fields'):
            self.fields = {}
        self.fields[config_key] = entry
    
    def save(self):
        """Save settings"""
        try:
            # Update config
            for key, entry in self.fields.items():
                value = entry.get()
                
                # Convert types
                if key == 'team_id' or (isinstance(key, str) and 'port' in key):
                    value = int(value)
                elif key in [('controls', 'base_speed'), ('controls', 'boost_speed')]:
                    value = float(value)
                
                # Set value
                if isinstance(key, tuple):
                    self.config.set(value, *key)
                else:
                    self.config.set(value, key)
            
            # Save to file
            if self.config.save_config():
                self.result = True
                self.dialog.destroy()
            else:
                messagebox.showerror("Error", "Failed to save configuration")
        
        except ValueError as e:
            messagebox.showerror("Invalid Input", f"Invalid value: {e}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save: {e}")
    
    def cancel(self):
        """Cancel settings"""
        self.dialog.destroy()


# ============ MAIN ============

def main():
    print("=" * 50)
    print("ROBOT CONTROL STATION - WASD Edition")
    print("=" * 50)
    print()
    
    app = RobotControlGUI()
    app.run()


if __name__ == '__main__':
    main()
