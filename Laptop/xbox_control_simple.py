# xbox_control_simple.py
# Windows Xbox controller client for mecanum_server.py with GUI (no OpenCV dependency)
# pip install pygame pillow

import json
import socket
import subprocess
import sys
import time
import threading
import tkinter as tk
from tkinter import ttk, messagebox
import pygame
from PIL import Image, ImageTk

# ============ USER CONFIG ============
PI_IP = "192.168.1.94"    # <-- set to your Pi's IP
PI_PORT = 5005

AUTO_LAUNCH_GSTREAMER = True
GST_RECEIVER_CMD = (
    'gst-launch-1.0 -v udpsrc port=5600 caps='
    '"application/x-rtp,media=video,encoding-name=H264,payload=96,clock-rate=90000,packetization-mode=1" '
    '! rtpjitterbuffer latency=50 ! rtph264depay ! h264parse ! d3d11h264dec ! autovideosink sync=false'
)

BASE_SPEED = 0.6    # default max motor percentage
BOOST_SPEED = 1.0   # when RT held
SEND_HZ = 30        # UDP send rate
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
        
        self.connect_controller()
    
    def connect_controller(self):
        """Try to connect to an Xbox controller"""
        try:
            pygame.joystick.quit()
            pygame.joystick.init()
            
            if pygame.joystick.get_count() == 0:
                print("No controllers found")
                self.connected = False
                return False
            
            self.joystick = pygame.joystick.Joystick(0)
            self.joystick.init()
            self.connected = True
            print(f"Connected to: {self.joystick.get_name()}")
            return True
        except Exception as e:
            print(f"Failed to connect controller: {e}")
            self.connected = False
            return False
    
    def update(self):
        """Update controller state"""
        if not self.connected:
            return
        
        try:
            pygame.event.pump()
            
            # Left stick for movement (vx, vy)
            left_x = self.joystick.get_axis(0)  # Left stick X
            left_y = -self.joystick.get_axis(1)  # Left stick Y (inverted)
            
            # Right stick X for rotation
            right_x = self.joystick.get_axis(2)  # Right stick X
            
            # Triggers for speed control
            left_trigger = self.joystick.get_axis(4)   # LT (-1 to 1)
            right_trigger = self.joystick.get_axis(5)  # RT (-1 to 1)
            
            # Convert triggers from -1..1 to 0..1
            left_trigger = (left_trigger + 1) / 2
            right_trigger = (right_trigger + 1) / 2
            
            # Buttons
            a_button = self.joystick.get_button(0)  # A button for estop
            back_button = self.joystick.get_button(6)  # Back button for reconnect
            
            # Apply deadzone
            def apply_deadzone(value, deadzone=0.15):
                return value if abs(value) > deadzone else 0.0
            
            self.vx = apply_deadzone(left_y)
            self.vy = apply_deadzone(left_x)
            self.omega = apply_deadzone(right_x)
            
            # Speed control: RT for boost, LT for slow
            if right_trigger > 0.1:
                self.speed = BASE_SPEED + (BOOST_SPEED - BASE_SPEED) * right_trigger
            elif left_trigger > 0.1:
                self.speed = BASE_SPEED * (1 - 0.7 * left_trigger)  # Slow down to 30%
            else:
                self.speed = BASE_SPEED
            
            # Emergency stop
            self.estop = bool(a_button)
            
            # Update last input time if there's any significant input
            if (abs(self.vx) > 0.05 or abs(self.vy) > 0.05 or abs(self.omega) > 0.05 or 
                self.estop or right_trigger > 0.1 or left_trigger > 0.1):
                self.last_input_time = time.time()
            
            # Handle back button for reconnect
            if back_button:
                return "reconnect"
                
        except Exception as e:
            print(f"Controller error: {e}")
            self.connected = False
        
        return None

class RobotControlGUI:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Robot Control - Xbox Controller")
        self.root.geometry("800x600")
        self.root.configure(bg='#2b2b2b')
        
        # Network setup
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.addr = (PI_IP, PI_PORT)
        
        # Controller
        self.controller = XboxController()
        
        # Video stream process
        self.gst_proc = None
        
        # Threading control
        self.running = True
        
        # Connection status
        self.last_successful_send = 0
        
        self.setup_gui()
        self.start_video_stream()
        self.start_control_loop()
        
        # Handle window close
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
    
    def setup_gui(self):
        """Create the GUI layout"""
        # Main frame
        main_frame = tk.Frame(self.root, bg='#2b2b2b')
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Title
        title_label = tk.Label(main_frame, text="Xbox Controller Robot Interface", 
                              font=('Arial', 18, 'bold'), bg='#2b2b2b', fg='white')
        title_label.pack(pady=10)
        
        # Video info (since we can't embed video without OpenCV)
        video_frame = tk.LabelFrame(main_frame, text="Video Stream", font=('Arial', 12, 'bold'),
                                   bg='#3b3b3b', fg='white')
        video_frame.pack(fill=tk.X, pady=10)
        
        video_info = tk.Label(video_frame, 
                             text="📹 Video stream opens in separate GStreamer window\n" +
                                  "If no video window appears, check GStreamer installation",
                             font=('Arial', 11), bg='#3b3b3b', fg='yellow', justify=tk.CENTER)
        video_info.pack(pady=10)
        
        # Create two columns
        content_frame = tk.Frame(main_frame, bg='#2b2b2b')
        content_frame.pack(fill=tk.BOTH, expand=True)
        
        # Left column - Status
        left_frame = tk.Frame(content_frame, bg='#2b2b2b')
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))
        
        # Connection status
        status_frame = tk.LabelFrame(left_frame, text="Connection Status", font=('Arial', 12, 'bold'),
                                    bg='#3b3b3b', fg='white')
        status_frame.pack(fill=tk.X, pady=5)
        
        self.controller_status = tk.Label(status_frame, 
                                         text="Controller: " + ("Connected" if self.controller.connected else "Disconnected"),
                                         font=('Arial', 11), bg='#3b3b3b', 
                                         fg='green' if self.controller.connected else 'red')
        self.controller_status.pack(pady=5)
        
        self.robot_status = tk.Label(status_frame, text="Robot: Connecting...", 
                                    font=('Arial', 11), bg='#3b3b3b', fg='yellow')
        self.robot_status.pack(pady=5)
        
        # Current values
        values_frame = tk.LabelFrame(left_frame, text="Current Values", font=('Arial', 12, 'bold'),
                                    bg='#3b3b3b', fg='white')
        values_frame.pack(fill=tk.X, pady=5)
        
        self.vx_label = tk.Label(values_frame, text="Forward/Back: 0.00", font=('Arial', 10),
                                bg='#3b3b3b', fg='white')
        self.vx_label.pack(pady=2)
        
        self.vy_label = tk.Label(values_frame, text="Strafe L/R: 0.00", font=('Arial', 10),
                                bg='#3b3b3b', fg='white')
        self.vy_label.pack(pady=2)
        
        self.omega_label = tk.Label(values_frame, text="Rotate L/R: 0.00", font=('Arial', 10),
                                   bg='#3b3b3b', fg='white')
        self.omega_label.pack(pady=2)
        
        self.speed_label = tk.Label(values_frame, text="Speed: 0.60", font=('Arial', 10),
                                   bg='#3b3b3b', fg='white')
        self.speed_label.pack(pady=2)
        
        # Right column - Controls
        right_frame = tk.Frame(content_frame, bg='#2b2b2b')
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        
        # Controls instruction
        controls_frame = tk.LabelFrame(right_frame, text="Xbox Controller Mapping", font=('Arial', 12, 'bold'),
                                      bg='#3b3b3b', fg='white')
        controls_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        controls_text = """🎮 MOVEMENT:
Left Stick ↕️ : Forward/Backward
Left Stick ↔️ : Strafe Left/Right
Right Stick ↔️ : Rotate Left/Right

⚡ SPEED CONTROL:
Right Trigger (RT): Boost Speed
Left Trigger (LT): Slow Mode

🛑 SAFETY:
A Button: Emergency Stop
Back Button: Reconnect Controller

📊 INDICATORS:
• Green = Connected & Working
• Yellow = Connecting/Searching
• Red = Disconnected/Error

💡 TIPS:
• Hold RT for maximum speed
• Hold LT for precise movements  
• A button stops robot instantly
• Controller auto-reconnects"""
        
        controls_label = tk.Label(controls_frame, text=controls_text, font=('Arial', 9),
                                 bg='#3b3b3b', fg='white', justify=tk.LEFT)
        controls_label.pack(padx=10, pady=10, anchor='nw')
        
        # Control buttons
        button_frame = tk.Frame(left_frame, bg='#2b2b2b')
        button_frame.pack(fill=tk.X, pady=10)
        
        self.reconnect_btn = tk.Button(button_frame, text="🔄 Reconnect Controller", 
                                      command=self.reconnect_controller,
                                      font=('Arial', 10), bg='#4CAF50', fg='white',
                                      relief=tk.RAISED, bd=2)
        self.reconnect_btn.pack(fill=tk.X, pady=2)
        
        self.estop_btn = tk.Button(button_frame, text="🛑 EMERGENCY STOP", 
                                  command=self.emergency_stop,
                                  font=('Arial', 10, 'bold'), bg='#f44336', fg='white',
                                  relief=tk.RAISED, bd=2)
        self.estop_btn.pack(fill=tk.X, pady=2)
    
    def start_video_stream(self):
        """Start GStreamer video receiver in separate window"""
        if AUTO_LAUNCH_GSTREAMER:
            try:
                self.gst_proc = subprocess.Popen(GST_RECEIVER_CMD, shell=True)
                print("[Video] GStreamer receiver started in separate window.")
            except Exception as e:
                print(f"[Video] Failed to start video stream: {e}")
    
    def reconnect_controller(self):
        """Try to reconnect the controller"""
        self.controller.connect_controller()
        self.controller_status.config(
            text="Controller: " + ("Connected" if self.controller.connected else "Disconnected"),
            fg='green' if self.controller.connected else 'red'
        )
    
    def emergency_stop(self):
        """Send emergency stop command"""
        payload = {
            "vx": 0.0, "vy": 0.0, "omega": 0.0,
            "speed": 0.0, "estop": True,
            "last_input_time": time.time()
        }
        try:
            self.sock.sendto(json.dumps(payload).encode("utf-8"), self.addr)
            print("[Emergency] Stop command sent!")
        except Exception as e:
            print(f"[Emergency] Failed to send stop: {e}")
    
    def start_control_loop(self):
        """Start the control loop"""
        threading.Thread(target=self.control_loop, daemon=True).start()
        
        # Start GUI update loop
        self.update_gui()
    
    def control_loop(self):
        """Main control loop - sends UDP commands"""
        period = 1.0 / SEND_HZ
        
        while self.running:
            if self.controller.connected:
                result = self.controller.update()
                
                # Handle reconnect request from controller
                if result == "reconnect":
                    self.reconnect_controller()
                    time.sleep(0.5)  # Prevent spam
                    continue
                
                # Prepare payload
                payload = {
                    "vx": self.controller.vx,
                    "vy": self.controller.vy,
                    "omega": self.controller.omega,
                    "speed": self.controller.speed,
                    "estop": self.controller.estop,
                    "last_input_time": self.controller.last_input_time
                }
                
                # Send UDP command
                try:
                    self.sock.sendto(json.dumps(payload).encode("utf-8"), self.addr)
                    self.last_successful_send = time.time()
                    
                except Exception as e:
                    print(f"UDP send error: {e}")
            
            time.sleep(period)
    
    def update_gui(self):
        """Update GUI values"""
        current_time = time.time()
        
        # Update controller status
        if pygame.joystick.get_count() == 0 and self.controller.connected:
            self.controller.connected = False
        
        self.controller_status.config(
            text="Controller: " + ("Connected" if self.controller.connected else "Disconnected"),
            fg='green' if self.controller.connected else 'red'
        )
        
        # Update robot status based on last successful send
        if current_time - self.last_successful_send < 2.0:
            self.robot_status.config(text="Robot: Connected", fg='green')
        elif current_time - self.last_successful_send < 5.0:
            self.robot_status.config(text="Robot: Timeout", fg='yellow')
        else:
            self.robot_status.config(text="Robot: Disconnected", fg='red')
        
        # Update values if controller connected
        if self.controller.connected:
            self.vx_label.config(text=f"Forward/Back: {self.controller.vx:+.2f}")
            self.vy_label.config(text=f"Strafe L/R: {self.controller.vy:+.2f}")
            self.omega_label.config(text=f"Rotate L/R: {self.controller.omega:+.2f}")
            self.speed_label.config(text=f"Speed: {self.controller.speed:.2f}")
        
        # Schedule next update
        self.root.after(50, self.update_gui)  # 20 FPS GUI updates
    
    def on_closing(self):
        """Handle window closing"""
        self.running = False
        
        # Clean up video
        if self.gst_proc and self.gst_proc.poll() is None:
            self.gst_proc.terminate()
            try:
                self.gst_proc.wait(timeout=2)
            except:
                pass
        
        # Clean up socket
        self.sock.close()
        
        # Close pygame
        pygame.quit()
        
        self.root.destroy()
    
    def run(self):
        """Start the GUI"""
        self.root.mainloop()

def main():
    print("=" * 50)
    print("Xbox Controller Robot Interface")
    print("=" * 50)
    print("🎮 Connect your Xbox controller")
    print("📡 Make sure robot is powered on")
    print("🚀 Starting GUI...")
    print()
    
    try:
        app = RobotControlGUI()
        app.run()
    except KeyboardInterrupt:
        print("\n[Shutdown] User interrupted")
    except Exception as e:
        print(f"[Error] Application error: {e}")
        messagebox.showerror("Error", f"Application error: {e}")

if __name__ == "__main__":
    main()
