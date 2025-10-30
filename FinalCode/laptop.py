import json
import socket
import subprocess
import sys
import time
import threading
import tkinter as tk
from tkinter import ttk, messagebox
import pygame
import os

# ============ USER CONFIG ============
PI_IP = "192.168.50.147"    # Your Pi's IP
PI_PORT = 5005

AUTO_LAUNCH_GSTREAMER = True
GST_RECEIVER_CMD = (
    'gst-launch-1.0 -v udpsrc port=5600 caps='
    '"application/x-rtp,media=video,encoding-name=H264,payload=96,clock-rate=90000,packetization-mode=1" '
    '! rtpjitterbuffer latency=50 ! rtph264depay ! h264parse ! d3d11h264dec ! autovideosink sync=false'
)

BASE_SPEED = 0.6
BOOST_SPEED = 1.0
SLOW_SPEED = 0.3
SEND_HZ = 30
DEADZONE = 0.12

TEAM_CONFIG_FILE = "team_config.json"
# =====================================

class XboxController:
    def __init__(self):
        pygame.init()
        pygame.joystick.init()
        
        self.joystick = None
        self.connected = False
        self.last_input_time = time.time()
        
        # Controller state
        self.vx = 0.0
        self.vy = 0.0
        self.omega = 0.0
        self.speed = BASE_SPEED
        self.estop = False
        self.fire = False
        self.fire_last_state = False  # For edge detection
        
        self.connect_controller()
    
    def connect_controller(self):
        """Try to connect to an Xbox controller"""
        try:
            # Reinitialize pygame joystick system
            pygame.joystick.quit()
            pygame.joystick.init()
            
            if pygame.joystick.get_count() == 0:
                print("No controllers found")
                self.connected = False
                return False
            
            # Use first available controller
            self.joystick = pygame.joystick.Joystick(0)
            self.joystick.init()
            self.connected = True
            print(f"Connected to: {self.joystick.get_name()}")
            return True
        except Exception as e:
            print(f"Failed to connect controller: {e}")
            self.connected = False
            return False
    
    def apply_deadzone(self, value, deadzone=DEADZONE):
        return value if abs(value) > deadzone else 0.0
    
    def clamp(self, x, lo, hi):
        return max(lo, min(hi, x))
    
    def update(self):
        """Update controller state"""
        if not self.connected:
            return None
        
        try:
            # IMPORTANT: Process pygame events
            pygame.event.pump()
            
            # Check if joystick is still valid
            if not self.joystick.get_init():
                print("Controller disconnected, attempting reconnect...")
                self.connected = False
                return "reconnect"
            
            # Read axes
            lx = self.apply_deadzone(self.joystick.get_axis(0))    # Left stick X
            ly = self.apply_deadzone(self.joystick.get_axis(1))    # Left stick Y
            rx = self.apply_deadzone(self.joystick.get_axis(2))    # Right stick X
            
            # Read triggers with error handling
            try:
                left_trigger = (self.joystick.get_axis(4) + 1) / 2   # LT (0 to 1)
                right_trigger = (self.joystick.get_axis(5) + 1) / 2  # RT (0 to 1)
            except:
                left_trigger = 0.0
                right_trigger = 0.0
            
            # Convert to robot movement
            self.vx = self.clamp(-ly, -1, 1)     # Forward/back (invert Y)
            self.vy = self.clamp(lx, -1, 1)      # Strafe left/right
            self.omega = self.clamp(-rx, -1, 1)  # Rotation (invert for intuitive control)
            
            # Speed control
            boosting_lb = bool(self.joystick.get_button(4))  # LB button
            
            if right_trigger > 0.1:  # RT pressed
                self.speed = BASE_SPEED + (BOOST_SPEED - BASE_SPEED) * right_trigger
            elif boosting_lb:  # LB button
                self.speed = BOOST_SPEED
            elif left_trigger > 0.1:  # LT pressed
                self.speed = BASE_SPEED - (BASE_SPEED - SLOW_SPEED) * left_trigger
            else:
                self.speed = BASE_SPEED
            
            # Buttons
            self.estop = bool(self.joystick.get_button(1))  # B button
            
            # Fire button with edge detection (only fire on press, not hold)
            fire_current = bool(self.joystick.get_button(0)) or bool(self.joystick.get_button(5))  # A or RB
            self.fire = fire_current and not self.fire_last_state  # Edge detection
            self.fire_last_state = fire_current
            
            # Update input time
            if (abs(self.vx) > 0.05 or abs(self.vy) > 0.05 or abs(self.omega) > 0.05 or 
                self.estop or boosting_lb or right_trigger > 0.1 or left_trigger > 0.1 or self.fire):
                self.last_input_time = time.time()
            
            # Handle special buttons
            if self.joystick.get_button(7):  # START button
                return "quit"
            
            if self.joystick.get_button(6):  # Back button
                return "reconnect"
                
        except Exception as e:
            print(f"Controller error: {e}")
            self.connected = False
            return "reconnect"
        
        return None

class TeamConfig:
    def __init__(self):
        self.team_id = 1
        self.load_config()
    
    def load_config(self):
        """Load team configuration"""
        try:
            if os.path.exists(TEAM_CONFIG_FILE):
                with open(TEAM_CONFIG_FILE, 'r') as f:
                    config = json.load(f)
                    self.team_id = config.get("team_id", 1)
                    print(f"Loaded team ID: {self.team_id}")
        except Exception as e:
            print(f"Failed to load config: {e}")
            self.team_id = 1
    
    def save_config(self):
        """Save team configuration"""
        try:
            config = {"team_id": self.team_id}
            with open(TEAM_CONFIG_FILE, 'w') as f:
                json.dump(config, f)
            print(f"Saved team ID: {self.team_id}")
        except Exception as e:
            print(f"Failed to save config: {e}")

class RobotControlGUI:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("🎯 Laser Tag Robot Control 🎯")
        self.root.geometry("900x700")
        self.root.configure(bg='#2b2b2b')
        
        # Network setup
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.addr = (PI_IP, PI_PORT)
        
        # Controller and config
        self.controller = XboxController()
        self.team_config = TeamConfig()
        
        # Robot status
        self.robot_status = {
            "team_id": self.team_config.team_id,
            "is_hit": False,
            "hit_by_team": 0,
            "time_remaining": 0,
            "is_self_hit": False  # Add this for self-hit detection
        }
        
        # Video and threading
        self.gst_proc = None
        self.running = True
        self.last_successful_send = 0
        
        self.setup_gui()
        self.start_video_stream()
        self.start_control_loop()
        
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
    
    def setup_gui(self):
        """Create GUI"""
        main_frame = tk.Frame(self.root, bg='#2b2b2b')
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        title_label = tk.Label(main_frame, text="🎯 Laser Tag Robot Control 🎯", 
                              font=('Arial', 20, 'bold'), bg='#2b2b2b', fg='white')
        title_label.pack(pady=10)
        
        content_frame = tk.Frame(main_frame, bg='#2b2b2b')
        content_frame.pack(fill=tk.BOTH, expand=True)
        
        left_frame = tk.Frame(content_frame, bg='#2b2b2b')
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))
        
        # Team Configuration
        team_frame = tk.LabelFrame(left_frame, text="🏆 Team Configuration", 
                                  font=('Arial', 12, 'bold'), bg='#3b3b3b', fg='white')
        team_frame.pack(fill=tk.X, pady=5)
        
        team_input_frame = tk.Frame(team_frame, bg='#3b3b3b')
        team_input_frame.pack(pady=10)
        
        tk.Label(team_input_frame, text="Team ID (1-255):", font=('Arial', 11), 
                bg='#3b3b3b', fg='white').pack(side=tk.LEFT, padx=5)
        
        self.team_entry = tk.Entry(team_input_frame, font=('Arial', 11), width=10)
        self.team_entry.pack(side=tk.LEFT, padx=5)
        self.team_entry.insert(0, str(self.team_config.team_id))
        
        self.update_team_btn = tk.Button(team_input_frame, text="Update", 
                                        command=self.update_team_id,
                                        font=('Arial', 10), bg='#4CAF50', fg='white')
        self.update_team_btn.pack(side=tk.LEFT, padx=5)
        
        self.current_team_label = tk.Label(team_frame, 
                                          text=f"Current Team: {self.team_config.team_id}", 
                                          font=('Arial', 12, 'bold'), bg='#3b3b3b', fg='lime')
        self.current_team_label.pack(pady=5)
        
        # Status frames
        status_frame = tk.LabelFrame(left_frame, text="🎯 Laser Tag Status", 
                                    font=('Arial', 12, 'bold'), bg='#3b3b3b', fg='white')
        status_frame.pack(fill=tk.X, pady=5)
        
        self.hit_status_label = tk.Label(status_frame, text="Status: Active", 
                                        font=('Arial', 12, 'bold'), bg='#3b3b3b', fg='lime')
        self.hit_status_label.pack(pady=5)
        
        self.hit_by_label = tk.Label(status_frame, text="", 
                                    font=('Arial', 11), bg='#3b3b3b', fg='white')
        self.hit_by_label.pack(pady=2)
        
        self.respawn_timer_label = tk.Label(status_frame, text="", 
                                           font=('Arial', 11), bg='#3b3b3b', fg='yellow')
        self.respawn_timer_label.pack(pady=2)
        
        # Add self-hit warning label
        self.self_hit_label = tk.Label(status_frame, text="", 
                                      font=('Arial', 11, 'bold'), bg='#3b3b3b', fg='orange')
        self.self_hit_label.pack(pady=2)
        
        # Connection status
        conn_frame = tk.LabelFrame(left_frame, text="📡 Connection", 
                                  font=('Arial', 12, 'bold'), bg='#3b3b3b', fg='white')
        conn_frame.pack(fill=tk.X, pady=5)
        
        self.controller_status = tk.Label(conn_frame, text="Controller: Disconnected",
                                         font=('Arial', 11), bg='#3b3b3b', fg='red')
        self.controller_status.pack(pady=5)
        
        self.robot_connection_status = tk.Label(conn_frame, text="Robot: Connecting...", 
                                               font=('Arial', 11), bg='#3b3b3b', fg='yellow')
        self.robot_connection_status.pack(pady=5)
        
        # Values
        values_frame = tk.LabelFrame(left_frame, text="📊 Current Values", 
                                    font=('Arial', 12, 'bold'), bg='#3b3b3b', fg='white')
        values_frame.pack(fill=tk.X, pady=5)
        
        self.vx_label = tk.Label(values_frame, text="Forward/Back: 0.00", 
                                font=('Arial', 10), bg='#3b3b3b', fg='white')
        self.vx_label.pack(pady=2)
        
        self.vy_label = tk.Label(values_frame, text="Strafe L/R: 0.00", 
                                font=('Arial', 10), bg='#3b3b3b', fg='white')
        self.vy_label.pack(pady=2)
        
        self.omega_label = tk.Label(values_frame, text="Rotate L/R: 0.00", 
                                   font=('Arial', 10), bg='#3b3b3b', fg='white')
        self.omega_label.pack(pady=2)
        
        self.speed_label = tk.Label(values_frame, text="Speed: 0.60", 
                                   font=('Arial', 10), bg='#3b3b3b', fg='white')
        self.speed_label.pack(pady=2)
        
        self.fire_label = tk.Label(values_frame, text="🔫 Fire: OFF", 
                                  font=('Arial', 10, 'bold'), bg='#3b3b3b', fg='white')
        self.fire_label.pack(pady=2)
        
        # Add test info
        test_frame = tk.LabelFrame(left_frame, text="🧪 Testing Info", 
                                  font=('Arial', 12, 'bold'), bg='#3b3b3b', fg='white')
        test_frame.pack(fill=tk.X, pady=5)
        
        test_info = tk.Label(test_frame, 
                           text="Self-hit detection enabled for testing!\nPoint IR at your own receivers and fire.",
                           font=('Arial', 9), bg='#3b3b3b', fg='cyan', justify=tk.CENTER)
        test_info.pack(pady=5)
        
        # Right column - Controls info
        right_frame = tk.Frame(content_frame, bg='#2b2b2b')
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        
        # Controls instruction
        controls_frame = tk.LabelFrame(right_frame, text="🎮 Xbox Controller Mapping", font=('Arial', 12, 'bold'),
                                      bg='#3b3b3b', fg='white')
        controls_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        controls_text = """🎮 MOVEMENT:
Left Stick ↕️ : Forward/Backward
Left Stick ↔️ : Strafe Left/Right
Right Stick ↔️ : Rotate Left/Right

⚡ SPEED CONTROL:
Right Trigger (RT): Boost Speed (Variable)
LB Button: Full Boost Speed
Left Trigger (LT): Slow Mode (Variable)

🔫 LASER TAG:
A Button: Fire Laser
RB Button: Fire Laser (Alternative)

🛑 SAFETY:
B Button: Emergency Stop
Back Button: Reconnect Controller
START Button: Quit Application

📊 STATUS INDICATORS:
• Green = Connected & Active
• Yellow = Connecting/Hit Recovery
• Red = Disconnected/Hit
• Orange = Self Hit (Testing)

🎯 LASER TAG RULES:
• Robot disabled for 10 seconds when hit
• Can't fire when hit
• Shows which team hit you
• Respawn timer displayed
• Self-hits detected for testing

💡 TIPS:
• Set your team ID before starting
• RT/LT triggers are variable speed
• A or RB to fire at enemies
• B button stops robot instantly
• Point IR at own receivers to test"""
        
        controls_label = tk.Label(controls_frame, text=controls_text, font=('Arial', 9),
                                 bg='#3b3b3b', fg='white', justify=tk.LEFT)
        controls_label.pack(padx=10, pady=10, anchor='nw')
        
        # Buttons
        button_frame = tk.Frame(left_frame, bg='#2b2b2b')
        button_frame.pack(fill=tk.X, pady=10)
        
        self.reconnect_btn = tk.Button(button_frame, text="🔄 Reconnect Controller", 
                                      command=self.reconnect_controller,
                                      font=('Arial', 10), bg='#4CAF50', fg='white')
        self.reconnect_btn.pack(fill=tk.X, pady=2)
        
        self.estop_btn = tk.Button(button_frame, text="🛑 EMERGENCY STOP", 
                                  command=self.emergency_stop,
                                  font=('Arial', 10, 'bold'), bg='#f44336', fg='white')
        self.estop_btn.pack(fill=tk.X, pady=2)
    
    def update_team_id(self):
        """Update team ID"""
        try:
            new_team_id = int(self.team_entry.get())
            if 1 <= new_team_id <= 255:
                self.team_config.team_id = new_team_id
                self.team_config.save_config()
                self.current_team_label.config(text=f"Current Team: {new_team_id}")
                print(f"Team ID updated to: {new_team_id}")
            else:
                messagebox.showerror("Invalid Team ID", "Team ID must be between 1 and 255")
        except ValueError:
            messagebox.showerror("Invalid Input", "Please enter a valid number")
    
    def start_video_stream(self):
        """Start video stream"""
        if AUTO_LAUNCH_GSTREAMER:
            try:
                self.gst_proc = subprocess.Popen(GST_RECEIVER_CMD, shell=True)
                print("[Video] GStreamer started")
            except Exception as e:
                print(f"[Video] Failed: {e}")
    
    def reconnect_controller(self):
        """Reconnect controller"""
        print("Attempting to reconnect controller...")
        self.controller.connect_controller()
    
    def emergency_stop(self):
        """Emergency stop"""
        payload = {
            "vx": 0.0, "vy": 0.0, "omega": 0.0, "speed": 0.0, 
            "estop": True, "fire": False, "team_id": self.team_config.team_id,
            "last_input_time": time.time()
        }
        try:
            self.sock.sendto(json.dumps(payload).encode("utf-8"), self.addr)
            print("[Emergency] Stop sent!")
        except Exception as e:
            print(f"[Emergency] Failed: {e}")
    
    def start_control_loop(self):
        """Start control and GUI loops"""
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
                
                # Send data to robot
                payload = {
                    "vx": float(self.controller.vx),
                    "vy": float(self.controller.vy),
                    "omega": float(self.controller.omega),
                    "speed": float(self.controller.speed),
                    "estop": bool(self.controller.estop),
                    "fire": bool(self.controller.fire),
                    "team_id": int(self.team_config.team_id),
                    "last_input_time": float(self.controller.last_input_time)
                }
                
                try:
                    self.sock.sendto(json.dumps(payload).encode("utf-8"), self.addr)
                    
                    # Try to receive response
                    self.sock.settimeout(0.001)
                    try:
                        data, addr = self.sock.recvfrom(1024)
                        response = json.loads(data.decode("utf-8"))
                        self.robot_status.update(response)
                        
                        # Debug print for self-hits
                        if response.get("is_self_hit", False):
                            print(f"[GUI] Self-hit detected in response: {response}")
                            
                    except (socket.timeout, json.JSONDecodeError):
                        pass
                    finally:
                        self.sock.settimeout(None)
                    
                    self.last_successful_send = time.time()
                except Exception as e:
                    print(f"UDP error: {e}")
            
            time.sleep(period)
    
    def update_gui(self):
        """Update GUI display - FIXED self-hit detection"""
        if not self.running:
            return
        
        current_time = time.time()
        
        # Update controller status
        if pygame.joystick.get_count() == 0:
            self.controller.connected = False
        
        self.controller_status.config(
            text="Controller: " + ("Connected" if self.controller.connected else "Disconnected"),
            fg='green' if self.controller.connected else 'red'
        )
        
        # Update robot connection
        if current_time - self.last_successful_send < 2.0:
            self.robot_connection_status.config(text="Robot: Connected", fg='green')
        else:
            self.robot_connection_status.config(text="Robot: Disconnected", fg='red')
        
        # Update laser tag status with PROPER self-hit detection
        if self.robot_status["is_hit"]:
            if self.robot_status.get("is_self_hit", False):
                # SELF HIT DETECTED!
                self.hit_status_label.config(text="Status: SELF HIT! 🤦‍♂️", fg='orange')
                self.hit_by_label.config(text=f"🔄 You hit yourself! Team: {self.robot_status['hit_by_team']}")
                self.self_hit_label.config(text="⚠️ OOPS! FRIENDLY FIRE! ⚠️", fg='orange')
                print(f"[GUI] Displaying self-hit: Team {self.robot_status['hit_by_team']}")
            else:
                # Regular enemy hit
                self.hit_status_label.config(text="Status: HIT! 💥", fg='red')
                self.hit_by_label.config(text=f"💀 Hit by Team: {self.robot_status['hit_by_team']}")
                self.self_hit_label.config(text="")
            
            self.respawn_timer_label.config(text=f"⏰ Respawn: {self.robot_status['time_remaining']:.1f}s")
        else:
            # Not hit - active status
            self.hit_status_label.config(text="Status: Active 🟢", fg='lime')
            self.hit_by_label.config(text="")
            self.respawn_timer_label.config(text="")
            self.self_hit_label.config(text="")
        
        # Update values
        if self.controller.connected:
            self.vx_label.config(text=f"Forward/Back: {self.controller.vx:+.2f}")
            self.vy_label.config(text=f"Strafe L/R: {self.controller.vy:+.2f}")
            self.omega_label.config(text=f"Rotate L/R: {self.controller.omega:+.2f}")
            self.speed_label.config(text=f"Speed: {self.controller.speed:.2f}")
            
            if self.controller.fire:
                self.fire_label.config(text="🔫 Fire: FIRING!", fg='red')
            else:
                self.fire_label.config(text="🔫 Fire: OFF", fg='white')
        
        self.root.after(50, self.update_gui)
    
    def on_closing(self):
        """Clean up on close"""
        self.running = False
        
        if self.gst_proc and self.gst_proc.poll() is None:
            self.gst_proc.terminate()
        
        self.sock.close()
        pygame.quit()
        self.root.destroy()
    
    def run(self):
        """Start GUI"""
        self.root.mainloop()

def main():
    print("🎯 LASER TAG ROBOT CONTROL 🎯")
    print("Connect Xbox controller and set team ID!")
    print("🧪 TESTING MODE: Self-hit detection enabled!")
    print("Point IR transmitter at your own receivers to test!")
    
    try:
        app = RobotControlGUI()
        app.run()
    except KeyboardInterrupt:
        print("\nShutdown")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()