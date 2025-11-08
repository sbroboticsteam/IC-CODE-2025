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

# ============ CONFIG ============
# Laptop requests config from Pi at startup - Pi is the single source of truth!

# Default controls (only laptop-specific setting)
DEFAULT_CONTROLS = {
    "base_speed": 0.6,
    "boost_speed": 1.0,
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

SEND_HZ = 30
CONFIG_REQUEST_TIMEOUT = 5.0  # Seconds to wait for Pi to send config

GST_RECEIVER_CMD_TEMPLATE = (
    'gst-launch-1.0 -v udpsrc port={port} caps='
    '"application/x-rtp,media=video,encoding-name=H264,payload=96,clock-rate=90000,packetization-mode=1" '
    '! rtpjitterbuffer latency=50 ! rtph264depay ! h264parse ! d3d11h264dec ! autovideosink sync=false'
)


class Config:
    """Configuration manager - receives config from Pi over UDP"""
    
    def __init__(self, robot_ip: str = None):
        """Initialize config - will request from Pi"""
        self.data = None  # Will be populated by Pi
        self.robot_ip = robot_ip  # Need this to send initial request
        self.controls = self.load_controls()
        self.config_received = False
    
    def set_robot_config(self, config_data: Dict):
        """Set configuration data received from Pi"""
        self.data = config_data
        self.config_received = True
        print(f"[Config] ✅ Received config from Pi")
        print(f"[Config] Team: {config_data.get('team', {}).get('team_name')}")
        print(f"[Config] Robot: {config_data.get('team', {}).get('robot_name')}")
    
    def load_controls(self):
        """Load or create controls configuration"""
        controls_file = "laptop_controls.json"
        if os.path.exists(controls_file):
            try:
                with open(controls_file, 'r') as f:
                    controls = json.load(f)
                    print(f"[Config] Loaded controls from {controls_file}")
                    return controls
            except Exception as e:
                print(f"[Config] Error loading controls: {e}")
        
        print("[Config] Using default controls")
        return DEFAULT_CONTROLS.copy()
    
    def save_controls(self):
        """Save controls configuration"""
        controls_file = "laptop_controls.json"
        try:
            with open(controls_file, 'w') as f:
                json.dump(self.controls, f, indent=2)
            print(f"[Config] Saved controls to {controls_file}")
            return True
        except Exception as e:
            print(f"[Config] Error saving controls: {e}")
            return False
    
    def get(self, *keys):
        """Get nested value from config or controls"""
        # First try controls
        if keys[0] == 'controls':
            if len(keys) == 1:
                return self.controls
            return self.controls.get(keys[1])
        
        # Then try main config
        if self.data is None:
            return None
            
        value = self.data
        for key in keys:
            if isinstance(value, dict):
                value = value.get(key)
            else:
                return None
            if value is None:
                return None
        return value
    
    def set(self, value, *keys):
        """Set nested value in controls"""
        if keys[0] == 'controls':
            if len(keys) == 2:
                self.controls[keys[1]] = value
            return
        
        # For other values, set in main config (though we shouldn't modify team_config.json)
        d = self.data
        for key in keys[:-1]:
            d = d.setdefault(key, {})
        d[keys[-1]] = value
    
    def get_robot_ip(self):
        """Get robot IP"""
        return self.get('network', 'robot_ip')
    
    def get_robot_port(self):
        """Get robot listen port"""
        return self.get('network', 'robot_listen_port')
    
    def get_gv_ip(self):
        """Get game viewer IP"""
        return self.get('network', 'game_viewer_ip')
    
    def get_gv_port(self):
        """Get game viewer control port"""
        return self.get('network', 'game_viewer_control_port')
    
    def get_video_port(self):
        """Get laptop video receive port (constant)"""
        return self.get('network', 'laptop_video_port')
    
    def get_gv_video_port(self):
        """Calculate GV video port: 5000 + team_id"""
        team_id = self.get('team', 'team_id')
        return 5000 + team_id
    
    def get_team_id(self):
        """Get team ID"""
        return self.get('team', 'team_id')
    
    def get_team_name(self):
        """Get team name"""
        return self.get('team', 'team_name')
    
    def get_robot_name(self):
        """Get robot name"""
        return self.get('team', 'robot_name')


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
        
        # Servo toggle states (True = MAX, False = MIN)
        self.servo1_at_max = False
        self.servo2_at_max = False
        
        # GPIO states
        self.gpio_states = [False, False, False, False]
        self.lights_on = False
        
        # Fire cooldown (match Pi's 2s weapon cooldown)
        self.last_fire_time = 0
        self.fire_cooldown = 2.0  # 2000ms to match Pi's IR weapon cooldown
        
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
        """Handle toggle keys (GPIO, lights, and SERVOS)"""
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
        
        # SERVO TOGGLES - Q/Z for servo1, E/C for servo2
        if key == controls.get('servo1_up', 'q'):
            self.servo1_at_max = not self.servo1_at_max
            print(f"[Keyboard] Servo1 toggled to {'MAX' if self.servo1_at_max else 'MIN'}")
        
        if key == controls.get('servo1_down', 'z'):
            self.servo1_at_max = not self.servo1_at_max
            print(f"[Keyboard] Servo1 toggled to {'MAX' if self.servo1_at_max else 'MIN'}")
        
        if key == controls.get('servo2_up', 'e'):
            self.servo2_at_max = not self.servo2_at_max
            print(f"[Keyboard] Servo2 toggled to {'MAX' if self.servo2_at_max else 'MIN'}")
        
        if key == controls.get('servo2_down', 'c'):
            self.servo2_at_max = not self.servo2_at_max
            print(f"[Keyboard] Servo2 toggled to {'MAX' if self.servo2_at_max else 'MIN'}")
    
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
        
        # Calculate movement - MECANUM DRIVE
        # W/S = Forward/Backward (vy)
        # A/D = Strafe Left/Right (vx)
        # Arrow Left/Right = Rotate (vr)
        if controls.get('forward', 'w') in self.keys_pressed:
            self.vy += 1.0  # Forward
        if controls.get('backward', 's') in self.keys_pressed:
            self.vy -= 1.0  # Backward
        if controls.get('left', 'a') in self.keys_pressed:
            self.vx -= 1.0  # Strafe left
        if controls.get('right', 'd') in self.keys_pressed:
            self.vx += 1.0  # Strafe right
        
        # Rotation with arrow keys
        if 'left' in self.keys_pressed:  # Arrow left
            self.vr -= 1.0  # Rotate counter-clockwise
        if 'right' in self.keys_pressed:  # Arrow right
            self.vr += 1.0  # Rotate clockwise
        
        # Apply speed multiplier
        speed = self.config.get('controls', 'boost_speed') if self.boost else self.config.get('controls', 'base_speed')
        self.vx *= speed
        self.vy *= speed
        self.vr *= speed
        
        # Fire handling
        fire_pressed = controls.get('fire', 'space') in self.keys_pressed
        
        return {
            'vx': self.vx,
            'vy': self.vy,
            'vr': self.vr,
            'boost': self.boost,
            'fire': fire_pressed,
            'servo1_toggle': self.servo1_at_max,
            'servo2_toggle': self.servo2_at_max,
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
        
        # Get robot IP from user at startup
        robot_ip = self.prompt_robot_ip()
        
        # Config (will be populated from Pi)
        self.config = Config(robot_ip)
        
        # Keyboard controller
        self.keyboard = KeyboardController(self.config)
        
        # Game state
        self.game_mode = False  # False = Debug mode, True = Game mode
        self.ready_status = False
        self.game_active = False
        self.game_time_remaining = 0
        
        # Disabled state
        self.is_disabled = False
        self.disabled_by = ""
        self.disabled_until = 0
        self.disabled_time_remaining = 0
        
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
        
        # Connection tracking
        self.last_gv_contact = 0
        
        # Video stream
        self.video_process: Optional[subprocess.Popen] = None
        
        # Threading
        self.running = True
        self.control_thread = None
        self.gv_listener_thread = None
        
        # Setup GUI (before requesting config so we can show status)
        self.setup_gui()
        
        # Request config from Pi and wait for response
        self.request_pi_config()
        
        # Update team info now that we have config
        self.update_team_info()
        
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
    
    def prompt_robot_ip(self):
        """Prompt user for robot IP address"""
        # Try to load last used IP
        last_ip_file = "last_robot_ip.txt"
        default_ip = "192.168.50.147"
        
        if os.path.exists(last_ip_file):
            try:
                with open(last_ip_file, 'r') as f:
                    default_ip = f.read().strip()
            except:
                pass
        
        # Hide the main window while prompting
        self.root.withdraw()
        
        robot_ip = simpledialog.askstring(
            "Robot IP Address",
            "Enter the robot's IP address:",
            initialvalue=default_ip
        )
        
        if not robot_ip:
            print("[Config] No robot IP provided - exiting")
            sys.exit(0)
        
        # Save for next time
        try:
            with open(last_ip_file, 'w') as f:
                f.write(robot_ip)
        except:
            pass
        
        # Show main window again
        self.root.deiconify()
        
        return robot_ip
    
    def request_pi_config(self):
        """Request configuration from Pi and wait for response"""
        print("[Config] Requesting configuration from Pi...")
        
        # Send config request
        request = {
            'type': 'CONFIG_REQUEST'
        }
        
        try:
            data = json.dumps(request).encode('utf-8')
            robot_port = 5005  # Default robot listen port
            self.robot_sock.sendto(data, (self.config.robot_ip, robot_port))
            print(f"[Config] Sent config request to {self.config.robot_ip}:{robot_port}")
        except Exception as e:
            print(f"[Config] Failed to send request: {e}")
            messagebox.showerror("Connection Error", 
                f"Failed to contact robot at {self.config.robot_ip}\n{e}")
            sys.exit(1)
        
        # Start listener thread to receive response
        self.robot_listener_thread = threading.Thread(target=self.robot_listener_loop, daemon=True)
        self.robot_listener_thread.start()
        
        # Wait for response (will be handled in robot_listener_loop)
        start_time = time.time()
        while not self.config.config_received:
            time.sleep(0.1)
            self.root.update()  # Keep GUI responsive
            if time.time() - start_time > CONFIG_REQUEST_TIMEOUT:
                messagebox.showerror("Configuration Error",
                    f"No response from robot at {self.config.robot_ip}\n"
                    "Make sure the robot is running and on the network.")
                sys.exit(1)
        
        print("[Config] ✅ Configuration received successfully!")
    
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
        self.create_disabled_frame(left_frame)  # Add disabled status frame
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
    
    def create_disabled_frame(self, parent):
        """Disabled status frame - shows when robot is disabled"""
        self.disabled_frame = tk.LabelFrame(parent, text="⚠️ ROBOT DISABLED", 
                                           font=('Arial', 12, 'bold'),
                                           bg='#ff0000', fg='white', padx=10, pady=10)
        # Don't pack yet - only show when disabled
        
        self.disabled_status_label = tk.Label(self.disabled_frame, 
                                             text="YOU HAVE BEEN HIT!",
                                             font=('Arial', 16, 'bold'), 
                                             bg='#ff0000', fg='white')
        self.disabled_status_label.pack()
        
        self.disabled_by_label = tk.Label(self.disabled_frame, 
                                         text="Disabled by: Unknown",
                                         font=('Arial', 12), 
                                         bg='#ff0000', fg='white')
        self.disabled_by_label.pack(pady=5)
        
        self.disabled_timer_label = tk.Label(self.disabled_frame, 
                                            text="00:00",
                                            font=('Arial', 32, 'bold'), 
                                            bg='#ff0000', fg='white')
        self.disabled_timer_label.pack(pady=10)
        
        self.disabled_info_label = tk.Label(self.disabled_frame, 
                                           text="Controls are locked",
                                           font=('Arial', 10), 
                                           bg='#ff0000', fg='white')
        self.disabled_info_label.pack()
    
    def create_team_info_frame(self, parent):
        """Team info frame"""
        frame = tk.LabelFrame(parent, text="👥 TEAM INFO", font=('Arial', 12, 'bold'),
                             bg='#2a2a2a', fg='white', padx=10, pady=10)
        frame.pack(fill='x', pady=5)
        
        self.team_name_label = tk.Label(frame, text="Waiting for config...",
                                        font=('Arial', 14, 'bold'), bg='#2a2a2a', fg='#00ffff')
        self.team_name_label.pack()
        
        self.robot_label = tk.Label(frame, text=f"Robot: ...",
                              font=('Arial', 10), bg='#2a2a2a', fg='#aaaaaa')
        self.robot_label.pack()
        
        self.team_id_label = tk.Label(frame, text=f"Team ID: ...",
                                font=('Arial', 10), bg='#2a2a2a', fg='#aaaaaa')
        self.team_id_label.pack()
    
    def update_team_info(self):
        """Update team info labels after config is received"""
        if self.config.config_received:
            self.team_name_label.config(text=self.config.get_team_name())
            self.robot_label.config(text=f"Robot: {self.config.get_robot_name()}")
            self.team_id_label.config(text=f"Team ID: {self.config.get_team_id()}")
    
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
MECANUM DRIVE:
  W - Forward       S - Backward
  A - Strafe Left   D - Strafe Right
  ← - Rotate Left   → - Rotate Right
  Shift - Boost

COMBAT:
  Space - Fire Laser

SERVOS (Toggle MIN/MAX):
  Q/Z - Toggle Servo 1
  E/C - Toggle Servo 2

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
        self.servo1_label = tk.Label(servo_frame, text="MIN", font=('Arial', 9, 'bold'),
                                     bg='#2a2a2a', fg='#00ff00')
        self.servo1_label.grid(row=0, column=1, sticky='w', padx=5)
        
        tk.Label(servo_frame, text="Servo 2:", font=('Arial', 9),
                bg='#2a2a2a', fg='#aaaaaa').grid(row=1, column=0, sticky='w')
        self.servo2_label = tk.Label(servo_frame, text="MIN", font=('Arial', 9, 'bold'),
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
                                         bg='#00aa00', fg='white', width=15)
        self.start_video_btn.pack(padx=2)
    
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
        
        # Robot listener is already started in request_pi_config()
        # Don't start it again here!
        
        # Start periodic registration thread
        self.gv_registration_thread = threading.Thread(target=self.gv_registration_loop, daemon=True)
        self.gv_registration_thread.start()
    
    def gv_registration_loop(self):
        """Periodic registration with Game Viewer - ONLY IF DISCONNECTED"""
        # Initial registration happens in gv_listener_loop
        # This loop only re-registers if connection is lost
        
        while self.running:
            try:
                # Check connection status every 5 seconds
                time.sleep(5.0)
                
                if not self.running:
                    break
                
                # ONLY re-register if we've lost connection (no heartbeat for 15+ seconds)
                current_time = time.time()
                if not self.gv_connected and self.last_gv_contact > 0:
                    if (current_time - self.last_gv_contact) > 15.0:
                        print("[GV] 🔄 Connection lost - attempting re-registration...")
                        local_port = 6100 + self.config.get_team_id()
                        self.register_with_gv(local_port)
                        time.sleep(5.0)  # Wait before next attempt
                        
            except Exception as e:
                if self.running:
                    print(f"[GV] Registration loop error: {e}")
                time.sleep(5.0)
    
    def robot_listener_loop(self):
        """Listen for status responses from robot"""
        # Use the SAME socket that sends commands (self.robot_sock)
        # This way Pi responses come back to the right place
        self.robot_sock.settimeout(1.0)
        
        last_response_time = 0
        
        while self.running:
            try:
                data, addr = self.robot_sock.recvfrom(4096)
                message = json.loads(data.decode('utf-8'))
                
                msg_type = message.get('type')
                
                # Update connection status for ANY message from robot
                current_time = time.time()
                self.robot_connected = True
                last_response_time = current_time
                
                # Handle config response
                if msg_type == 'CONFIG_RESPONSE':
                    config_data = message.get('config')
                    if config_data:
                        self.config.set_robot_config(config_data)
                    continue
                
                # Handle STATUS response with fire confirmation
                if msg_type == 'STATUS':
                    # Only count shot if Pi confirms fire actually happened
                    if message.get('fire_success', False):
                        self.shots_fired += 1
                        print(f"[Robot] 🔥 Shot fired! Total: {self.shots_fired}")
                    
                    # CHECK IR STATUS FROM PI - SYNC DISABLED STATE!
                    # This works TOGETHER with GV's ROBOT_DISABLED message
                    # Pi is the SOURCE OF TRUTH for hit state, GV handles scoring
                    ir_status = message.get('ir_status', {})
                    if ir_status:
                        pi_is_hit = ir_status.get('is_hit', False)
                        time_remaining = ir_status.get('time_remaining', 0)
                        
                        # If Pi says we're hit but laptop doesn't know - SYNC IT!
                        if pi_is_hit and not self.is_disabled:
                            hit_by_team = ir_status.get('hit_by_team', 0)
                            
                            print(f"[Robot] 💥 SYNCING DISABLED STATE from Pi! Hit by Team {hit_by_team}, {time_remaining:.1f}s remaining")
                            self.is_disabled = True
                            self.disabled_by = f"Team {hit_by_team}"
                            self.disabled_until = time.time() + time_remaining
                            # Don't increment hits_taken here - GV will send POINTS_UPDATE with deaths count
                        
                        # If Pi says we're NOT hit but laptop thinks we are - CLEAR IT!
                        elif not pi_is_hit and self.is_disabled:
                            print(f"[Robot] ✅ SYNCING ENABLED STATE from Pi - respawned!")
                            self.is_disabled = False
                            self.disabled_by = ""
                            self.disabled_until = 0
                            self.disabled_time_remaining = 0
                    
                    continue
                
                # Debug: Print first response
                if not hasattr(self, '_debug_robot_response'):
                    self._debug_robot_response = True
                    print(f"[Robot] ✅ First response received from {addr}")
                    
            except socket.timeout:
                # Check if connection timed out
                if time.time() - last_response_time > 3.0:
                    if self.robot_connected:  # Only print once
                        print("[Robot] ⚠️ Connection timeout")
                    self.robot_connected = False
                continue
            except Exception as e:
                if not hasattr(self, '_debug_listener_error'):
                    self._debug_listener_error = True
                    print(f"[Robot] Listener error: {e}")
    
    def control_loop(self):
        """Main control loop - sends commands to robot"""
        rate = 1.0 / SEND_HZ
        
        while self.running:
            start_time = time.time()
            
            try:
                # Get current control state
                state = self.keyboard.update()
                
                # Check if robot is disabled OR ready but game not started - if so, send stop commands
                if self.is_disabled or (self.ready_status and not self.game_active):
                    # Send all-stop command
                    cmd = {
                        'type': 'CONTROL',
                        'vx': 0,
                        'vy': 0,
                        'vr': 0,
                        'servo1_toggle': state['servo1_toggle'],  # Allow servo control when disabled
                        'servo2_toggle': state['servo2_toggle'],
                        'gpio': [False, False, False, False],  # Turn off all GPIO
                        'lights': False  # Turn off lights
                    }
                    self.send_to_robot(cmd)
                
                # Only send controls in debug mode or during active game
                elif not self.game_mode or (self.game_mode and self.game_active):
                    # Build command
                    cmd = {
                        'type': 'CONTROL',
                        'vx': state['vx'],
                        'vy': state['vy'],
                        'vr': state['vr'],
                        'servo1_toggle': state['servo1_toggle'],
                        'servo2_toggle': state['servo2_toggle'],
                        'gpio': state['gpio'],
                        'lights': state['lights']
                    }
                    
                    # Handle fire with cooldown (Pi has 2s cooldown, don't count here)
                    if state['fire'] and self.keyboard.can_fire():
                        if not self.game_mode or (self.game_mode and self.game_active):
                            cmd['fire'] = True
                            self.keyboard.fire_executed()
                            # Don't increment shots here - wait for Pi confirmation via fire_success
                    
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
            robot_ip = self.config.get_robot_ip()
            robot_port = self.config.get_robot_port()
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
        # Bind to a fixed port for receiving GV messages
        listen_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        listen_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        listen_sock.settimeout(1.0)
        
        try:
            # Use fixed port: 6100 + team_id
            local_port = 6100 + self.config.get_team_id()
            listen_sock.bind(('0.0.0.0', local_port))
            print(f"[GV] Listening on port {local_port}")
            
            # Register with Game Viewer
            self.register_with_gv(local_port)
        except Exception as e:
            print(f"[GV] Failed to bind listener: {e}")
            return
        
        # Start with current time to avoid immediate timeout
        self.last_gv_contact = time.time()
        last_gv_message_time = time.time()
        
        while self.running:
            try:
                data, addr = listen_sock.recvfrom(4096)
                message = json.loads(data.decode('utf-8'))
                
                # Update GV connection status
                self.gv_connected = True
                self.last_gv_contact = time.time()  # Track last contact time
                last_gv_message_time = time.time()
                
                # Debug: Print first GV message
                if not hasattr(self, '_debug_gv_msg'):
                    self._debug_gv_msg = True
                    print(f"[GV] ✅ First message received from {addr}")
                
                self.handle_gv_message(message)
            except socket.timeout:
                # Check if GV connection timed out (no messages for 10+ seconds)
                # GV sends heartbeats every 1 second, so 10s is very generous
                if time.time() - last_gv_message_time > 10.0:
                    if self.gv_connected:  # Only print once when transitioning
                        print("[GV] ⚠️ Connection timeout - no messages for 10+ seconds")
                    self.gv_connected = False
                continue
            except Exception as e:
                print(f"[GV] Listener error: {e}")
    
    def register_with_gv(self, listen_port):
        """Register this laptop with Game Viewer"""
        message = {
            'type': 'REGISTER',
            'team_id': self.config.get_team_id(),
            'team_name': self.config.get_team_name(),
            'robot_name': self.config.get_robot_name(),
            'listen_port': listen_port
        }
        self.send_to_gv(message)
        print(f"[GV] Sent registration")
    
    def send_to_gv(self, message):
        """Send message to Game Viewer"""
        try:
            data = json.dumps(message).encode('utf-8')
            gv_ip = self.config.get_gv_ip()
            gv_port = self.config.get_gv_port()
            self.gv_sock.sendto(data, (gv_ip, gv_port))
        except Exception as e:
            print(f"[Network] Failed to send to GV: {e}")
    
    def handle_gv_message(self, message):
        """Handle message from Game Viewer"""
        msg_type = message.get('type')
        
        # Update last contact time for any message from GV
        self.last_gv_contact = time.time()
        
        if msg_type == 'DISCOVERY':
            # Game Viewer is looking for laptops - respond with registration
            print("[GV] 📡 Discovery received - sending registration")
            local_port = 6100 + self.config.get_team_id()
            self.register_with_gv(local_port)
        
        elif msg_type == 'HEARTBEAT':
            # GV keepalive - update connection status silently
            # Debug: Print first few heartbeats to confirm reception
            if not hasattr(self, '_debug_heartbeat_count'):
                self._debug_heartbeat_count = 0
            if self._debug_heartbeat_count < 3:
                self._debug_heartbeat_count += 1
                print(f"[GV] ✅ Heartbeat received ({self._debug_heartbeat_count}/3)")
            pass
        
        elif msg_type == 'REGISTER_ACK':
            print("[GV] Registration acknowledged")
        
        elif msg_type == 'READY_CHECK':
            print(f"[GV] Received ready check - Current status: {self.ready_status}")
            # Only respond if we're actually ready
            if self.ready_status:
                response = {
                    'type': 'READY_RESPONSE',
                    'team_id': self.config.get('team_id'),
                    'ready': True
                }
                self.send_to_gv(response)
                print("[GV] Sent READY response")
            else:
                print("[GV] Not ready - no response sent")
        
        elif msg_type == 'FORCE_READY':
            # Game Viewer is forcing us into ready state for match start
            reason = message.get('reason', 'No reason given')
            print(f"[GV] 🔧 ================================")
            print(f"[GV] 🔧 FORCE_READY RECEIVED!")
            print(f"[GV] 🔧 Reason: {reason}")
            print(f"[GV] 🔧 Team ID: {message.get('team_id', 'unknown')}")
            print(f"[GV] 🔧 Current ready_status: {self.ready_status}")
            print(f"[GV] 🔧 ================================")
            
            # Force into ready state
            self.ready_status = True
            self.game_mode = True
            
            # Update UI buttons on main thread
            self.root.after(0, lambda: self.ready_btn.config(state='disabled'))
            self.root.after(0, lambda: self.unready_btn.config(state='normal'))
            
            print(f"[GV] ✅ Forced into READY state - Robot movement LOCKED")
            print(f"[GV] ✅ New ready_status: {self.ready_status}")
            print(f"[GV] ✅ New game_mode: {self.game_mode}")
            
        elif msg_type == 'GAME_START':
            # Game Viewer already forced us ready, so just start the game
            duration = message.get('duration', 120)
            print(f"[GV] 📢 ================================")
            print(f"[GV] 📢 GAME_START RECEIVED!")
            print(f"[GV] 📢 Duration: {duration}s")
            print(f"[GV] 📢 Current ready_status: {self.ready_status}")
            print(f"[GV] 📢 Current game_mode: {self.game_mode}")
            print(f"[GV] 📢 ================================")
            
            self.game_mode = True
            self.game_active = True
            self.game_time_remaining = duration
            self.points = 0
            self.hits_taken = 0
            self.shots_fired = 0
            
            # Forward GAME_START to Pi
            pi_message = {
                'type': 'GAME_START',
                'duration': duration
            }
            self.send_to_robot(pi_message)
            
            print(f"[GV] ✅ Game started! Duration: {duration}s")
            print(f"[GV] ✅ Forwarded GAME_START to Pi")
            
        elif msg_type == 'GAME_END':
            print("[GV] Game ended")
            self.game_active = False
            final_points = message.get('points', self.points)
            self.points = final_points
            
            # Forward GAME_END to Pi to put robot into standby
            pi_message = {
                'type': 'GAME_END'
            }
            self.send_to_robot(pi_message)
            
            # Keep game_mode True and ready_status True so robot stays locked
            # User must click "Not Ready" to return to debug mode
            print("[GV] ⏸️ WAITING MODE - Click 'Not Ready' to return to debug mode")
            
        elif msg_type == 'POINTS_UPDATE':
            # Update points, kills, and deaths from GV
            self.points = message.get('points', self.points)
            # Update hits_taken (deaths) if provided
            if 'deaths' in message:
                self.hits_taken = message['deaths']
            print(f"[GV] Points updated: {self.points} (Deaths: {self.hits_taken})")
            
        elif msg_type == 'HIT_NOTIFICATION':
            self.hits_taken += 1
            print(f"[GV] Hit taken! Total: {self.hits_taken}")
        
        elif msg_type == 'ROBOT_DISABLED':
            # Robot has been disabled by enemy hit (from GV)
            # This works TOGETHER with Pi's ir_status sync
            # GV provides team name, Pi provides hit state
            # Only update if we're not already disabled (avoid override)
            if not self.is_disabled:
                self.is_disabled = True
                self.disabled_by = message.get('disabled_by', 'Unknown')
                self.disabled_until = message.get('disabled_until', 0)
                duration = message.get('duration', 10)
                print(f"[GV] 💥 DISABLED by {self.disabled_by} for {duration}s!")
            else:
                # Already disabled from Pi sync - just update the name
                friendly_name = message.get('disabled_by', 'Unknown')
                if self.disabled_by.startswith('Team ') and friendly_name != 'Unknown':
                    self.disabled_by = friendly_name
                    print(f"[GV] Updated disabled-by name: {friendly_name}")
        
        elif msg_type == 'ROBOT_ENABLED':
            # Robot has been re-enabled
            self.is_disabled = False
            self.disabled_by = ""
            self.disabled_until = 0
            self.disabled_time_remaining = 0
            print("[GV] ROBOT RE-ENABLED!")
    
    def toggle_ready(self):
        """Toggle ready status"""
        self.ready_status = not self.ready_status
        
        # Send to Game Viewer
        message = {
            'type': 'READY_STATUS',
            'team_id': self.config.get_team_id(),
            'ready': self.ready_status
        }
        self.send_to_gv(message)
        
        # Update UI
        if self.ready_status:
            self.ready_btn.config(state='disabled')
            self.unready_btn.config(state='normal')
            print("[GV] Marked as READY - Robot movement locked until game starts")
        else:
            self.ready_btn.config(state='normal')
            self.unready_btn.config(state='disabled')
            self.game_mode = False
            self.game_active = False  # Also clear game_active
            print("[GV] Marked as NOT READY - Returning to DEBUG MODE")
    
    # ============ VIDEO ============
    
    def start_video(self):
        """Start video stream"""
        if self.video_process:
            return
        
        try:
            port = self.config.get_video_port()
            cmd = GST_RECEIVER_CMD_TEMPLATE.format(port=port)
            self.video_process = subprocess.Popen(cmd, shell=True)
            
            self.video_status_label.config(text="Stream: Running", fg='#00ff00')
            self.start_video_btn.config(state='disabled')
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
            print("[Video] Stopped stream")
    
    # ============ GUI UPDATE ============
    
    def update_gui(self):
        """Update GUI periodically"""
        if not self.running:
            return
        
        # Update disabled state
        if self.is_disabled:
            # Calculate time remaining
            current_time = time.time()
            self.disabled_time_remaining = max(0, self.disabled_until - current_time)
            
            # CHECK IF TIMER EXPIRED - AUTO RE-ENABLE!
            if self.disabled_time_remaining <= 0:
                print("[Laptop] ✅ Disabled timer expired - RE-ENABLING ROBOT!")
                self.is_disabled = False
                self.disabled_by = ""
                self.disabled_until = 0
                self.disabled_time_remaining = 0
            else:
                # Show disabled frame if not already shown
                if not self.disabled_frame.winfo_ismapped():
                    self.disabled_frame.pack(fill='x', pady=5, after=self.mode_label.master)
                
                # Update disabled info
                self.disabled_by_label.config(text=f"Disabled by: {self.disabled_by}")
                seconds = int(self.disabled_time_remaining)
                millis = int((self.disabled_time_remaining % 1) * 10)
                self.disabled_timer_label.config(text=f"{seconds:02d}.{millis:01d}")
                
                # Apply red theme to main frames
                self.root.configure(bg='#330000')
            
        else:
            # Hide disabled frame if shown
            if self.disabled_frame.winfo_ismapped():
                self.disabled_frame.pack_forget()
            
            # Restore normal theme
            self.root.configure(bg='#1a1a1a')
        
        # Update connection status
        if self.robot_connected:
            self.robot_status.config(text="🟢 Robot: Connected", fg='#00ff00')
        else:
            self.robot_status.config(text="🔴 Robot: Disconnected", fg='#ff0000')
        
        if self.gv_connected:
            self.gv_status.config(text="🟢 Game Viewer: Connected", fg='#00ff00')
        else:
            self.gv_status.config(text="🔴 Game Viewer: Disconnected", fg='#ff0000')
        
        # Update mode
        if self.game_active:
            self.mode_label.config(text="GAME ACTIVE", fg='#ff0000')
            self.game_status_label.config(text="🔥 IN GAME", fg='#ff0000')
        elif self.ready_status and not self.game_active:
            # Ready but game hasn't started yet (or just ended - WAITING mode)
            self.mode_label.config(text="WAITING MODE", fg='#ffaa00')
            self.game_status_label.config(text="⏸️ STANDBY", fg='#ffaa00')
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
        
        # Update servo positions (show MIN/MAX instead of percentage)
        servo1_pos = "MAX" if self.keyboard.servo1_at_max else "MIN"
        servo2_pos = "MAX" if self.keyboard.servo2_at_max else "MIN"
        self.servo1_label.config(text=f"{servo1_pos}")
        self.servo2_label.config(text=f"{servo2_pos}")
        
        # Schedule next update
        self.root.after(100, self.update_gui)
    
    # ============ SETTINGS ============
    
    def open_settings(self):
        """Open settings dialog"""
        dialog = SettingsDialog(self.root, self.config)
        if dialog.result:
            # Reload controls
            self.config.controls = self.config.load_controls()
            self.team_name_label.config(text=self.config.get_team_name())
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
        if hasattr(self, 'gv_registration_thread') and self.gv_registration_thread:
            self.gv_registration_thread.join(timeout=1)
        
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
