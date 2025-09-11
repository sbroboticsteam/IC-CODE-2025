# mecanum_server_xbox.py
# Pi Zero 2 W + TB6612FNG x2 | UDP control + GStreamer sender with power saving
# Requires: sudo apt install pigpio gstreamer1.0-tools gstreamer1.0-plugins-base gstreamer1.0-plugins-good
# Also requires rpicam-vid (libcamera stack)

import asyncio, json, math, os, signal, subprocess, sys, time
import pigpio

# ===================== USER CONFIG =====================
PI_UDP_PORT = 5005  # Port this server listens on
PC_VIDEO_IP = "192.168.1.237"  # <-- set to your Windows laptop IP
PC_VIDEO_PORT = 5600

# Motor pins (BCM)
MOTORS = {
    "A": {"EN": 18, "IN1": 23, "IN2": 24, "corner": "FL"},
    "B": {"EN": 19, "IN1": 25, "IN2": 8, "corner": "FR"},
    "C": {"EN": 5, "IN1": 22, "IN2": 26, "corner": "RL"},
    "D": {"EN": 6, "IN1": 16, "IN2": 20, "corner": "RR"},
}

# If any wheel spins the opposite of expected, flip it here (-1)
DIR_OFFSET = {"A": 1, "B": 1, "C": 1, "D": 1}

# TB6612 standby pins (BCM). Leave [] if hard-wired to 3.3V
STBY_PINS = [9, 11]

# PWM behavior
PWM_FREQ_HZ = 10000
MIN_DUTY_FLOOR = 30  # % minimum when |speed| > 0
PURE_DC_THRESHOLD = 80  # % above which we drive EN HIGH (no PWM) for torque

# Safety: stop if no command for this many seconds
COMMAND_TIMEOUT_S = 0.8

# Power saving: enter standby after this many seconds of no input
POWER_SAVE_TIMEOUT_S = 10.0
# =======================================================

pi = pigpio.pi()
if not pi.connected:
    print("ERROR: pigpiod not running. Run: sudo pigpiod", file=sys.stderr)
    sys.exit(1)

def clamp(v, lo, hi):
    return max(lo, min(hi, v))

def _kill_pwm(pin):
    try:
        pi.set_PWM_dutycycle(pin, 0)
    except pigpio.error:
        pass
    try:
        pi.hardware_PWM(pin, 0, 0)  # harmless on non-HW PWM pins
    except pigpio.error:
        pass

def setup_io():
    # Enable STBY (if used)
    for s in STBY_PINS:
        pi.set_mode(s, 1)  # 1 = OUTPUT
        pi.write(s, 1)     # Enable by default
    
    # Motor pins
    for m in MOTORS.values():
        for k in ("EN", "IN1", "IN2"):
            pi.set_mode(m[k], 1)
            pi.write(m[k], 0)
        _kill_pwm(m["EN"])
        pi.set_PWM_frequency(m["EN"], PWM_FREQ_HZ)

def stop_all():
    """Stop all motors"""
    for m in MOTORS.values():
        pi.set_PWM_dutycycle(m["EN"], 0)
        pi.write(m["IN1"], 0)
        pi.write(m["IN2"], 0)

def enter_standby():
    """Enter power saving mode"""
    print("[Power] Entering standby mode")
    stop_all()
    # Disable STBY pins to put motor drivers into standby
    for s in STBY_PINS:
        pi.write(s, 0)

def exit_standby():
    """Exit power saving mode"""
    print("[Power] Exiting standby mode")
    # Enable STBY pins to wake up motor drivers
    for s in STBY_PINS:
        pi.write(s, 1)
    # Small delay to let drivers stabilize
    time.sleep(0.01)

def apply_motor(name, norm):
    """norm ∈ [-1,1]; sign = direction. Applies DIR_OFFSET and stable PWM/DC."""
    norm = clamp(norm, -1.0, 1.0) * DIR_OFFSET[name]
    pins = MOTORS[name]
    
    if abs(norm) < 1e-3:
        pi.set_PWM_dutycycle(pins["EN"], 0)
        pi.write(pins["IN1"], 0)
        pi.write(pins["IN2"], 0)
        return
    
    forward = norm > 0
    pi.write(pins["IN1"], 1 if forward else 0)
    pi.write(pins["IN2"], 0 if forward else 1)
    
    pct = int(abs(norm) * 100)
    if pct >= PURE_DC_THRESHOLD:
        pi.write(pins["EN"], 1)  # solid high
    else:
        pct = max(MIN_DUTY_FLOOR, pct)
        duty = pct * 255 // 100
        pi.set_PWM_dutycycle(pins["EN"], duty)

def drive(vx, vy, omega, max_speed=1.0):
    """
    Standard mecanum:
    FL(A)= vy + vx + omega
    FR(B)= -vy + vx - omega  
    RL(C)= -vy + vx + omega
    RR(D)= vy + vx - omega
    """
    fl = vy + vx + omega
    fr = -vy + vx - omega
    rl = -vy + vx + omega
    rr = vy + vx - omega
    
    # Normalize to prevent any wheel from exceeding ±1
    scale = max(1.0, abs(fl), abs(fr), abs(rl), abs(rr))
    fl /= scale; fr /= scale; rl /= scale; rr /= scale
    
    # Apply max speed
    fl *= max_speed; fr *= max_speed; rl *= max_speed; rr *= max_speed
    
    apply_motor("A", fl)
    apply_motor("B", fr)
    apply_motor("C", rl)
    apply_motor("D", rr)

# ---------- GStreamer sender ----------
gst_proc = None

def start_gstreamer_sender():
    global gst_proc
    cmd = (
        f"rpicam-vid -t 0 --width 1280 --height 720 --framerate 30 "
        f"--codec h264 --bitrate 4000000 --profile baseline --intra 30 --inline "
        f"--nopreview -o - | "
        f"gst-launch-1.0 -v fdsrc ! h264parse ! "
        f"rtph264pay config-interval=1 pt=96 ! "
        f"udpsink host={PC_VIDEO_IP} port={PC_VIDEO_PORT} sync=false async=false"
    )
    
    # Run as shell pipeline so the pipe works
    gst_proc = subprocess.Popen(cmd, shell=True, preexec_fn=os.setsid)
    print(f"[GStreamer] sender started → {PC_VIDEO_IP}:{PC_VIDEO_PORT}")

def stop_gstreamer_sender():
    global gst_proc
    if gst_proc and gst_proc.poll() is None:
        try:
            os.killpg(os.getpgid(gst_proc.pid), signal.SIGTERM)
        except Exception:
            pass
        try:
            gst_proc.wait(timeout=2)
        except:
            pass
        print("[GStreamer] sender stopped.")
    gst_proc = None

# ---------- UDP server ----------
last_cmd_time = 0.0
last_input_time = 0.0  # Track actual user input
in_standby = False
state = {"vx": 0.0, "vy": 0.0, "omega": 0.0, "speed": 1.0, "estop": False}

class ControlProtocol(asyncio.DatagramProtocol):
    def datagram_received(self, data, addr):
        global last_cmd_time, last_input_time, in_standby
        
        try:
            msg = json.loads(data.decode("utf-8"))
        except Exception:
            return
        
        # Expected payload keys: vx, vy, omega, speed, estop, last_input_time (all optional)
        state["vx"] = float(msg.get("vx", state["vx"]))
        state["vy"] = float(msg.get("vy", state["vy"]))
        state["omega"] = float(msg.get("omega", state["omega"]))
        state["speed"] = clamp(float(msg.get("speed", state["speed"])), 0.0, 1.0)
        state["estop"] = bool(msg.get("estop", False))
        
        last_cmd_time = time.time()
        
        # Update last input time from client (when user actually moved controller)
        if "last_input_time" in msg:
            last_input_time = float(msg["last_input_time"])
        
        # Check if we need to exit standby mode
        if in_standby:
            # Check if there's any significant input
            if (abs(state["vx"]) > 0.05 or abs(state["vy"]) > 0.05 or 
                abs(state["omega"]) > 0.05 or state["estop"]):
                exit_standby()
                in_standby = False

async def control_loop():
    """Runs at ~50 Hz; applies last received command, handles power saving"""
    global last_cmd_time, last_input_time, in_standby
    
    while True:
        now = time.time()
        
        # Check for emergency stop or command timeout
        if state["estop"] or (now - last_cmd_time) > COMMAND_TIMEOUT_S:
            stop_all()
        # Check for power saving timeout
        elif (now - last_input_time) > POWER_SAVE_TIMEOUT_S and not in_standby:
            enter_standby()
            in_standby = True
        # Normal operation (not in standby)
        elif not in_standby:
            drive(state["vx"], state["vy"], state["omega"], state["speed"])
        
        await asyncio.sleep(0.02)  # 50 Hz

async def main():
    global last_cmd_time, last_input_time
    
    setup_io()
    start_gstreamer_sender()
    
    # Initialize timestamps
    now = time.time()
    last_cmd_time = now
    last_input_time = now
    
    loop = asyncio.get_running_loop()
    transport, protocol = await loop.create_datagram_endpoint(
        lambda: ControlProtocol(),
        local_addr=("0.0.0.0", PI_UDP_PORT)
    )
    
    print(f"[Control] UDP listening on 0.0.0.0:{PI_UDP_PORT}")
    print(f"[Safety] Will STOP if no command for {COMMAND_TIMEOUT_S}s (or estop=true)")
    print(f"[Power] Will enter standby after {POWER_SAVE_TIMEOUT_S}s of no input")
    
    try:
        await control_loop()
    finally:
        transport.close()
        stop_gstreamer_sender()
        stop_all()
        # Disable standby pins on shutdown
        for s in STBY_PINS:
            pi.write(s, 0)
        pi.stop()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[Shutdown] Received interrupt signal")
    except Exception as e:
        print(f"[Error] {e}")
    finally:
        # Final cleanup
        if pi.connected:
            stop_all()
            for s in STBY_PINS:
                pi.write(s, 0)
            pi.stop()
