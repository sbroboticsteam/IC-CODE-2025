#!/usr/bin/env python3
"""
Arm Robot Control System (armpi.py)
- UDP control for mecanum drive (4 motors), arm lift (1 motor), and claw servo
- No IR, no camera, no hit logic
"""
import pigpio
import time
import sys
import asyncio
import socket
import json

# ===================== USER CONFIG =====================
PI_UDP_PORT = 5005

# Motor pins (BCM numbering) - Updated to match your pin connections
MOTORS = {
    "FR": {"EN": 7, "IN1": 15, "IN2": 13},
    "BR": {"EN": 17, "IN1": 19, "IN2": 21},
    "FL": {"EN": 8, "IN1": 16, "IN2": 12},
    "BL": {"EN": 10, "IN1": 18, "IN2": 22},
    "ARM": {"EN": 37, "IN1": 38, "IN2": 40},
}
CLAW_SERVO_PWM = 33

# Standby pins
STBY_PINS = [23, 24, 36]  # Right driver, Left driver, Arm driver

# Motor configuration (same as original)
DIR_OFFSET = {"FR": 1, "BR": 1, "FL": 1, "BL": 1, "ARM": 1}
PWM_FREQ_HZ = 10000
MIN_DUTY_FLOOR = 30
PURE_DC_THRESHOLD = 80

# Servo config
SERVO_OPEN = 1000   # microseconds
SERVO_CLOSE = 2000  # microseconds

# =======================================================

# Global variables
pi = None
bad_pins = set()  # Track pins that can't be accessed

state = {
    "vx": 0.0, "vy": 0.0, "omega": 0.0, "speed": 1.0,
    "arm": 0.0,  # -1.0 (down) to 1.0 (up)
    "claw": 0.0, # 0.0=open, 1.0=close
}

def init_pigpio():
    global pi
    pi = pigpio.pi()
    if not pi.connected:
        print("ERROR: pigpiod not running. Run: sudo pigpiod", file=sys.stderr)
        sys.exit(1)

def clamp(v, lo, hi):
    return max(lo, min(hi, v))

def setup_io():
    # Enable STBY pins
    for s in STBY_PINS:
        try:
            pi.set_mode(s, pigpio.OUTPUT)
            pi.write(s, 1)
            print(f"[GPIO] STBY pin {s} configured successfully")
        except Exception as e:
            print(f"[GPIO] WARNING: Could not configure STBY pin {s}: {e}")
            bad_pins.add(s)
    
    # Motor pins
    for motor_name, m in MOTORS.items():
        for k in ("EN", "IN1", "IN2"):
            try:
                pi.set_mode(m[k], pigpio.OUTPUT)
                pi.write(m[k], 0)
                if k == "EN":
                    pi.set_PWM_frequency(m[k], PWM_FREQ_HZ)
                print(f"[GPIO] {motor_name} {k} pin {m[k]} configured successfully")
            except Exception as e:
                print(f"[GPIO] WARNING: Could not configure {motor_name} {k} pin {m[k]}: {e}")
                bad_pins.add(m[k])
    
    # Servo
    try:
        pi.set_mode(CLAW_SERVO_PWM, pigpio.OUTPUT)
        pi.set_servo_pulsewidth(CLAW_SERVO_PWM, 0)
        print(f"[GPIO] Servo pin {CLAW_SERVO_PWM} configured successfully")
    except Exception as e:
        print(f"[GPIO] WARNING: Could not configure servo pin {CLAW_SERVO_PWM}: {e}")
        bad_pins.add(CLAW_SERVO_PWM)

def stop_all_motors():
    for motor_name, m in MOTORS.items():
        try:
            if m["EN"] not in bad_pins:
                pi.set_PWM_dutycycle(m["EN"], 0)
            if m["IN1"] not in bad_pins:
                pi.write(m["IN1"], 0)
            if m["IN2"] not in bad_pins:
                pi.write(m["IN2"], 0)
        except Exception as e:
            print(f"[GPIO] WARNING: Could not stop {motor_name}: {e}")

def apply_motor(name, norm):
    norm = clamp(norm, -1.0, 1.0) * DIR_OFFSET[name]
    pins = MOTORS[name]
    
    # Check if any pins for this motor are bad
    if pins["EN"] in bad_pins or pins["IN1"] in bad_pins or pins["IN2"] in bad_pins:
        return  # Skip this motor
    
    try:
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
            pi.write(pins["EN"], 1)
        else:
            pct = max(MIN_DUTY_FLOOR, pct)
            duty = pct * 255 // 100
            pi.set_PWM_dutycycle(pins["EN"], duty)
    except Exception as e:
        print(f"[GPIO] WARNING: Could not control motor {name}: {e}")
        # Add pins to bad list
        bad_pins.update([pins["EN"], pins["IN1"], pins["IN2"]])

def drive_mecanum(vx, vy, omega, max_speed=1.0):
    # Standard mecanum drive
    fl = vy + vx + omega
    fr = -vy + vx - omega
    bl = vy - vx + omega
    br = -vy - vx - omega
    scale = max(1.0, abs(fl), abs(fr), abs(bl), abs(br))
    fl /= scale; fr /= scale; bl /= scale; br /= scale
    fl *= max_speed; fr *= max_speed; bl *= max_speed; br *= max_speed
    apply_motor("FL", fl)
    apply_motor("FR", fr)
    apply_motor("BL", bl)
    apply_motor("BR", br)

def apply_arm_lift(norm):
    apply_motor("ARM", norm)

def set_claw_servo(pos):
    # pos: 0.0=open, 1.0=close
    if CLAW_SERVO_PWM in bad_pins:
        return  # Skip if servo pin is bad
    
    try:
        pulse = int(SERVO_OPEN + (SERVO_CLOSE - SERVO_OPEN) * clamp(pos, 0.0, 1.0))
        pi.set_servo_pulsewidth(CLAW_SERVO_PWM, pulse)
    except Exception as e:
        print(f"[GPIO] WARNING: Could not control servo: {e}")
        bad_pins.add(CLAW_SERVO_PWM)

class ControlProtocol(asyncio.DatagramProtocol):
    def datagram_received(self, data, addr):
        try:
            msg = json.loads(data.decode())
        except Exception:
            return
        state["vx"] = float(msg.get("vx", 0.0))
        state["vy"] = float(msg.get("vy", 0.0))
        state["omega"] = float(msg.get("omega", 0.0))
        state["speed"] = clamp(float(msg.get("speed", 1.0)), 0.0, 1.0)
        state["arm"] = clamp(float(msg.get("arm", 0.0)), -1.0, 1.0)
        state["claw"] = clamp(float(msg.get("claw", 0.0)), 0.0, 1.0)

async def control_loop():
    while True:
        # Drive
        drive_mecanum(state["vx"], state["vy"], state["omega"], state["speed"])
        # Arm
        apply_arm_lift(state["arm"])
        # Claw
        set_claw_servo(state["claw"])
        await asyncio.sleep(0.02)  # 50 Hz

def cleanup():
    print("\n[Shutdown] Cleaning up...")
    
    # Stop motors and disable standby
    stop_all_motors()
    for s in STBY_PINS:
        try:
            if s not in bad_pins:
                pi.write(s, 0)
        except Exception as e:
            print(f"[GPIO] WARNING: Could not disable STBY pin {s}: {e}")
    
    # Stop servo
    try:
        if CLAW_SERVO_PWM not in bad_pins:
            pi.set_servo_pulsewidth(CLAW_SERVO_PWM, 0)
    except Exception as e:
        print(f"[GPIO] WARNING: Could not stop servo: {e}")
    
    # Close pigpio
    if pi:
        pi.stop()
    
    if bad_pins:
        print(f"[GPIO] Bad pins detected: {sorted(bad_pins)}")
    print("[Shutdown] Cleanup complete")

async def main():
    print("🤖 Arm Robot Control (armpi.py)")
    init_pigpio()
    setup_io()
    
    if bad_pins:
        print(f"[GPIO] WARNING: Some pins could not be configured: {sorted(bad_pins)}")
        print("[GPIO] Robot will continue with available pins...")
    else:
        print("[GPIO] All pins configured successfully!")
    
    loop = asyncio.get_running_loop()
    transport, protocol = await loop.create_datagram_endpoint(
        lambda: ControlProtocol(),
        local_addr=("0.0.0.0", PI_UDP_PORT)
    )
    print(f"[Control] UDP listening on 0.0.0.0:{PI_UDP_PORT}")
    try:
        await control_loop()
    finally:
        transport.close()
        cleanup()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[Shutdown] Received interrupt")
    except Exception as e:
        print(f"[Error] {e}")
    finally:
        cleanup()
