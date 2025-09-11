# xbox_control.py
# Windows Xbox controller client for mecanum_server.py with GUI and camera stream
# pip install pygame opencv-python pillow

import json
import socket
import subprocess
import sys
import time
import threading
import tkinter as tk
from tkinter import ttk, messagebox
import pygame
import cv2
from PIL import Image, ImageTk

# ============ USER CONFIG ============
PI_IP = "192.168.1.94"    # <-- set to your Pi's IP
PI_PORT = 5005

AUTO_LAUNCH_GSTREAMER = True
GST_RECEIVER_CMD = (
    'gst-launch-1.0 -v udpsrc port=5600 caps='
    '"application/x-rtp,media=video,encoding-name=H264,payload=96,clock-rate=90000,packetization-mode=1" '
    '! rtpjitterbuffer latency=50 ! rtph264depay ! h264parse ! d3d11h264dec ! videoconvert ! appsink'
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
            if pygame.joystick.get_count() == 0:
                print("No controllers found")
                return False
            
            self.joystick = pygame.joystick.Joystick(0)
            self.joystick.init()
            self.connected = True
            print(f"Connected to: {self.joystick.get_name()}")
            return True
        except Exception as e:
            print(f"Failed to connect controller: {e}")
            return False
    
    def update(self):
        """Update controller state"""
        if not self.connected:
            return
        
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

class RobotControlGUI:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Robot Control - Xbox Controller")
        self.root.geometry("1000x700")
        self.root.configure(bg='#2b2b2b')
        
        # Network setup
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.addr = (PI_IP, PI_PORT)
        
        # Controller
        self.controller = XboxController()
        
        # Video stream
        self.video_cap = None
        self.gst_proc = None
        
        # Threading control
        self.running = True
        
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
        
        # Left side - Video feed
        video_frame = tk.Frame(main_frame, bg='#3b3b3b', relief=tk.RAISED, bd=2)
        video_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))
        
        video_label = tk.Label(video_frame, text="Camera Feed", font=('Arial', 14, 'bold'), 
                              bg='#3b3b3b', fg='white')
        video_label.pack(pady=5)
        
        self.video_canvas = tk.Canvas(video_frame, bg='black', width=640, height=360)
        self.video_canvas.pack(pady=5, padx=5)
        
        # Right side - Controls and status
        control_frame = tk.Frame(main_frame, bg='#3b3b3b', relief=tk.RAISED, bd=2, width=300)
        control_frame.pack(side=tk.RIGHT, fill=tk.Y)
        control_frame.pack_propagate(False)
        
        # Title
        title_label = tk.Label(control_frame, text="Xbox Controller", font=('Arial', 16, 'bold'),
                              bg='#3b3b3b', fg='white')
        title_label.pack(pady=10)
        
        # Connection status
        self.status_frame = tk.Frame(control_frame, bg='#3b3b3b')
        self.status_frame.pack(pady=5)
        
        self.controller_status = tk.Label(self.status_frame, text="Controller: Connected" if self.controller.connected else "Controller: Disconnected",
                                         font=('Arial', 10), bg='#3b3b3b', 
                                         fg='green' if self.controller.connected else 'red')
        self.controller_status.pack()
        
        self.robot_status = tk.Label(self.status_frame, text="Robot: Unknown", 
                                    font=('Arial', 10), bg='#3b3b3b', fg='yellow')
        self.robot_status.pack()
        
        # Controls instruction
        controls_frame = tk.LabelFrame(control_frame, text="Controls", font=('Arial', 12, 'bold'),
                                      bg='#3b3b3b', fg='white')
        controls_frame.pack(fill=tk.X, padx=10, pady=10)
        
        controls_text = """
Left Stick: Move robot
• Forward/Backward
• Left/Right strafe

Right Stick X: Rotate
• Left/Right turning

Triggers:
• RT: Boost speed
• LT: Slow mode

A Button: Emergency Stop

Back Button: Reconnect controller
        """
        
        controls_label = tk.Label(controls_frame, text=controls_text, font=('Arial', 9),
                                 bg='#3b3b3b', fg='white', justify=tk.LEFT)
        controls_label.pack(padx=5, pady=5)
        
        # Current values
        values_frame = tk.LabelFrame(control_frame, text="Current Values", font=('Arial', 12, 'bold'),
                                    bg='#3b3b3b', fg='white')
        values_frame.pack(fill=tk.X, padx=10, pady=10)
        
        self.vx_label = tk.Label(values_frame, text="Forward: 0.00", font=('Arial', 9),
                                bg='#3b3b3b', fg='white')
        self.vx_label.pack()
        
        self.vy_label = tk.Label(values_frame, text="Strafe: 0.00", font=('Arial', 9),
                                bg='#3b3b3b', fg='white')
        self.vy_label.pack()
        
        self.omega_label = tk.Label(values_frame, text="Rotate: 0.00", font=('Arial', 9),
                                   bg='#3b3b3b', fg='white')
        self.omega_label.pack()
        
        self.speed_label = tk.Label(values_frame, text="Speed: 0.60", font=('Arial', 9),
                                   bg='#3b3b3b', fg='white')
        self.speed_label.pack()
        
        # Reconnect button
        self.reconnect_btn = tk.Button(control_frame, text="Reconnect Controller", 
                                      command=self.reconnect_controller,
                                      font=('Arial', 10), bg='#4CAF50', fg='white')
        self.reconnect_btn.pack(pady=10)
    
    def start_video_stream(self):
        """Start GStreamer video receiver"""
        if AUTO_LAUNCH_GSTREAMER:
            try:
                self.gst_proc = subprocess.Popen(GST_RECEIVER_CMD, shell=True)
                print("[Video] GStreamer receiver started.")
                
                # Give GStreamer a moment to start
                time.sleep(2)
                
                # Try to connect to the video stream
                self.video_cap = cv2.VideoCapture('udpsrc port=5600 ! application/x-rtp,encoding-name=H264,payload=96 ! rtph264depay ! h264parse ! avdec_h264 ! videoconvert ! appsink', cv2.CAP_GSTREAMER)
                
                threading.Thread(target=self.update_video, daemon=True).start()
                
            except Exception as e:
                print(f"[Video] Failed to start video stream: {e}")
    
    def update_video(self):
        """Update video display in GUI"""
        while self.running:
            if self.video_cap and self.video_cap.isOpened():
                ret, frame = self.video_cap.read()
                if ret:
                    # Resize frame to fit canvas
                    frame = cv2.resize(frame, (640, 360))
                    frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    
                    # Convert to PIL Image
                    image = Image.fromarray(frame)
                    photo = ImageTk.PhotoImage(image)
                    
                    # Update canvas
                    self.video_canvas.delete("all")
                    self.video_canvas.create_image(320, 180, image=photo, anchor=tk.CENTER)
                    self.video_canvas.image = photo  # Keep a reference
            
            time.sleep(1/30)  # 30 FPS
    
    def reconnect_controller(self):
        """Try to reconnect the controller"""
        self.controller.connect_controller()
        self.controller_status.config(
            text="Controller: Connected" if self.controller.connected else "Controller: Disconnected",
            fg='green' if self.controller.connected else 'red'
        )
    
    def start_control_loop(self):
        """Start the control loop"""
        threading.Thread(target=self.control_loop, daemon=True).start()
        
        # Start GUI update loop
        self.update_gui()
    
    def control_loop(self):
        """Main control loop - sends UDP commands"""
        period = 1.0 / SEND_HZ
        last_send_time = 0
        
        while self.running:
            current_time = time.time()
            
            if self.controller.connected:
                self.controller.update()
                
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
                    last_send_time = current_time
                    
                    # Update robot status
                    if current_time - last_send_time < 1.0:
                        status_text = "Robot: Connected"
                        status_color = 'green'
                    else:
                        status_text = "Robot: Timeout"
                        status_color = 'red'
                    
                    self.robot_status.config(text=status_text, fg=status_color)
                    
                except Exception as e:
                    print(f"UDP send error: {e}")
                    self.robot_status.config(text="Robot: Error", fg='red')
            
            time.sleep(period)
    
    def update_gui(self):
        """Update GUI values"""
        if self.controller.connected:
            self.vx_label.config(text=f"Forward: {self.controller.vx:.2f}")
            self.vy_label.config(text=f"Strafe: {self.controller.vy:.2f}")
            self.omega_label.config(text=f"Rotate: {self.controller.omega:.2f}")
            self.speed_label.config(text=f"Speed: {self.controller.speed:.2f}")
        
        # Check controller connection
        if pygame.joystick.get_count() == 0 and self.controller.connected:
            self.controller.connected = False
            self.controller_status.config(text="Controller: Disconnected", fg='red')
        
        # Schedule next update
        self.root.after(50, self.update_gui)  # 20 FPS GUI updates
    
    def on_closing(self):
        """Handle window closing"""
        self.running = False
        
        # Clean up video
        if self.video_cap:
            self.video_cap.release()
        
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
    try:
        app = RobotControlGUI()
        app.run()
    except KeyboardInterrupt:
        pass
    except Exception as e:
        messagebox.showerror("Error", f"Application error: {e}")

if __name__ == "__main__":
    main()
