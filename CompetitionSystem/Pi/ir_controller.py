#!/usr/bin/env python3
"""
IR Controller - PROTECTED FILE - DO NOT MODIFY
Handles IR transmission, reception, hit detection, and game communication
"""

import pigpio
import time
import json
import socket
from typing import Dict, List, Callable
from datetime import datetime

class IRController:
    def __init__(self, pi: pigpio.pi, config: Dict, team_id: int, gv_ip: str, gv_port: int):
        self.pi = pi
        self.config = config['ir_system']
        self.team_id = team_id
        self.gv_ip = gv_ip
        self.gv_port = gv_port
        
        # IR pins
        self.tx_gpio = self.config['transmitter_gpio']
        self.rx_gpios = self.config['receiver_gpios']
        
        # Protocol timing
        self.carrier_freq = self.config['carrier_frequency']
        self.carrier_period_us = int(1_000_000 / self.carrier_freq)
        self.pulse_on_us = self.carrier_period_us // 2
        self.pulse_off_us = self.carrier_period_us - self.pulse_on_us
        
        protocol = self.config['protocol']
        self.bit_0_burst = protocol['bit_0_burst_us']
        self.bit_1_burst = protocol['bit_1_burst_us']
        self.start_end_burst = protocol['start_end_burst_us']
        self.tolerance = protocol['tolerance_us']
        
        # Weapon cooldown and hit timing
        self.weapon_cooldown = self.config['weapon_cooldown_ms'] / 1000.0
        self.hit_disable_time = self.config['hit_disable_time_s']
        self.last_fire_time = 0
        
        # Hit tracking
        self.is_hit = False
        self.hit_by_team = 0
        self.hit_time = 0
        self.time_remaining = 0
        self.hit_log: List[Dict] = []
        self.game_start_time = None
        
        # Callbacks
        self.on_hit_callback: Callable = None
        
        # Network
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        
        # Receivers
        self.receivers: List['IRReceiver'] = []
        
        self.setup_ir()
    
    def setup_ir(self):
        """Initialize IR hardware"""
        print("[IR] Initializing IR system...")
        
        # Setup transmitter
        self.pi.set_mode(self.tx_gpio, pigpio.OUTPUT)
        self.pi.write(self.tx_gpio, 0)
        
        # Setup receivers
        for gpio in self.rx_gpios:
            receiver = IRReceiver(self.pi, gpio, self)
            self.receivers.append(receiver)
        
        print(f"[IR] Initialized - TX on GPIO {self.tx_gpio}, RX on {self.rx_gpios}")
    
    def start_game(self):
        """Called when game starts - resets hit log"""
        print("[IR] Game started - resetting hit log")
        self.game_start_time = time.time()
        self.hit_log = []
        self.is_hit = False
        self.hit_by_team = 0
        self.hit_time = 0
        self.time_remaining = 0
    
    def end_game(self):
        """Called when game ends"""
        print(f"[IR] Game ended - Total hits received: {len(self.hit_log)}")
        self.game_start_time = None
    
    def send_ir_burst(self, burst_us: int):
        """Send modulated IR burst"""
        self.pi.wave_clear()
        
        # Create carrier wave
        cycle = [
            pigpio.pulse(1 << self.tx_gpio, 0, self.pulse_on_us),
            pigpio.pulse(0, 1 << self.tx_gpio, self.pulse_off_us)
        ]
        self.pi.wave_add_generic(cycle)
        wid = self.pi.wave_create()
        
        # Calculate number of cycles
        cycles = burst_us // self.carrier_period_us
        
        # Transmit
        self.pi.wave_chain([255, 0, wid, 255, 1, cycles & 255, (cycles >> 8) & 255])
        
        while self.pi.wave_tx_busy():
            time.sleep(0.0001)
        
        self.pi.wave_delete(wid)
    
    def send_ir_bit(self, bit: int):
        """Send a single bit"""
        if bit == 1:
            self.send_ir_burst(self.bit_1_burst)
        else:
            self.send_ir_burst(self.bit_0_burst)
        time.sleep(0.0008)
    
    def fire(self) -> bool:
        """Fire IR weapon - returns True if fired successfully"""
        current_time = time.time()
        
        # Check if we're disabled from being hit
        if self.is_hit:
            return False
        
        # Check weapon cooldown
        if current_time - self.last_fire_time < self.weapon_cooldown:
            return False
        
        self.last_fire_time = current_time
        
        print(f"[IR] 🔫 Firing! Team {self.team_id}")
        
        # Start burst
        self.send_ir_burst(self.start_end_burst)
        time.sleep(0.0008)
        
        # Send 8-bit team ID
        for i in range(8):
            bit = (self.team_id >> (7 - i)) & 1
            self.send_ir_bit(bit)
        
        # End burst
        self.send_ir_burst(self.start_end_burst)
        
        return True
    
    def on_hit_received(self, attacking_team: int):
        """Called when robot is hit by another team's IR"""
        if self.is_hit:
            return  # Already hit
        
        current_time = time.time()
        
        # Check for self-hit
        if attacking_team == self.team_id:
            print(f"[IR] ⚠️ SELF HIT DETECTED - Team {attacking_team} (ignoring)")
            return  # Don't process self-hits
        
        print(f"[IR] 💥 HIT! Attacked by Team {attacking_team}")
        
        # Update hit state
        self.is_hit = True
        self.hit_by_team = attacking_team
        self.hit_time = current_time
        self.time_remaining = self.hit_disable_time
        
        # Log the hit
        hit_record = {
            "timestamp": datetime.now().isoformat(),
            "game_time": current_time - self.game_start_time if self.game_start_time else 0,
            "attacking_team": attacking_team,
            "defending_team": self.team_id
        }
        self.hit_log.append(hit_record)
        
        # Send hit notification to Game Viewer
        self.send_hit_to_gv(hit_record)
        
        # Trigger callback
        if self.on_hit_callback:
            self.on_hit_callback()
    
    def send_hit_to_gv(self, hit_record: Dict):
        """Send hit notification to Game Viewer"""
        try:
            message = {
                "type": "HIT_REPORT",
                "data": hit_record
            }
            
            self.sock.sendto(
                json.dumps(message).encode('utf-8'),
                (self.gv_ip, self.gv_port)
            )
            
            print(f"[IR] Sent hit report to GV ({self.gv_ip}:{self.gv_port})")
        
        except Exception as e:
            print(f"[IR] Failed to send hit to GV: {e}")
    
    def update(self):
        """Update hit timer - call this in main loop"""
        if not self.is_hit:
            return
        
        current_time = time.time()
        elapsed = current_time - self.hit_time
        self.time_remaining = max(0, self.hit_disable_time - elapsed)
        
        # Check if respawn time is up
        if elapsed >= self.hit_disable_time:
            print("[IR] ✅ Respawning!")
            self.is_hit = False
            self.hit_by_team = 0
            self.hit_time = 0
            self.time_remaining = 0
    
    def get_status(self) -> Dict:
        """Get current hit status"""
        return {
            "is_hit": self.is_hit,
            "hit_by_team": self.hit_by_team,
            "time_remaining": self.time_remaining,
            "total_hits": len(self.hit_log)
        }
    
    def get_hit_log(self) -> List[Dict]:
        """Get complete hit log"""
        return self.hit_log.copy()
    
    def cleanup(self):
        """Clean up IR resources"""
        print("[IR] Cleaning up...")
        for receiver in self.receivers:
            receiver.cleanup()
        self.sock.close()


class IRReceiver:
    """IR Receiver - monitors a single GPIO for IR signals"""
    
    def __init__(self, pi: pigpio.pi, gpio: int, controller: IRController):
        self.pi = pi
        self.gpio = gpio
        self.controller = controller
        
        self.bursts: List[int] = []
        self.last_tick = 0
        self.last_burst_time = 0
        
        # Setup GPIO
        self.pi.set_mode(self.gpio, pigpio.INPUT)
        self.pi.set_pull_up_down(self.gpio, pigpio.PUD_UP)
        
        # Register callback
        self.cb = self.pi.callback(self.gpio, pigpio.EITHER_EDGE, self.edge_callback)
        
        print(f"[IR] Receiver monitoring GPIO {self.gpio}")
    
    def edge_callback(self, gpio, level, tick):
        """Callback for IR signal edges"""
        current_time = time.time()
        
        if level == 0:  # Start of IR burst (active low)
            self.last_tick = tick
        
        elif level == 1 and self.last_tick:  # End of IR burst
            burst_width = pigpio.tickDiff(self.last_tick, tick)
            
            # New transmission if gap > 100ms
            if current_time - self.last_burst_time > 0.1:
                if len(self.bursts) > 0:
                    self.process_bursts()
                self.bursts = []
            
            self.bursts.append(burst_width)
            self.last_burst_time = current_time
            
            # Process complete transmission (10 bursts)
            if len(self.bursts) == 10:
                self.process_bursts()
                self.bursts = []
    
    def process_bursts(self):
        """Decode received IR bursts"""
        if len(self.bursts) != 10:
            return
        
        tolerance = self.controller.tolerance
        
        # Validate start and end bursts
        if (abs(self.bursts[0] - self.controller.start_end_burst) > tolerance or
            abs(self.bursts[9] - self.controller.start_end_burst) > tolerance):
            return
        
        # Decode 8-bit team ID
        team_id = 0
        for i in range(1, 9):
            burst = self.bursts[i]
            bit_position = 7 - (i - 1)
            
            if abs(burst - self.controller.bit_1_burst) <= tolerance:
                team_id |= (1 << bit_position)
            elif abs(burst - self.controller.bit_0_burst) <= tolerance:
                pass  # Bit is 0
            else:
                return  # Invalid burst width
        
        # Valid team ID received
        self.controller.on_hit_received(team_id)
    
    def cleanup(self):
        """Clean up receiver"""
        self.cb.cancel()
