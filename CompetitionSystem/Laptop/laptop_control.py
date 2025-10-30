#!/usr/bin/env python3
"""
Laptop Control Interface
Enhanced GUI for robot control with settings, video feed, and game integration
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
import pygame

# ============ DEFAULT CONFIG ============
DEFAULT_CONFIG = {
    "robot_ip": "192.168.1.10",
    "robot_port": 5005,
    "video_port": 5100,
    "team_id": 1,
    "team_name": "Team Alpha",
    "robot_name": "Alpha-1",
    "controller": {
        "deadzone": 0.12,
        "base_speed": 0.6,
        "boost_speed": 1.0,
        "slow_speed": 0.3
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


class XboxController:
    """Xbox controller handler"""
    
    def __init__(self, config: Config):
        pygame.init()
        pygame.joystick.init()
        
        self.config = config
        self.joystick = None
        self.connected = False
        self.last_input_time = time.time()
        
        # Controller state
        self.vx = 0.0
        self.vy = 0.0
        self.omega = 0.0
        self.speed = config.get('controller', 'base_speed')
        self.estop = False
        self.fire = False
        self.fire_last_state = False
        
        # Servo control
        self.servo_1 = 0.0
        self.servo_2 = 0.0
        
        self.connect_controller()
    
    def connect_controller(self):
        """Connect to Xbox controller"""
        try:
            pygame.joystick.quit()
            pygame.joystick.init()
            
            if pygame.joystick.get_count() == 0:
                print("[Controller] No controllers found")
                self.connected = False
                return False
            
            self.joystick = pygame.joystick.Joystick(0)
            self.joystick.init()
            self.connected = True
            print(f"[Controller] Connected: {self.joystick.get_name()}")
            return True
        
        except Exception as e:
            print(f"[Controller] Failed: {e}")
            self.connected = False
            return False
    
    def apply_deadzone(self, value):
        """Apply deadzone to analog input"""
        deadzone = self.config.get('controller', 'deadzone')
        return value if abs(value) > deadzone else 0.0
    
    def clamp(self, x, lo=-1.0, hi=1.0):
        """Clamp value"""
        return max(lo, min(hi, x))
    
    def update(self):
        """Update controller state"""
        if not self.connected:
            return None
        
        try:
            pygame.event.pump()
            
            if not self.joystick.get_init():
                print("[Controller] Disconnected")
                self.connected = False
                return "reconnect"
            
            # Read axes
            lx = self.apply_deadzone(self.joystick.get_axis(0))  # Left X
            ly = self.apply_deadzone(self.joystick.get_axis(1))  # Left Y
            rx = self.apply_deadzone(self.joystick.get_axis(2))  # Right X
            
            # Read triggers
            try:
                lt = (self.joystick.get_axis(4) + 1) / 2  # Left trigger
                rt = (self.joystick.get_axis(5) + 1) / 2  # Right trigger
            except:
                lt = 0.0
                rt = 0.0
            
            # Movement
            self.vx = self.clamp(-ly)
            self.vy = self.clamp(lx)
            self.omega = self.clamp(-rx)
            
            # Speed control
            lb = bool(self.joystick.get_button(4))
            base_speed = self.config.get('controller', 'base_speed')
            boost_speed = self.config.get('controller', 'boost_speed')
            slow_speed = self.config.get('controller', 'slow_speed')
            
            if rt > 0.1:
                self.speed = base_speed + (boost_speed - base_speed) * rt
            elif lb:
                self.speed = boost_speed
            elif lt > 0.1:
                self.speed = base_speed - (base_speed - slow_speed) * lt
            else:
                self.speed = base_speed
            
            # Buttons
            self.estop = bool(self.joystick.get_button(1))  # B
            
            # Fire with edge detection
            fire_current = bool(self.joystick.get_button(0)) or bool(self.joystick.get_button(5))  # A or RB
            self.fire = fire_current and not self.fire_last_state
            self.fire_last_state = fire_current
            
            # Servo control (D-pad)
            try:
                hat = self.joystick.get_hat(0)
                if hat[1] != 0:  # Up/Down
                    self.servo_1 = self.clamp(self.servo_1 + hat[1] * 0.1)
                if hat[0] != 0:  # Left/Right
                    self.servo_2 = self.clamp(self.servo_2 + hat[0] * 0.1)
            except:
                pass
            
            # Update input time
            if (abs(self.vx) > 0.05 or abs(self.vy) > 0.05 or abs(self.omega) > 0.05 or 
                self.estop or lb or rt > 0.1 or lt > 0.1 or self.fire):
                self.last_input_time = time.time()
            
            # Special buttons
            if self.joystick.get_button(7):  # START
                return "quit"
            if self.joystick.get_button(6):  # BACK
                return "reconnect"
        
        except Exception as e:
            print(f"[Controller] Error: {e}")
            self.connected = False
            return "reconnect"
        
        return None


class RobotControlGUI:
    """Main GUI application"""
    
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("🎯 Laser Tag Robot Control - Competition System")
        self.root.geometry("1000x800")
        self.root.configure(bg='#1e1e1e')
        
        # Configuration
        self.config = Config()
        
        # Controller
        self.controller = XboxController(self.config)
        
        # Network
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.robot_addr = (
            self.config.get('robot_ip'),
            self.config.get('robot_port')
        )
        
        # Video
        self.gst_proc = None
        self.video_active = False
        
        # State
        self.running = True
        self.last_successful_send = 0
        self.robot_status = {
            "ir_status": {"is_hit": False, "hit_by_team": 0, "time_remaining": 0, "total_hits": 0},
            "game_status": {"game_active": False, "is_ready": False, "points": 0, "kills": 0, "deaths": 0},
            "camera_active": False
        }
        
        # Setup GUI
        self.setup_gui()
        
        # Start loops
        self.start_control_loop()
        
        # Cleanup handler
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
    
    def setup_gui(self):
        """Create GUI"""
        # Main container
        main_frame = tk.Frame(self.root, bg='#1e1e1e')
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Title
        title_frame = tk.Frame(main_frame, bg='#1e1e1e')
        title_frame.pack(fill=tk.X, pady=(0, 10))
        
        tk.Label(title_frame, text="🎯 LASER TAG ROBOT CONTROL", 
                font=('Arial', 24, 'bold'), bg='#1e1e1e', fg='#00ff00').pack()
        
        # Content area
        content_frame = tk.Frame(main_frame, bg='#1e1e1e')
        content_frame.pack(fill=tk.BOTH, expand=True)
        
        # Left panel
        left_panel = tk.Frame(content_frame, bg='#1e1e1e')
        left_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))
        
        # Right panel
        right_panel = tk.Frame(content_frame, bg='#1e1e1e')
        right_panel.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(5, 0))
        
        # ==== LEFT PANEL ====
        self.create_team_info_frame(left_panel)
        self.create_game_status_frame(left_panel)
        self.create_robot_status_frame(left_panel)
        self.create_connection_frame(left_panel)
        self.create_controls_frame(left_panel)
        
        # ==== RIGHT PANEL ====
        self.create_stats_frame(right_panel)
        self.create_values_frame(right_panel)
        self.create_buttons_frame(right_panel)
        self.create_instructions_frame(right_panel)
    
    def create_team_info_frame(self, parent):
        """Team information"""
        frame = tk.LabelFrame(parent, text="👥 Team Information", 
                             font=('Arial', 12, 'bold'), bg='#2d2d2d', fg='#00ff00')
        frame.pack(fill=tk.X, pady=5)
        
        info_text = f"""Team: {self.config.get('team_name')}
Robot: {self.config.get('robot_name')}
Team ID: {self.config.get('team_id')}"""
        
        tk.Label(frame, text=info_text, font=('Arial', 10), 
                bg='#2d2d2d', fg='white', justify=tk.LEFT).pack(padx=10, pady=10)
    
    def create_game_status_frame(self, parent):
        """Game status display"""
        frame = tk.LabelFrame(parent, text="🎮 Game Status", 
                             font=('Arial', 12, 'bold'), bg='#2d2d2d', fg='#00ff00')
        frame.pack(fill=tk.X, pady=5)
        
        self.game_status_label = tk.Label(frame, text="Status: Waiting for Game", 
                                          font=('Arial', 12, 'bold'), bg='#2d2d2d', fg='yellow')
        self.game_status_label.pack(pady=5)
        
        self.ready_label = tk.Label(frame, text="Ready: No", 
                                   font=('Arial', 10), bg='#2d2d2d', fg='white')
        self.ready_label.pack(pady=2)
    
    def create_robot_status_frame(self, parent):
        """Robot hit status"""
        frame = tk.LabelFrame(parent, text="⚔️ Combat Status", 
                             font=('Arial', 12, 'bold'), bg='#2d2d2d', fg='#00ff00')
        frame.pack(fill=tk.X, pady=5)
        
        self.hit_status_label = tk.Label(frame, text="Robot: Active", 
                                        font=('Arial', 12, 'bold'), bg='#2d2d2d', fg='lime')
        self.hit_status_label.pack(pady=5)
        
        self.hit_info_label = tk.Label(frame, text="", 
                                      font=('Arial', 10), bg='#2d2d2d', fg='white')
        self.hit_info_label.pack(pady=2)
        
        self.respawn_label = tk.Label(frame, text="", 
                                     font=('Arial', 10), bg='#2d2d2d', fg='yellow')
        self.respawn_label.pack(pady=2)
    
    def create_connection_frame(self, parent):
        """Connection status"""
        frame = tk.LabelFrame(parent, text="📡 Connection", 
                             font=('Arial', 12, 'bold'), bg='#2d2d2d', fg='#00ff00')
        frame.pack(fill=tk.X, pady=5)
        
        self.controller_status = tk.Label(frame, text="Controller: Disconnected", 
                                         font=('Arial', 10), bg='#2d2d2d', fg='red')
        self.controller_status.pack(pady=5)
        
        self.robot_connection = tk.Label(frame, text="Robot: Disconnected", 
                                        font=('Arial', 10), bg='#2d2d2d', fg='red')
        self.robot_connection.pack(pady=2)
        
        self.camera_status = tk.Label(frame, text="Camera: Not Streaming", 
                                     font=('Arial', 10), bg='#2d2d2d', fg='gray')
        self.camera_status.pack(pady=2)
    
    def create_controls_frame(self, parent):
        """Controller values"""
        frame = tk.LabelFrame(parent, text="📊 Controller Input", 
                             font=('Arial', 12, 'bold'), bg='#2d2d2d', fg='#00ff00')
        frame.pack(fill=tk.X, pady=5)
        
        self.vx_label = tk.Label(frame, text="Forward/Back: 0.00", 
                                font=('Arial', 9), bg='#2d2d2d', fg='white')
        self.vx_label.pack(pady=1)
        
        self.vy_label = tk.Label(frame, text="Strafe L/R: 0.00", 
                                font=('Arial', 9), bg='#2d2d2d', fg='white')
        self.vy_label.pack(pady=1)
        
        self.omega_label = tk.Label(frame, text="Rotate: 0.00", 
                                   font=('Arial', 9), bg='#2d2d2d', fg='white')
        self.omega_label.pack(pady=1)
        
        self.speed_label = tk.Label(frame, text="Speed: 0.60", 
                                   font=('Arial', 9), bg='#2d2d2d', fg='white')
        self.speed_label.pack(pady=1)
        
        self.servo_labels = [
            tk.Label(frame, text="Servo 1: 0.00", font=('Arial', 9), bg='#2d2d2d', fg='white'),
            tk.Label(frame, text="Servo 2: 0.00", font=('Arial', 9), bg='#2d2d2d', fg='white')
        ]
        for label in self.servo_labels:
            label.pack(pady=1)
    
    def create_stats_frame(self, parent):
        """Game statistics"""
        frame = tk.LabelFrame(parent, text="📈 Statistics", 
                             font=('Arial', 12, 'bold'), bg='#2d2d2d', fg='#00ff00')
        frame.pack(fill=tk.X, pady=5)
        
        self.points_label = tk.Label(frame, text="Points: 0", 
                                    font=('Arial', 14, 'bold'), bg='#2d2d2d', fg='gold')
        self.points_label.pack(pady=5)
        
        self.kd_label = tk.Label(frame, text="K/D: 0/0 (0.00)", 
                                font=('Arial', 11), bg='#2d2d2d', fg='white')
        self.kd_label.pack(pady=2)
        
        self.hits_label = tk.Label(frame, text="Hits Taken: 0", 
                                  font=('Arial', 10), bg='#2d2d2d', fg='white')
        self.hits_label.pack(pady=2)
    
    def create_values_frame(self, parent):
        """Extended values"""
        frame = tk.LabelFrame(parent, text="⚙️ System", 
                             font=('Arial', 12, 'bold'), bg='#2d2d2d', fg='#00ff00')
        frame.pack(fill=tk.X, pady=5)
        
        self.fire_label = tk.Label(frame, text="🔫 Weapon: Ready", 
                                  font=('Arial', 11), bg='#2d2d2d', fg='white')
        self.fire_label.pack(pady=5)
        
        self.estop_label = tk.Label(frame, text="Emergency Stop: OFF", 
                                   font=('Arial', 10), bg='#2d2d2d', fg='white')
        self.estop_label.pack(pady=2)
    
    def create_buttons_frame(self, parent):
        """Action buttons"""
        frame = tk.Frame(parent, bg='#1e1e1e')
        frame.pack(fill=tk.X, pady=10)
        
        # Row 1
        row1 = tk.Frame(frame, bg='#1e1e1e')
        row1.pack(fill=tk.X, pady=2)
        
        tk.Button(row1, text="⚙️ Settings", command=self.open_settings,
                 font=('Arial', 10), bg='#4CAF50', fg='white', width=15).pack(side=tk.LEFT, padx=2)
        
        tk.Button(row1, text="📹 Start Camera", command=self.toggle_camera,
                 font=('Arial', 10), bg='#2196F3', fg='white', width=15).pack(side=tk.LEFT, padx=2)
        
        # Row 2
        row2 = tk.Frame(frame, bg='#1e1e1e')
        row2.pack(fill=tk.X, pady=2)
        
        self.ready_button = tk.Button(row2, text="✅ Ready Up", command=self.toggle_ready,
                                     font=('Arial', 10), bg='#FF9800', fg='white', width=15)
        self.ready_button.pack(side=tk.LEFT, padx=2)
        
        tk.Button(row2, text="🔄 Reconnect", command=self.reconnect_controller,
                 font=('Arial', 10), bg='#9C27B0', fg='white', width=15).pack(side=tk.LEFT, padx=2)
        
        # Row 3
        row3 = tk.Frame(frame, bg='#1e1e1e')
        row3.pack(fill=tk.X, pady=2)
        
        tk.Button(row3, text="🛑 EMERGENCY STOP", command=self.emergency_stop,
                 font=('Arial', 10, 'bold'), bg='#f44336', fg='white', width=32).pack()
    
    def create_instructions_frame(self, parent):
        """Quick instructions"""
        frame = tk.LabelFrame(parent, text="ℹ️ Quick Guide", 
                             font=('Arial', 12, 'bold'), bg='#2d2d2d', fg='#00ff00')
        frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        instructions = """🎮 CONTROLS:
• Left Stick: Move robot
• Right Stick: Rotate
• RT: Boost speed
• LT: Slow speed
• A / RB: Fire weapon
• B: Emergency stop
• D-Pad: Control servos
• START: Quit
• BACK: Reconnect

⚙️ SETTINGS:
• Configure IPs and ports
• Adjust controller sensitivity
• Set team information

📹 CAMERA:
• Start/stop video feed
• Auto-connects to robot stream

✅ READY UP:
• Click when ready to play
• Wait for game to start"""
        
        tk.Label(frame, text=instructions, font=('Arial', 8), 
                bg='#2d2d2d', fg='white', justify=tk.LEFT).pack(padx=10, pady=10, anchor='nw')
    
    def open_settings(self):
        """Open settings dialog"""
        SettingsDialog(self.root, self.config, self.on_settings_saved)
    
    def on_settings_saved(self):
        """Called when settings are saved"""
        self.robot_addr = (
            self.config.get('robot_ip'),
            self.config.get('robot_port')
        )
        messagebox.showinfo("Settings", "Settings saved! Reconnect to apply changes.")
    
    def toggle_camera(self):
        """Start/stop camera feed"""
        if not self.video_active:
            self.start_video()
        else:
            self.stop_video()
    
    def start_video(self):
        """Start video stream"""
        if self.video_active:
            return
        
        port = self.config.get('video_port')
        cmd = GST_RECEIVER_CMD_TEMPLATE.format(port=port)
        
        try:
            self.gst_proc = subprocess.Popen(cmd, shell=True)
            self.video_active = True
            print(f"[Video] Started on port {port}")
        except Exception as e:
            print(f"[Video] Failed: {e}")
            messagebox.showerror("Video Error", f"Failed to start video: {e}")
    
    def stop_video(self):
        """Stop video stream"""
        if not self.video_active:
            return
        
        if self.gst_proc and self.gst_proc.poll() is None:
            self.gst_proc.terminate()
        
        self.video_active = False
        print("[Video] Stopped")
    
    def toggle_ready(self):
        """Toggle ready status"""
        # This would send ready status to robot, which forwards to GV
        is_ready = not self.robot_status['game_status']['is_ready']
        self.robot_status['game_status']['is_ready'] = is_ready
        print(f"[Ready] Set to: {is_ready}")
    
    def reconnect_controller(self):
        """Reconnect Xbox controller"""
        print("[Controller] Reconnecting...")
        self.controller.connect_controller()
    
    def emergency_stop(self):
        """Send emergency stop"""
        payload = {
            "vx": 0.0, "vy": 0.0, "omega": 0.0, "speed": 0.0,
            "estop": True, "fire": False,
            "servo_1": 0.0, "servo_2": 0.0,
            "last_input_time": time.time()
        }
        
        try:
            self.sock.sendto(json.dumps(payload).encode('utf-8'), self.robot_addr)
            print("[Emergency] Stop sent!")
        except Exception as e:
            print(f"[Emergency] Failed: {e}")
    
    def start_control_loop(self):
        """Start control and update loops"""
        threading.Thread(target=self.control_loop, daemon=True).start()
        self.update_gui()
    
    def control_loop(self):
        """Main control loop"""
        period = 1.0 / SEND_HZ
        
        while self.running:
            if self.controller.connected:
                result = self.controller.update()
                
                if result == "quit":
                    self.root.quit()
                    break
                elif result == "reconnect":
                    self.reconnect_controller()
                    time.sleep(0.5)
                    continue
                
                # Build payload
                payload = {
                    "vx": float(self.controller.vx),
                    "vy": float(self.controller.vy),
                    "omega": float(self.controller.omega),
                    "speed": float(self.controller.speed),
                    "estop": bool(self.controller.estop),
                    "fire": bool(self.controller.fire),
                    "servo_1": float(self.controller.servo_1),
                    "servo_2": float(self.controller.servo_2),
                    "last_input_time": float(self.controller.last_input_time)
                }
                
                try:
                    self.sock.sendto(json.dumps(payload).encode('utf-8'), self.robot_addr)
                    
                    # Try to receive response
                    self.sock.settimeout(0.001)
                    try:
                        data, addr = self.sock.recvfrom(4096)
                        response = json.loads(data.decode('utf-8'))
                        self.robot_status.update(response)
                    except (socket.timeout, json.JSONDecodeError):
                        pass
                    finally:
                        self.sock.settimeout(None)
                    
                    self.last_successful_send = time.time()
                
                except Exception as e:
                    print(f"[Network] Error: {e}")
            
            time.sleep(period)
    
    def update_gui(self):
        """Update GUI display"""
        if not self.running:
            return
        
        current_time = time.time()
        
        # Controller status
        if pygame.joystick.get_count() == 0:
            self.controller.connected = False
        
        self.controller_status.config(
            text=f"Controller: {'Connected' if self.controller.connected else 'Disconnected'}",
            fg='green' if self.controller.connected else 'red'
        )
        
        # Robot connection
        robot_connected = (current_time - self.last_successful_send) < 2.0
        self.robot_connection.config(
            text=f"Robot: {'Connected' if robot_connected else 'Disconnected'}",
            fg='green' if robot_connected else 'red'
        )
        
        # Camera status
        self.camera_status.config(
            text=f"Camera: {'Streaming' if self.video_active else 'Not Streaming'}",
            fg='green' if self.video_active else 'gray'
        )
        
        # Game status
        game_status = self.robot_status.get('game_status', {})
        if game_status.get('game_active'):
            self.game_status_label.config(text="Status: GAME ACTIVE", fg='lime')
        else:
            self.game_status_label.config(text="Status: Waiting for Game", fg='yellow')
        
        self.ready_label.config(
            text=f"Ready: {'Yes' if game_status.get('is_ready') else 'No'}",
            fg='lime' if game_status.get('is_ready') else 'white'
        )
        
        # Robot hit status
        ir_status = self.robot_status.get('ir_status', {})
        if ir_status.get('is_hit'):
            self.hit_status_label.config(text="Robot: DISABLED", fg='red')
            self.hit_info_label.config(text=f"Hit by Team {ir_status.get('hit_by_team', 0)}")
            self.respawn_label.config(text=f"Respawn: {ir_status.get('time_remaining', 0):.1f}s")
        else:
            self.hit_status_label.config(text="Robot: Active", fg='lime')
            self.hit_info_label.config(text="")
            self.respawn_label.config(text="")
        
        # Stats
        self.points_label.config(text=f"Points: {game_status.get('points', 0)}")
        
        kills = game_status.get('kills', 0)
        deaths = game_status.get('deaths', 0)
        kd_ratio = kills / deaths if deaths > 0 else kills
        self.kd_label.config(text=f"K/D: {kills}/{deaths} ({kd_ratio:.2f})")
        
        self.hits_label.config(text=f"Hits Taken: {ir_status.get('total_hits', 0)}")
        
        # Controller values
        if self.controller.connected:
            self.vx_label.config(text=f"Forward/Back: {self.controller.vx:+.2f}")
            self.vy_label.config(text=f"Strafe L/R: {self.controller.vy:+.2f}")
            self.omega_label.config(text=f"Rotate: {self.controller.omega:+.2f}")
            self.speed_label.config(text=f"Speed: {self.controller.speed:.2f}")
            self.servo_labels[0].config(text=f"Servo 1: {self.controller.servo_1:+.2f}")
            self.servo_labels[1].config(text=f"Servo 2: {self.controller.servo_2:+.2f}")
            
            if self.controller.fire:
                self.fire_label.config(text="🔫 Weapon: FIRING!", fg='red')
            else:
                self.fire_label.config(text="🔫 Weapon: Ready", fg='white')
            
            if self.controller.estop:
                self.estop_label.config(text="Emergency Stop: ACTIVE", fg='red')
            else:
                self.estop_label.config(text="Emergency Stop: OFF", fg='white')
        
        self.root.after(50, self.update_gui)
    
    def on_closing(self):
        """Clean up on close"""
        self.running = False
        self.stop_video()
        self.sock.close()
        pygame.quit()
        self.root.destroy()
    
    def run(self):
        """Start GUI main loop"""
        self.root.mainloop()


class SettingsDialog:
    """Settings dialog window"""
    
    def __init__(self, parent, config: Config, callback):
        self.config = config
        self.callback = callback
        
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("⚙️ Settings")
        self.dialog.geometry("500x600")
        self.dialog.configure(bg='#2d2d2d')
        self.dialog.transient(parent)
        self.dialog.grab_set()
        
        self.create_widgets()
    
    def create_widgets(self):
        """Create settings widgets"""
        main_frame = tk.Frame(self.dialog, bg='#2d2d2d')
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        tk.Label(main_frame, text="⚙️ CONFIGURATION", font=('Arial', 16, 'bold'),
                bg='#2d2d2d', fg='#00ff00').pack(pady=(0, 20))
        
        # Team settings
        self.add_section(main_frame, "👥 Team Information")
        self.team_id_var = self.add_entry(main_frame, "Team ID:", str(self.config.get('team_id')))
        self.team_name_var = self.add_entry(main_frame, "Team Name:", self.config.get('team_name'))
        self.robot_name_var = self.add_entry(main_frame, "Robot Name:", self.config.get('robot_name'))
        
        # Network settings
        self.add_section(main_frame, "🌐 Network")
        self.robot_ip_var = self.add_entry(main_frame, "Robot IP:", self.config.get('robot_ip'))
        self.robot_port_var = self.add_entry(main_frame, "Robot Port:", str(self.config.get('robot_port')))
        self.video_port_var = self.add_entry(main_frame, "Video Port:", str(self.config.get('video_port')))
        
        # Controller settings
        self.add_section(main_frame, "🎮 Controller")
        self.deadzone_var = self.add_entry(main_frame, "Deadzone:", str(self.config.get('controller', 'deadzone')))
        self.base_speed_var = self.add_entry(main_frame, "Base Speed:", str(self.config.get('controller', 'base_speed')))
        self.boost_speed_var = self.add_entry(main_frame, "Boost Speed:", str(self.config.get('controller', 'boost_speed')))
        self.slow_speed_var = self.add_entry(main_frame, "Slow Speed:", str(self.config.get('controller', 'slow_speed')))
        
        # Buttons
        button_frame = tk.Frame(main_frame, bg='#2d2d2d')
        button_frame.pack(pady=20)
        
        tk.Button(button_frame, text="💾 Save", command=self.save_settings,
                 font=('Arial', 11), bg='#4CAF50', fg='white', width=12).pack(side=tk.LEFT, padx=5)
        
        tk.Button(button_frame, text="❌ Cancel", command=self.dialog.destroy,
                 font=('Arial', 11), bg='#f44336', fg='white', width=12).pack(side=tk.LEFT, padx=5)
    
    def add_section(self, parent, title):
        """Add section header"""
        tk.Label(parent, text=title, font=('Arial', 12, 'bold'),
                bg='#2d2d2d', fg='#00ff00').pack(anchor='w', pady=(10, 5))
    
    def add_entry(self, parent, label, default):
        """Add labeled entry field"""
        frame = tk.Frame(parent, bg='#2d2d2d')
        frame.pack(fill=tk.X, pady=2)
        
        tk.Label(frame, text=label, font=('Arial', 10),
                bg='#2d2d2d', fg='white', width=15, anchor='w').pack(side=tk.LEFT)
        
        var = tk.StringVar(value=default)
        tk.Entry(frame, textvariable=var, font=('Arial', 10), width=30).pack(side=tk.LEFT, padx=5)
        
        return var
    
    def save_settings(self):
        """Save settings"""
        try:
            # Team settings
            self.config.set(int(self.team_id_var.get()), 'team_id')
            self.config.set(self.team_name_var.get(), 'team_name')
            self.config.set(self.robot_name_var.get(), 'robot_name')
            
            # Network settings
            self.config.set(self.robot_ip_var.get(), 'robot_ip')
            self.config.set(int(self.robot_port_var.get()), 'robot_port')
            self.config.set(int(self.video_port_var.get()), 'video_port')
            
            # Controller settings
            self.config.set(float(self.deadzone_var.get()), 'controller', 'deadzone')
            self.config.set(float(self.base_speed_var.get()), 'controller', 'base_speed')
            self.config.set(float(self.boost_speed_var.get()), 'controller', 'boost_speed')
            self.config.set(float(self.slow_speed_var.get()), 'controller', 'slow_speed')
            
            # Save to file
            if self.config.save_config():
                self.callback()
                self.dialog.destroy()
            else:
                messagebox.showerror("Error", "Failed to save configuration")
        
        except ValueError as e:
            messagebox.showerror("Invalid Input", f"Please check your inputs: {e}")


def main():
    """Main entry point"""
    print("=" * 60)
    print("🎯 LASER TAG ROBOT CONTROL - LAPTOP INTERFACE")
    print("=" * 60)
    print()
    
    try:
        app = RobotControlGUI()
        app.run()
    
    except KeyboardInterrupt:
        print("\n[Shutdown] Keyboard interrupt")
    
    except Exception as e:
        print(f"\n[Error] {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
