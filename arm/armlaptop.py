import tkinter as tk
from tkinter import ttk
import socket
import threading
import time
import json
import pygame

# ============ USER CONFIG ============
PI_IP = "192.168.0.103"    # Your Pi's IP
PI_PORT = 5005
SEND_HZ = 30
BASE_SPEED = 0.6
BOOST_SPEED = 1.0
SLOW_SPEED = 0.3
DEADZONE = 0.12
# =====================================

class XboxController:
    def __init__(self):
        pygame.init()
        pygame.joystick.init()
        self.joystick = None
        self.connected = False
        self.last_input_time = time.time()
        self.vx = 0.0
        self.vy = 0.0
        self.omega = 0.0
        self.speed = BASE_SPEED
        self.arm = 0.0
        self.claw = 0.0
        self.estop = False
        self.fire = False
        self.connect_controller()
    def connect_controller(self):
        try:
            if pygame.joystick.get_count() > 0:
                self.joystick = pygame.joystick.Joystick(0)
                self.joystick.init()
                self.connected = True
            else:
                self.connected = False
        except Exception:
            self.connected = False
    def apply_deadzone(self, value, deadzone=DEADZONE):
        return value if abs(value) > deadzone else 0.0
    def clamp(self, x, lo, hi):
        return max(lo, min(hi, x))
    def update(self):
        if not self.connected:
            self.connect_controller()
            return None
        
        try:
            pygame.event.pump()
            
            # Left stick: mecanum drive
            self.vx = -self.apply_deadzone(self.joystick.get_axis(1))  # Forward/back (inverted)
            self.vy = self.apply_deadzone(self.joystick.get_axis(0))   # Strafe left/right
            self.omega = self.apply_deadzone(self.joystick.get_axis(3))  # Right stick X for rotation
            
            # Triggers for speed control
            rt = (self.joystick.get_axis(5) + 1) / 2  # RT: 0 to 1
            lt = (self.joystick.get_axis(2) + 1) / 2  # LT: 0 to 1
            
            if self.joystick.get_button(4):  # LB for full boost
                self.speed = BOOST_SPEED
            elif lt > 0.1:  # Left trigger for slow mode
                self.speed = SLOW_SPEED + (BASE_SPEED - SLOW_SPEED) * (1 - lt)
            elif rt > 0.1:  # Right trigger for boost
                self.speed = BASE_SPEED + (BOOST_SPEED - BASE_SPEED) * rt
            else:
                self.speed = BASE_SPEED
            
            # Arm lift: D-pad up/down
            hat = self.joystick.get_hat(0)
            if hat[1] > 0:  # D-pad up
                self.arm = 1.0
            elif hat[1] < 0:  # D-pad down
                self.arm = -1.0
            else:
                self.arm = 0.0
            
            # Claw: D-pad left/right
            if hat[0] > 0:  # D-pad right
                self.claw = 1.0  # Close
            elif hat[0] < 0:  # D-pad left
                self.claw = 0.0  # Open
            # Keep current claw position if no D-pad input
            
            # Emergency stop: B button
            self.estop = bool(self.joystick.get_button(1))
            
            self.last_input_time = time.time()
            
            return {
                "vx": self.vx, "vy": self.vy, "omega": self.omega, "speed": self.speed,
                "arm": self.arm, "claw": self.claw, "estop": self.estop
            }
            
        except Exception as e:
            print(f"Controller error: {e}")
            self.connected = False
            return None

class ArmRobotGUI:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("🤖 Arm Robot Control (armlaptop.py)")
        self.root.geometry("600x400")
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.addr = (PI_IP, PI_PORT)
        self.controller = XboxController()
        self.running = True
        self.arm_val = 0.0
        self.claw_val = 0.0
        self.setup_gui()
        self.start_control_loop()
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
    def setup_gui(self):
        main_frame = tk.Frame(self.root, bg='#2b2b2b')
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        title_label = tk.Label(main_frame, text="🤖 Arm Robot Control", 
                              font=('Arial', 20, 'bold'), bg='#2b2b2b', fg='white')
        title_label.pack(pady=10)
        
        content_frame = tk.Frame(main_frame, bg='#2b2b2b')
        content_frame.pack(fill=tk.BOTH, expand=True)
        
        left_frame = tk.Frame(content_frame, bg='#2b2b2b')
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))
        
        # Arm controls
        arm_frame = tk.LabelFrame(left_frame, text="🦾 Arm Lift", 
                                 font=('Arial', 12, 'bold'), bg='#3b3b3b', fg='white')
        arm_frame.pack(fill=tk.X, pady=5)
        
        self.arm_slider = tk.Scale(arm_frame, from_=-1, to=1, resolution=0.1, orient=tk.HORIZONTAL, length=300,
                                   label="Arm Lift (-1=Down, 1=Up)", bg='#3b3b3b', fg='white', 
                                   command=self.on_arm_slider)
        self.arm_slider.set(0)
        self.arm_slider.pack(pady=5)
        
        # Claw controls
        claw_frame = tk.LabelFrame(left_frame, text="🦀 Claw", 
                                  font=('Arial', 12, 'bold'), bg='#3b3b3b', fg='white')
        claw_frame.pack(fill=tk.X, pady=5)
        
        self.claw_slider = tk.Scale(claw_frame, from_=0, to=1, resolution=0.01, orient=tk.HORIZONTAL, length=300,
                                    label="Claw (0=Open, 1=Close)", bg='#3b3b3b', fg='white', 
                                    command=self.on_claw_slider)
        self.claw_slider.set(0)
        self.claw_slider.pack(pady=5)
        
        # Status
        status_frame = tk.LabelFrame(left_frame, text="📡 Status", 
                                    font=('Arial', 12, 'bold'), bg='#3b3b3b', fg='white')
        status_frame.pack(fill=tk.X, pady=5)
        
        self.status_label = tk.Label(status_frame, text="Controller: Disconnected", 
                                    font=('Arial', 12), bg='#3b3b3b', fg='red')
        self.status_label.pack(pady=5)
        
        # Current values display
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
        
        self.arm_label = tk.Label(values_frame, text="Arm: 0.00", 
                                 font=('Arial', 10), bg='#3b3b3b', fg='white')
        self.arm_label.pack(pady=2)
        
        self.claw_label = tk.Label(values_frame, text="Claw: 0.00", 
                                  font=('Arial', 10), bg='#3b3b3b', fg='white')
        self.claw_label.pack(pady=2)
        
        # Right frame - Controls info
        right_frame = tk.Frame(content_frame, bg='#2b2b2b')
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        
        # Controls instruction
        controls_frame = tk.LabelFrame(right_frame, text="🎮 Xbox Controller Mapping", 
                                      font=('Arial', 12, 'bold'), bg='#3b3b3b', fg='white')
        controls_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        controls_text = """🎮 MOVEMENT:
Left Stick ↕️ : Forward/Backward
Left Stick ↔️ : Strafe Left/Right  
Right Stick ↔️ : Rotate Left/Right

⚡ SPEED CONTROL:
Right Trigger (RT): Boost Speed
LB Button: Full Boost Speed
Left Trigger (LT): Slow Mode

🦾 ARM CONTROLS:
D-Pad ↑ : Arm Lift Up
D-Pad ↓ : Arm Lift Down

🦀 CLAW CONTROLS:
D-Pad → : Close Claw
D-Pad ← : Open Claw

🛑 SAFETY:
B Button: Emergency Stop

💡 TIPS:
• Use GUI sliders to override controller
• Reset sliders to 0 to return control to D-pad
• RT/LT triggers are variable speed
• B button stops robot instantly"""
        
        controls_label = tk.Label(controls_frame, text=controls_text, font=('Arial', 9),
                                 bg='#3b3b3b', fg='white', justify=tk.LEFT)
        controls_label.pack(padx=10, pady=10, anchor='nw')
    def on_arm_slider(self, val):
        self.arm_val = float(val)
    def on_claw_slider(self, val):
        self.claw_val = float(val)
    def start_control_loop(self):
        threading.Thread(target=self.control_loop, daemon=True).start()
        self.update_gui()
    def control_loop(self):
        period = 1.0 / SEND_HZ
        while self.running:
            ctrl = self.controller.update()
            if ctrl is not None:
                # Only override with GUI if sliders are moved from default
                # Arm: default is 0.0 (center)
                # Claw: default is 0.0 (open)
                arm_override = abs(self.arm_val) > 1e-2
                claw_override = abs(self.claw_val) > 1e-2
                if arm_override:
                    ctrl["arm"] = self.arm_val
                # else: use controller value
                if claw_override:
                    ctrl["claw"] = self.claw_val
                # else: use controller value
                try:
                    self.sock.sendto(json.dumps(ctrl).encode(), self.addr)
                except Exception:
                    pass
            time.sleep(period)
    def update_gui(self):
        if not self.running:
            return
        
        # Update controller status
        if self.controller.connected:
            self.status_label.config(text="Controller: Connected", fg='green')
            
            # Update current values display
            if hasattr(self.controller, 'vx'):
                self.vx_label.config(text=f"Forward/Back: {self.controller.vx:.2f}")
                self.vy_label.config(text=f"Strafe L/R: {self.controller.vy:.2f}")
                self.omega_label.config(text=f"Rotate L/R: {self.controller.omega:.2f}")
                self.speed_label.config(text=f"Speed: {self.controller.speed:.2f}")
                self.arm_label.config(text=f"Arm: {self.controller.arm:.2f}")
                self.claw_label.config(text=f"Claw: {self.controller.claw:.2f}")
        else:
            self.status_label.config(text="Controller: Disconnected", fg='red')
            # Reset values display
            self.vx_label.config(text="Forward/Back: 0.00")
            self.vy_label.config(text="Strafe L/R: 0.00")
            self.omega_label.config(text="Rotate L/R: 0.00")
            self.speed_label.config(text="Speed: 0.60")
            self.arm_label.config(text="Arm: 0.00")
            self.claw_label.config(text="Claw: 0.00")
        
        self.root.after(100, self.update_gui)
    def on_closing(self):
        self.running = False
        self.root.destroy()
    def run(self):
        self.root.mainloop()

def main():
    print("🤖 Arm Robot Control (armlaptop.py)")
    try:
        gui = ArmRobotGUI()
        gui.run()
    except KeyboardInterrupt:
        print("\n[Shutdown] Received interrupt")
    except Exception as e:
        print(f"[Error] {e}")

if __name__ == "__main__":
    main()
