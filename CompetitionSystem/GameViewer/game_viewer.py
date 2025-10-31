#!/usr/bin/env python3
"""
Game Viewer - Tournament Management System
Displays multiple robot video feeds and manages game state
"""

import json
import os
import socket
import sys
import threading
import time
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
from typing import Dict, List
from datetime import datetime

# Game Viewer Configuration
GV_CONFIG = {
    "gv_ip": "0.0.0.0",  # Listen on all interfaces
    "gv_port": 6000,
    "max_teams": 8,
    "game_duration": 120,  # 2 minutes (configurable)
    "points_per_hit": 100,
    "video_ports_start": 5001  # Team 1 = 5001, Team 2 = 5002, etc.
}

CONFIG_FILE = "game_viewer_config.json"


class GameViewer:
    """Main game viewer application"""
    
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("🎯 LASER TAG - Game Viewer")
        self.root.geometry("1400x900")
        self.root.configure(bg='#1a1a1a')
        
        # Load config
        self.config = self.load_config()
        
        # Game state
        self.teams: Dict[int, dict] = {}  # team_id -> team_data
        self.game_active = False
        self.game_start_time = 0
        self.game_time_remaining = 0
        
        # Network
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.settimeout(0.1)
        
        # Bind to port
        try:
            self.sock.bind((self.config['gv_ip'], self.config['gv_port']))
            print(f"[GV] Listening on {self.config['gv_ip']}:{self.config['gv_port']}")
        except Exception as e:
            messagebox.showerror("Network Error", f"Failed to bind to port: {e}")
            sys.exit(1)
        
        # Hit log
        self.hit_log: List[dict] = []
        
        # Threading
        self.running = True
        
        # Setup GUI
        self.setup_gui()
        
        # Start network listener
        self.start_network_thread()
        
        # Start update loop
        self.update_gui()
        
        # Cleanup handler
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
    
    def load_config(self):
        """Load configuration"""
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r') as f:
                    return json.load(f)
            except:
                pass
        return GV_CONFIG.copy()
    
    def save_config(self):
        """Save configuration"""
        try:
            with open(CONFIG_FILE, 'w') as f:
                json.dump(self.config, f, indent=2)
        except Exception as e:
            print(f"[GV] Failed to save config: {e}")
    
    def setup_gui(self):
        """Create GUI"""
        # Main container
        main_frame = tk.Frame(self.root, bg='#1a1a1a')
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Title
        title_label = tk.Label(main_frame, text="🎯 LASER TAG TOURNAMENT - GAME VIEWER",
                              font=('Arial', 24, 'bold'), bg='#1a1a1a', fg='#00ff00')
        title_label.pack(pady=(0, 10))
        
        # Top section - Game status and timer
        top_section = tk.Frame(main_frame, bg='#1a1a1a')
        top_section.pack(fill=tk.X, pady=(0, 10))
        
        # Game status
        status_frame = tk.LabelFrame(top_section, text="🎮 Game Status",
                                     font=('Arial', 12, 'bold'), bg='#2d2d2d', fg='#00ff00')
        status_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))
        
        self.game_status_label = tk.Label(status_frame, text="Status: Waiting",
                                          font=('Arial', 16, 'bold'), bg='#2d2d2d', fg='yellow')
        self.game_status_label.pack(pady=10)
        
        self.timer_label = tk.Label(status_frame, text="Time: 00:00",
                                    font=('Arial', 14), bg='#2d2d2d', fg='white')
        self.timer_label.pack(pady=5)
        
        # Control panel
        control_frame = tk.LabelFrame(top_section, text="🎛️ Control Panel",
                                      font=('Arial', 12, 'bold'), bg='#2d2d2d', fg='#00ff00')
        control_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(5, 0))
        
        btn_frame = tk.Frame(control_frame, bg='#2d2d2d')
        btn_frame.pack(pady=10)
        
        self.ready_check_btn = tk.Button(btn_frame, text="📢 Ready Check",
                                         command=self.send_ready_check,
                                         font=('Arial', 10), bg='#FF9800', fg='white', width=15)
        self.ready_check_btn.pack(pady=2)
        
        self.start_game_btn = tk.Button(btn_frame, text="▶️ Start Game",
                                        command=self.start_game,
                                        font=('Arial', 10, 'bold'), bg='#4CAF50', fg='white', width=15)
        self.start_game_btn.pack(pady=2)
        
        self.end_game_btn = tk.Button(btn_frame, text="⏹️ End Game",
                                      command=self.end_game,
                                      font=('Arial', 10, 'bold'), bg='#f44336', fg='white',
                                      width=15, state=tk.DISABLED)
        self.end_game_btn.pack(pady=2)
        
        tk.Button(btn_frame, text="� View Cameras",
                 command=self.open_camera_viewer,
                 font=('Arial', 10), bg='#9C27B0', fg='white', width=15).pack(pady=2)
        
        tk.Button(btn_frame, text="�💾 Export Log",
                 command=self.export_log,
                 font=('Arial', 10), bg='#2196F3', fg='white', width=15).pack(pady=2)
        
        tk.Button(btn_frame, text="⚙️ Settings",
                 command=self.open_settings,
                 font=('Arial', 10), bg='#607D8B', fg='white', width=15).pack(pady=2)
        
        # Main content - 3 columns
        content_frame = tk.Frame(main_frame, bg='#1a1a1a')
        content_frame.pack(fill=tk.BOTH, expand=True)
        
        # Left - Leaderboard
        left_frame = tk.LabelFrame(content_frame, text="🏆 Leaderboard",
                                   font=('Arial', 12, 'bold'), bg='#2d2d2d', fg='#00ff00')
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))
        
        # Leaderboard tree
        self.leaderboard_tree = ttk.Treeview(left_frame,
                                            columns=('Rank', 'Team', 'Points', 'K', 'D', 'K/D'),
                                            show='headings', height=15)
        
        for col in ('Rank', 'Team', 'Points', 'K', 'D', 'K/D'):
            self.leaderboard_tree.heading(col, text=col)
        
        self.leaderboard_tree.column('Rank', width=50)
        self.leaderboard_tree.column('Team', width=150)
        self.leaderboard_tree.column('Points', width=80)
        self.leaderboard_tree.column('K', width=50)
        self.leaderboard_tree.column('D', width=50)
        self.leaderboard_tree.column('K/D', width=60)
        
        self.leaderboard_tree.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Middle - Teams info
        middle_frame = tk.LabelFrame(content_frame, text="🤖 Connected Teams",
                                     font=('Arial', 12, 'bold'), bg='#2d2d2d', fg='#00ff00')
        middle_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))
        
        self.teams_text = scrolledtext.ScrolledText(middle_frame,
                                                    font=('Courier', 9),
                                                    bg='#1a1a1a', fg='white',
                                                    height=20, width=40)
        self.teams_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Right - Hit log
        right_frame = tk.LabelFrame(content_frame, text="💥 Hit Log",
                                    font=('Arial', 12, 'bold'), bg='#2d2d2d', fg='#00ff00')
        right_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        self.hit_log_text = scrolledtext.ScrolledText(right_frame,
                                                      font=('Courier', 8),
                                                      bg='#1a1a1a', fg='#00ff00',
                                                      height=20, width=50)
        self.hit_log_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Bottom - Video info
        bottom_frame = tk.LabelFrame(main_frame, text="📹 Video Streams",
                                     font=('Arial', 12, 'bold'), bg='#2d2d2d', fg='#00ff00')
        bottom_frame.pack(fill=tk.X, pady=(10, 0))
        
        video_info = "Video streams available on ports 5001-5008\n"
        video_info += "Use GStreamer to view: gst-launch-1.0 udpsrc port=<PORT> caps=... ! autovideosink"
        
        tk.Label(bottom_frame, text=video_info,
                font=('Courier', 9), bg='#2d2d2d', fg='cyan', justify=tk.LEFT).pack(padx=10, pady=10)
    
    def start_network_thread(self):
        """Start network listener thread"""
        thread = threading.Thread(target=self.network_loop, daemon=True)
        thread.start()
        print("[GV] Network thread started")
    
    def network_loop(self):
        """Network listener loop"""
        while self.running:
            try:
                data, addr = self.sock.recvfrom(4096)
                message = json.loads(data.decode('utf-8'))
                self.handle_message(message, addr)
            except socket.timeout:
                continue
            except json.JSONDecodeError:
                continue
            except Exception as e:
                if self.running:
                    print(f"[GV] Network error: {e}")
    
    def handle_message(self, message: dict, addr: tuple):
        """Handle incoming message"""
        msg_type = message.get('type')
        team_id = message.get('team_id')
        
        if msg_type == 'REGISTER':
            # Team registration
            self.register_team(team_id, message, addr)
        
        elif msg_type == 'HEARTBEAT':
            # Update team heartbeat
            if team_id in self.teams:
                self.teams[team_id]['last_heartbeat'] = time.time()
                self.teams[team_id]['addr'] = addr
        
        elif msg_type == 'HIT_REPORT':
            # Process hit
            self.process_hit(message.get('data', {}))
        
        elif msg_type == 'READY_STATUS':
            # Update ready status
            if team_id in self.teams:
                self.teams[team_id]['ready'] = message.get('ready', False)
    
    def register_team(self, team_id: int, message: dict, addr: tuple):
        """Register a new team"""
        if team_id not in self.teams:
            self.teams[team_id] = {
                'team_id': team_id,
                'team_name': message.get('team_name', f'Team {team_id}'),
                'robot_name': message.get('robot_name', f'Robot {team_id}'),
                'points': 0,
                'kills': 0,
                'deaths': 0,
                'ready': False,
                'addr': addr,
                'last_heartbeat': time.time(),
                'video_port': self.config['video_ports_start'] + team_id - 1
            }
            print(f"[GV] Team registered: {self.teams[team_id]['team_name']} (ID: {team_id})")
    
    def process_hit(self, hit_data: dict):
        """Process a hit report"""
        attacker_id = hit_data.get('attacking_team')
        defender_id = hit_data.get('defending_team')
        
        if attacker_id not in self.teams or defender_id not in self.teams:
            return
        
        # Award points to attacker
        self.teams[attacker_id]['points'] += self.config['points_per_hit']
        self.teams[attacker_id]['kills'] += 1
        
        # Record death for defender
        self.teams[defender_id]['deaths'] += 1
        
        # Add to hit log
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_entry = f"[{timestamp}] {self.teams[attacker_id]['team_name']} HIT {self.teams[defender_id]['team_name']}"
        self.hit_log.append(hit_data)
        
        self.hit_log_text.insert(tk.END, log_entry + "\n")
        self.hit_log_text.see(tk.END)
        
        # Send points update to both teams
        self.send_points_update(attacker_id)
        self.send_points_update(defender_id)
        
        print(f"[GV] Hit: Team {attacker_id} → Team {defender_id}")
    
    def send_points_update(self, team_id: int):
        """Send points update to a team"""
        if team_id not in self.teams:
            return
        
        team = self.teams[team_id]
        message = {
            'type': 'POINTS_UPDATE',
            'points': team['points'],
            'kills': team['kills'],
            'deaths': team['deaths']
        }
        
        try:
            self.sock.sendto(json.dumps(message).encode('utf-8'), team['addr'])
        except Exception as e:
            print(f"[GV] Failed to send points update: {e}")
    
    def send_ready_check(self):
        """Send ready check to all teams"""
        message = {'type': 'READY_CHECK'}
        self.broadcast_message(message)
        print("[GV] Sent ready check")
    
    def start_game(self):
        """Start the game"""
        # Check if any teams are connected
        if not self.teams:
            messagebox.showwarning("No Teams", "No teams are connected!")
            return
        
        # Check if teams are ready (optional)
        ready_teams = sum(1 for t in self.teams.values() if t['ready'])
        if ready_teams < len(self.teams):
            result = messagebox.askyesno("Not All Ready",
                                        f"Only {ready_teams}/{len(self.teams)} teams are ready. Start anyway?")
            if not result:
                return
        
        # Start game
        self.game_active = True
        self.game_start_time = time.time()
        self.game_time_remaining = self.config['game_duration']
        
        # Reset scores
        for team in self.teams.values():
            team['points'] = 0
            team['kills'] = 0
            team['deaths'] = 0
        
        # Clear hit log
        self.hit_log = []
        self.hit_log_text.delete(1.0, tk.END)
        
        # Send game start message WITH DURATION
        message = {
            'type': 'GAME_START',
            'duration': self.config['game_duration']
        }
        self.broadcast_message(message)
        
        # Update UI
        self.game_status_label.config(text="Status: GAME ACTIVE", fg='lime')
        self.start_game_btn.config(state=tk.DISABLED)
        self.end_game_btn.config(state=tk.NORMAL)
        self.ready_check_btn.config(state=tk.DISABLED)
        
        print(f"[GV] Game started! Duration: {self.config['game_duration']}s")
    
    def end_game(self):
        """End the game"""
        self.game_active = False
        
        # Send game end message
        message = {'type': 'GAME_END'}
        self.broadcast_message(message)
        
        # Update UI
        self.game_status_label.config(text="Status: Game Ended", fg='yellow')
        self.start_game_btn.config(state=tk.NORMAL)
        self.end_game_btn.config(state=tk.DISABLED)
        self.ready_check_btn.config(state=tk.NORMAL)
        
        # Show final results
        self.show_final_results()
        
        print("[GV] Game ended!")
    
    def show_final_results(self):
        """Show final results dialog"""
        results_window = tk.Toplevel(self.root)
        results_window.title("🏆 Final Results")
        results_window.geometry("500x400")
        results_window.configure(bg='#2d2d2d')
        
        tk.Label(results_window, text="🏆 FINAL RESULTS 🏆",
                font=('Arial', 18, 'bold'), bg='#2d2d2d', fg='gold').pack(pady=20)
        
        # Sort teams by points
        sorted_teams = sorted(self.teams.values(), key=lambda t: t['points'], reverse=True)
        
        results_text = scrolledtext.ScrolledText(results_window,
                                                font=('Courier', 11),
                                                bg='#1a1a1a', fg='white',
                                                height=15)
        results_text.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 20))
        
        for rank, team in enumerate(sorted_teams, 1):
            kd_ratio = team['kills'] / team['deaths'] if team['deaths'] > 0 else team['kills']
            line = f"{rank}. {team['team_name']:20s} {team['points']:4d} pts  K/D: {team['kills']}/{team['deaths']} ({kd_ratio:.2f})\n"
            results_text.insert(tk.END, line)
        
        results_text.config(state=tk.DISABLED)
    
    def broadcast_message(self, message: dict):
        """Broadcast message to all teams"""
        for team in self.teams.values():
            try:
                self.sock.sendto(json.dumps(message).encode('utf-8'), team['addr'])
            except Exception as e:
                print(f"[GV] Failed to send to team {team['team_id']}: {e}")
    
    def export_log(self):
        """Export game log to file"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"game_log_{timestamp}.json"
        
        log_data = {
            'timestamp': timestamp,
            'teams': self.teams,
            'hit_log': self.hit_log,
            'game_duration': self.config['game_duration']
        }
        
        try:
            with open(filename, 'w') as f:
                json.dump(log_data, f, indent=2)
            messagebox.showinfo("Export Success", f"Log exported to {filename}")
        except Exception as e:
            messagebox.showerror("Export Failed", f"Failed to export: {e}")
    
    def update_gui(self):
        """Update GUI periodically"""
        if not self.running:
            return
        
        current_time = time.time()
        
        # Update game timer
        if self.game_active:
            elapsed = current_time - self.game_start_time
            self.game_time_remaining = max(0, self.config['game_duration'] - elapsed)
            
            minutes = int(self.game_time_remaining // 60)
            seconds = int(self.game_time_remaining % 60)
            self.timer_label.config(text=f"Time: {minutes:02d}:{seconds:02d}")
            
            # Auto-end game when time runs out
            if self.game_time_remaining <= 0:
                self.end_game()
        
        # Update leaderboard
        self.leaderboard_tree.delete(*self.leaderboard_tree.get_children())
        
        sorted_teams = sorted(self.teams.values(), key=lambda t: t['points'], reverse=True)
        
        for rank, team in enumerate(sorted_teams, 1):
            kd_ratio = team['kills'] / team['deaths'] if team['deaths'] > 0 else team['kills']
            
            self.leaderboard_tree.insert('', tk.END, values=(
                rank,
                team['team_name'],
                team['points'],
                team['kills'],
                team['deaths'],
                f"{kd_ratio:.2f}"
            ))
        
        # Update teams info
        self.teams_text.delete(1.0, tk.END)
        
        for team in sorted_teams:
            last_seen = current_time - team['last_heartbeat']
            status = "🟢 ONLINE" if last_seen < 5 else "🔴 OFFLINE"
            ready_status = "✅" if team['ready'] else "⏳"
            
            info = f"{ready_status} Team {team['team_id']}: {team['team_name']}\n"
            info += f"   Robot: {team['robot_name']}\n"
            info += f"   Status: {status} ({last_seen:.1f}s)\n"
            info += f"   Video: Port {team['video_port']}\n"
            info += f"   Score: {team['points']} pts\n"
            info += f"   K/D: {team['kills']}/{team['deaths']}\n"
            info += "-" * 40 + "\n"
            
            self.teams_text.insert(tk.END, info)
        
        # Schedule next update
        self.root.after(100, self.update_gui)
    
    def open_camera_viewer(self):
        """Open 4-camera security monitor view"""
        import subprocess
        
        # Get team IDs to display (first 4 registered teams)
        team_ids = sorted(list(self.teams.keys()))[:4]
        
        if len(team_ids) == 0:
            messagebox.showinfo("No Cameras", "No robots connected yet.\nWait for robots to register first.")
            return
        
        # Create camera viewer window
        cam_window = tk.Toplevel(self.root)
        cam_window.title("📹 Security Camera Monitor - 4 Feeds")
        cam_window.geometry("1280x720")
        cam_window.configure(bg='#000000')
        
        # Title
        tk.Label(cam_window, text="📹 LIVE CAMERA FEEDS", font=('Arial', 20, 'bold'),
                bg='#000000', fg='#00ff00').pack(pady=10)
        
        # Create 2x2 grid for cameras
        grid_frame = tk.Frame(cam_window, bg='#000000')
        grid_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Configure grid to be 2x2
        grid_frame.grid_rowconfigure(0, weight=1)
        grid_frame.grid_rowconfigure(1, weight=1)
        grid_frame.grid_columnconfigure(0, weight=1)
        grid_frame.grid_columnconfigure(1, weight=1)
        
        # Launch GStreamer windows for each team
        gst_processes = []
        positions = [(0, 0), (0, 1), (1, 0), (1, 1)]
        
        for idx, (row, col) in enumerate(positions):
            frame = tk.Frame(grid_frame, bg='#1a1a1a', highlightbackground='#00ff00',
                            highlightthickness=2)
            frame.grid(row=row, column=col, sticky='nsew', padx=5, pady=5)
            
            if idx < len(team_ids):
                team_id = team_ids[idx]
                team = self.teams[team_id]
                video_port = team['video_port']
                
                # Team label
                tk.Label(frame, text=f"🤖 {team['team_name']} (ID: {team_id})",
                        font=('Arial', 14, 'bold'), bg='#1a1a1a', fg='#00ff00').pack(pady=5)
                
                # Stream info
                tk.Label(frame, text=f"UDP Port: {video_port}",
                        font=('Courier', 10), bg='#1a1a1a', fg='cyan').pack()
                
                # Launch GStreamer button
                def make_launch_func(port, name):
                    def launch():
                        # Use the working GStreamer command with proper RTP caps
                        cmd = [
                            'gst-launch-1.0', '-v',
                            f'udpsrc port={port}',
                            'caps=application/x-rtp,media=video,encoding-name=H264,payload=96,clock-rate=90000,packetization-mode=1',
                            '!', 'rtpjitterbuffer', 'latency=50',
                            '!', 'rtph264depay',
                            '!', 'h264parse',
                            '!', 'd3d11h264dec',
                            '!', 'autovideosink', 'sync=false'
                        ]
                        try:
                            proc = subprocess.Popen(cmd)
                            gst_processes.append(proc)
                            print(f"[Camera] Launched viewer for {name} on port {port}")
                        except Exception as e:
                            messagebox.showerror("GStreamer Error",
                                               f"Failed to launch camera viewer:\n{e}\n\n" +
                                               "Make sure GStreamer is installed.")
                    return launch
                
                btn = tk.Button(frame, text="▶️ Open Camera Feed",
                               command=make_launch_func(video_port, team['team_name']),
                               bg='#4CAF50', fg='white', font=('Arial', 11), width=20, height=2)
                btn.pack(pady=10)
                
                # Status indicator
                status = "🟢 Online" if team['last_heartbeat'] > time.time() - 5 else "🔴 Offline"
                tk.Label(frame, text=status, font=('Arial', 10), bg='#1a1a1a', fg='white').pack(pady=5)
            else:
                # Empty slot
                tk.Label(frame, text="No Robot", font=('Arial', 14), bg='#1a1a1a', fg='#666666').pack(expand=True)
        
        # Cleanup function
        def on_close():
            for proc in gst_processes:
                try:
                    proc.terminate()
                except:
                    pass
            cam_window.destroy()
        
        cam_window.protocol("WM_DELETE_WINDOW", on_close)
    
    def open_settings(self):
        """Open settings dialog"""
        dialog = tk.Toplevel(self.root)
        dialog.title("⚙️ Game Viewer Settings")
        dialog.geometry("400x300")
        dialog.configure(bg='#2a2a2a')
        dialog.transient(self.root)
        dialog.grab_set()
        
        # Main frame
        main_frame = tk.Frame(dialog, bg='#2a2a2a')
        main_frame.pack(fill='both', expand=True, padx=20, pady=20)
        
        # Title
        tk.Label(main_frame, text="Game Configuration",
                font=('Arial', 14, 'bold'), bg='#2a2a2a', fg='white').pack(pady=10)
        
        # Game Duration
        duration_frame = tk.Frame(main_frame, bg='#2a2a2a')
        duration_frame.pack(fill='x', pady=10)
        
        tk.Label(duration_frame, text="Game Duration (seconds):",
                font=('Arial', 11), bg='#2a2a2a', fg='white').pack(side='left')
        
        duration_var = tk.StringVar(value=str(self.config['game_duration']))
        duration_entry = tk.Entry(duration_frame, textvariable=duration_var,
                                 font=('Arial', 11), width=10,
                                 bg='#3a3a3a', fg='white', insertbackground='white')
        duration_entry.pack(side='left', padx=10)
        
        tk.Label(duration_frame, text=f"({self.config['game_duration']//60} min {self.config['game_duration']%60} sec)",
                font=('Arial', 9), bg='#2a2a2a', fg='#888888').pack(side='left')
        
        # Points per hit
        points_frame = tk.Frame(main_frame, bg='#2a2a2a')
        points_frame.pack(fill='x', pady=10)
        
        tk.Label(points_frame, text="Points per Hit:",
                font=('Arial', 11), bg='#2a2a2a', fg='white').pack(side='left')
        
        points_var = tk.StringVar(value=str(self.config['points_per_hit']))
        points_entry = tk.Entry(points_frame, textvariable=points_var,
                               font=('Arial', 11), width=10,
                               bg='#3a3a3a', fg='white', insertbackground='white')
        points_entry.pack(side='left', padx=10)
        
        # Max teams
        teams_frame = tk.Frame(main_frame, bg='#2a2a2a')
        teams_frame.pack(fill='x', pady=10)
        
        tk.Label(teams_frame, text="Max Teams:",
                font=('Arial', 11), bg='#2a2a2a', fg='white').pack(side='left')
        
        teams_var = tk.StringVar(value=str(self.config['max_teams']))
        teams_entry = tk.Entry(teams_frame, textvariable=teams_var,
                              font=('Arial', 11), width=10,
                              bg='#3a3a3a', fg='white', insertbackground='white')
        teams_entry.pack(side='left', padx=10)
        
        # Save button
        def save_settings():
            try:
                self.config['game_duration'] = int(duration_var.get())
                self.config['points_per_hit'] = int(points_var.get())
                self.config['max_teams'] = int(teams_var.get())
                self.save_config()
                messagebox.showinfo("Success", "Settings saved successfully!")
                dialog.destroy()
            except ValueError:
                messagebox.showerror("Error", "Please enter valid numbers")
        
        btn_frame = tk.Frame(main_frame, bg='#2a2a2a')
        btn_frame.pack(pady=20)
        
        tk.Button(btn_frame, text="💾 Save", command=save_settings,
                 font=('Arial', 11, 'bold'), bg='#4CAF50', fg='white',
                 width=12, height=2).pack(side='left', padx=5)
        
        tk.Button(btn_frame, text="✗ Cancel", command=dialog.destroy,
                 font=('Arial', 11, 'bold'), bg='#f44336', fg='white',
                 width=12, height=2).pack(side='left', padx=5)
    
    def on_closing(self):
        """Clean up on close"""
        self.running = False
        
        # End game if active
        if self.game_active:
            self.end_game()
        
        # Close socket
        self.sock.close()
        
        # Save config
        self.save_config()
        
        # Destroy window
        self.root.destroy()
    
    def run(self):
        """Start application"""
        self.root.mainloop()


def main():
    """Entry point"""
    print("=" * 60)
    print("🎯 LASER TAG TOURNAMENT - GAME VIEWER")
    print("=" * 60)
    
    try:
        import os
        gv = GameViewer()
        gv.run()
    
    except KeyboardInterrupt:
        print("\n[GV] Shutdown")
    
    except Exception as e:
        print(f"\n[GV] Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
