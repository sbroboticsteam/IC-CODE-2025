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
    "referee_port": 6700,  # Port for referee web interface
    "max_teams": 8,
    "game_duration": 120,  # 2 minutes (configurable)
    "points_per_hit": 10,  # IR hit points (One Shot, One Kill)
    "points_tesseract_retrieval": 15,  # First capture of Tesseract
    "points_tesseract_steal": 20,  # Stealing from another Safe Zone
    "points_tesseract_possession": 30,  # Tesseract in Safe Zone at end
    "robot_disable_duration": 10,  # Seconds robot is disabled after hit
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
        self.game_ended_time = 0  # Track when game ended
        
        # Disabled robots tracking (team_id -> disable_end_time)
        self.disabled_robots: Dict[int, float] = {}
        
        # Network
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)  # Enable broadcasting
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
        
        # Start heartbeat sender
        self.start_heartbeat_thread()
        
        # Start discovery broadcaster
        self.start_discovery_thread()
        
        # Send immediate discovery broadcast to find existing robots
        self.root.after(1000, self.send_immediate_discovery)  # Wait 1 second for startup
        
        # Start referee web server
        self.start_referee_server()
        
        # Start update loop
        self.update_gui()
        
        # Cleanup handler
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
    
    def load_config(self):
        """Load configuration and merge with defaults"""
        config = GV_CONFIG.copy()
        
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r') as f:
                    loaded = json.load(f)
                    # Merge loaded config with defaults (defaults get overwritten)
                    config.update(loaded)
            except Exception as e:
                print(f"[GV] Error loading config: {e}")
        
        return config
    
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
    
    def start_discovery_thread(self):
        """Start discovery broadcaster thread"""
        thread = threading.Thread(target=self.discovery_loop, daemon=True)
        thread.start()
        print("[GV] Discovery thread started")
    
    def discovery_loop(self):
        """Send periodic discovery broadcasts to find existing robots"""
        while self.running:
            try:
                # Broadcast discovery message to common subnet
                discovery_message = {
                    'type': 'DISCOVERY',
                    'gv_ip': self.config['gv_ip'],
                    'gv_port': self.config['gv_port'],
                    'timestamp': time.time()
                }
                
                # Send to broadcast address and common robot IPs
                broadcast_addresses = [
                    ('255.255.255.255', 6100),  # Subnet broadcast
                    ('192.168.50.255', 6100),   # Common robot subnet
                ]
                
                # Also try specific robot IPs if we know any teams
                for team_id in range(1, 9):  # Try team IDs 1-8
                    robot_ip = f"192.168.50.{140 + team_id}"  # Common robot IP pattern
                    laptop_ip = f"192.168.50.{60 + team_id}"   # Common laptop IP pattern
                    
                    broadcast_addresses.extend([
                        (robot_ip, 6100),
                        (laptop_ip, 6100),
                        (robot_ip, 6000 + team_id),  # Dynamic ports
                        (laptop_ip, 6000 + team_id)
                    ])
                
                data = json.dumps(discovery_message).encode('utf-8')
                
                for addr in broadcast_addresses:
                    try:
                        self.sock.sendto(data, addr)
                    except Exception:
                        # Ignore individual send failures
                        pass
                
                print("[GV] Discovery broadcast sent")
                
                # Send discovery every 15 seconds (less frequent than heartbeat)
                time.sleep(15.0)
                
            except Exception as e:
                if self.running:
                    print(f"[GV] Discovery error: {e}")
                time.sleep(15.0)
    
    def send_immediate_discovery(self):
        """Send immediate discovery broadcast on startup"""
        try:
            discovery_message = {
                'type': 'DISCOVERY',
                'gv_ip': self.config['gv_ip'],
                'gv_port': self.config['gv_port'],
                'timestamp': time.time()
            }
            
            # Send to broadcast address and common robot IPs
            broadcast_addresses = [
                ('255.255.255.255', 6100),  # Subnet broadcast
                ('192.168.50.255', 6100),   # Common robot subnet
            ]
            
            # Try specific robot IPs
            for team_id in range(1, 9):  # Try team IDs 1-8
                robot_ip = f"192.168.50.{140 + team_id}"
                laptop_ip = f"192.168.50.{60 + team_id}"
                
                broadcast_addresses.extend([
                    (robot_ip, 6100),
                    (laptop_ip, 6100),
                    (robot_ip, 6000 + team_id),
                    (laptop_ip, 6000 + team_id)
                ])
            
            data = json.dumps(discovery_message).encode('utf-8')
            
            for addr in broadcast_addresses:
                try:
                    self.sock.sendto(data, addr)
                except Exception:
                    pass
            
            print("[GV] Immediate discovery broadcast sent - looking for existing robots")
            
        except Exception as e:
            print(f"[GV] Immediate discovery error: {e}")
    
    def start_heartbeat_thread(self):
        """Start heartbeat sender thread"""
        thread = threading.Thread(target=self.heartbeat_loop, daemon=True)
        thread.start()
        print("[GV] Heartbeat thread started")
    
    def heartbeat_loop(self):
        """Send periodic heartbeats to all connected laptops"""
        while self.running:
            try:
                # Send heartbeat to all teams
                for team_id in list(self.teams.keys()):
                    self.send_to_team(team_id, {'type': 'HEARTBEAT', 'timestamp': time.time()})
                
                time.sleep(1.0)  # Send every 1 second
            except Exception as e:
                if self.running:
                    print(f"[GV] Heartbeat error: {e}")
    
    def start_referee_server(self):
        """Start HTTP server for referee interface"""
        from http.server import HTTPServer, BaseHTTPRequestHandler
        import urllib.parse
        
        game_viewer = self
        
        class RefereeHandler(BaseHTTPRequestHandler):
            def log_message(self, format, *args):
                pass  # Suppress default logging
            
            def do_GET(self):
                """Serve referee web interface"""
                if self.path == '/' or self.path == '/index.html':
                    self.send_response(200)
                    self.send_header('Content-type', 'text/html')
                    self.end_headers()
                    
                    html = self.generate_referee_page()
                    self.wfile.write(html.encode('utf-8'))
                
                elif self.path == '/api/teams':
                    # API to get team data
                    self.send_response(200)
                    self.send_header('Content-type', 'application/json')
                    self.send_header('Access-Control-Allow-Origin', '*')
                    self.end_headers()
                    
                    teams_data = {
                        'teams': {tid: {
                            'team_id': t['team_id'],
                            'team_name': t['team_name'],
                            'points': t['points'],
                            'kills': t['kills'],
                            'deaths': t['deaths']
                        } for tid, t in game_viewer.teams.items()},
                        'game_active': game_viewer.game_active,
                        'can_award_points': game_viewer.game_active or (
                            hasattr(game_viewer, 'game_ended_time') and 
                            game_viewer.game_ended_time > 0 and 
                            time.time() - game_viewer.game_ended_time < 300  # 5 min grace period
                        )
                    }
                    self.wfile.write(json.dumps(teams_data).encode('utf-8'))
                
                else:
                    self.send_response(404)
                    self.end_headers()
            
            def do_POST(self):
                """Handle point awards from referee"""
                if self.path == '/api/award_points':
                    content_length = int(self.headers['Content-Length'])
                    post_data = self.rfile.read(content_length)
                    data = json.loads(post_data.decode('utf-8'))
                    
                    team_id = data.get('team_id')
                    category = data.get('category')
                    
                    if team_id in game_viewer.teams:
                        # Award points based on category
                        if category == 'tesseract_retrieval':
                            points = game_viewer.config['points_tesseract_retrieval']
                            game_viewer.teams[team_id]['points'] += points
                            log_msg = f"Tesseract Retrieval: +{points} pts"
                        elif category == 'tesseract_steal':
                            points = game_viewer.config['points_tesseract_steal']
                            game_viewer.teams[team_id]['points'] += points
                            log_msg = f"Tesseract Steal: +{points} pts"
                        elif category == 'tesseract_possession':
                            points = game_viewer.config['points_tesseract_possession']
                            game_viewer.teams[team_id]['points'] += points
                            log_msg = f"Tesseract Possession Bonus: +{points} pts"
                        else:
                            self.send_response(400)
                            self.end_headers()
                            return
                        
                        # Log the award
                        timestamp = datetime.now().strftime("%H:%M:%S")
                        log_entry = f"[{timestamp}] REFEREE: {game_viewer.teams[team_id]['team_name']} - {log_msg}"
                        game_viewer.hit_log_text.insert(tk.END, log_entry + "\n")
                        game_viewer.hit_log_text.see(tk.END)
                        
                        # Send points update to team
                        game_viewer.send_points_update(team_id)
                        
                        print(f"[Referee] {log_entry}")
                        
                        self.send_response(200)
                        self.send_header('Content-type', 'application/json')
                        self.end_headers()
                        self.wfile.write(json.dumps({'success': True}).encode('utf-8'))
                    else:
                        self.send_response(404)
                        self.end_headers()
                else:
                    self.send_response(404)
                    self.end_headers()
            
            def generate_referee_page(self):
                """Generate mobile-friendly referee interface"""
                return '''<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>Referee Control Panel</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif;
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            color: white;
            min-height: 100vh;
            padding: 10px;
        }
        .header {
            background: rgba(0,255,0,0.1);
            padding: 15px;
            border-radius: 10px;
            margin-bottom: 20px;
            text-align: center;
            border: 2px solid #00ff00;
        }
        .header h1 { font-size: 24px; color: #00ff00; margin-bottom: 5px; }
        .status { font-size: 14px; color: #ffd700; margin-top: 5px; }
        .teams-grid {
            display: grid;
            grid-template-columns: 1fr;
            gap: 15px;
            margin-bottom: 20px;
        }
        .team-card {
            background: rgba(255,255,255,0.05);
            border-radius: 12px;
            padding: 15px;
            border: 2px solid rgba(0,255,0,0.3);
            transition: all 0.3s;
        }
        .team-card.selected {
            border-color: #00ff00;
            background: rgba(0,255,0,0.15);
            transform: scale(1.02);
        }
        .team-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 10px;
        }
        .team-name { font-size: 18px; font-weight: bold; color: #00ff00; }
        .team-points { font-size: 24px; font-weight: bold; color: #ffd700; }
        .team-stats {
            font-size: 12px;
            color: #aaa;
            margin-top: 5px;
        }
        .action-buttons {
            display: none;
            grid-template-columns: 1fr;
            gap: 10px;
            margin-top: 15px;
            padding-top: 15px;
            border-top: 1px solid rgba(255,255,255,0.1);
        }
        .team-card.selected .action-buttons { display: grid; }
        .btn {
            padding: 15px;
            border: none;
            border-radius: 8px;
            font-size: 16px;
            font-weight: bold;
            cursor: pointer;
            transition: all 0.2s;
            text-align: center;
        }
        .btn:active { transform: scale(0.95); }
        .btn-retrieval {
            background: linear-gradient(135deg, #4CAF50 0%, #45a049 100%);
            color: white;
        }
        .btn-steal {
            background: linear-gradient(135deg, #FF9800 0%, #F57C00 100%);
            color: white;
        }
        .btn-possession {
            background: linear-gradient(135deg, #2196F3 0%, #1976D2 100%);
            color: white;
        }
        .refresh-btn {
            width: 100%;
            padding: 15px;
            background: rgba(0,255,0,0.2);
            color: #00ff00;
            border: 2px solid #00ff00;
            border-radius: 10px;
            font-size: 16px;
            font-weight: bold;
            cursor: pointer;
            margin-bottom: 10px;
        }
        .notification {
            position: fixed;
            top: 20px;
            left: 50%;
            transform: translateX(-50%);
            background: rgba(0,255,0,0.95);
            color: black;
            padding: 15px 30px;
            border-radius: 10px;
            font-weight: bold;
            display: none;
            z-index: 1000;
            box-shadow: 0 4px 20px rgba(0,255,0,0.5);
        }
        .offline {
            background: rgba(255,0,0,0.2);
            border: 2px solid #ff0000;
            padding: 15px;
            border-radius: 10px;
            text-align: center;
            color: #ff0000;
            margin-bottom: 20px;
        }
    </style>
</head>
<body>
    <div id="notification" class="notification"></div>
    
    <div class="header">
        <h1>🎯 REFEREE CONTROL PANEL</h1>
        <div class="status" id="status">Loading...</div>
    </div>
    
    <div id="offline-notice" class="offline" style="display: none;">
        ⚠️ Point awarding is disabled<br>
        <small>Game must be active or recently ended</small>
    </div>
    
    <button class="refresh-btn" onclick="loadTeams()">🔄 Refresh Teams</button>
    
    <div class="teams-grid" id="teams-grid">
        <div style="text-align: center; padding: 40px; color: #666;">
            Loading teams...
        </div>
    </div>
    
    <script>
        let selectedTeam = null;
        let canAwardPoints = false;
        
        function loadTeams() {
            fetch('/api/teams')
                .then(r => r.json())
                .then(data => {
                    canAwardPoints = data.can_award_points;
                    const grid = document.getElementById('teams-grid');
                    const status = document.getElementById('status');
                    const offlineNotice = document.getElementById('offline-notice');
                    
                    if (data.game_active) {
                        status.textContent = '🟢 GAME ACTIVE';
                        status.style.color = '#00ff00';
                    } else {
                        status.textContent = '⏸️ Game Not Active';
                        status.style.color = '#ffd700';
                    }
                    
                    offlineNotice.style.display = canAwardPoints ? 'none' : 'block';
                    
                    if (Object.keys(data.teams).length === 0) {
                        grid.innerHTML = '<div style="text-align: center; padding: 40px; color: #666;">No teams connected</div>';
                        return;
                    }
                    
                    grid.innerHTML = '';
                    for (const [tid, team] of Object.entries(data.teams)) {
                        const card = document.createElement('div');
                        card.className = 'team-card';
                        card.onclick = () => selectTeam(tid);
                        
                        card.innerHTML = `
                            <div class="team-header">
                                <div class="team-name">Team ${tid}: ${team.team_name}</div>
                                <div class="team-points">${team.points} pts</div>
                            </div>
                            <div class="team-stats">K: ${team.kills} | D: ${team.deaths}</div>
                            <div class="action-buttons">
                                <button class="btn btn-retrieval" onclick="awardPoints(${tid}, 'tesseract_retrieval', event)">
                                    📦 Tesseract Retrieval<br><small>+15 points</small>
                                </button>
                                <button class="btn btn-steal" onclick="awardPoints(${tid}, 'tesseract_steal', event)">
                                    🎯 Tesseract Steal<br><small>+20 points</small>
                                </button>
                                <button class="btn btn-possession" onclick="awardPoints(${tid}, 'tesseract_possession', event)">
                                    👑 Possession Bonus<br><small>+30 points</small>
                                </button>
                            </div>
                        `;
                        grid.appendChild(card);
                    }
                })
                .catch(err => {
                    console.error('Error loading teams:', err);
                    document.getElementById('status').textContent = '❌ Connection Error';
                });
        }
        
        function selectTeam(tid) {
            if (!canAwardPoints) return;
            
            const cards = document.querySelectorAll('.team-card');
            cards.forEach(card => card.classList.remove('selected'));
            event.currentTarget.classList.add('selected');
            selectedTeam = tid;
        }
        
        function awardPoints(teamId, category, event) {
            event.stopPropagation();
            
            if (!canAwardPoints) {
                showNotification('⚠️ Point awarding disabled');
                return;
            }
            
            fetch('/api/award_points', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({team_id: parseInt(teamId), category: category})
            })
            .then(r => r.json())
            .then(data => {
                if (data.success) {
                    const names = {
                        'tesseract_retrieval': 'Tesseract Retrieval',
                        'tesseract_steal': 'Tesseract Steal',
                        'tesseract_possession': 'Possession Bonus'
                    };
                    showNotification(`✅ ${names[category]} awarded!`);
                    setTimeout(() => loadTeams(), 500);
                }
            })
            .catch(err => {
                console.error('Error awarding points:', err);
                showNotification('❌ Failed to award points');
            });
        }
        
        function showNotification(message) {
            const notif = document.getElementById('notification');
            notif.textContent = message;
            notif.style.display = 'block';
            setTimeout(() => {
                notif.style.display = 'none';
            }, 2000);
        }
        
        // Auto-refresh every 2 seconds
        setInterval(loadTeams, 2000);
        loadTeams();
    </script>
</body>
</html>'''
        
        def run_server():
            try:
                server = HTTPServer(('0.0.0.0', game_viewer.config['referee_port']), RefereeHandler)
                server.timeout = 0.5  # Short timeout to allow checking game_viewer.running
                print(f"[Referee] Web interface started on port {game_viewer.config['referee_port']}")
                print(f"[Referee] Access at: http://192.168.50.87:{game_viewer.config['referee_port']}")
                
                # Serve forever with periodic checks
                server.serve_forever()
            except Exception as e:
                print(f"[Referee] Server error: {e}")
            finally:
                try:
                    server.shutdown()
                    server.server_close()
                except:
                    pass
        
        thread = threading.Thread(target=run_server, daemon=True)
        thread.start()
    
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
            listen_port = message.get('listen_port')
            self.register_team(team_id, message, addr, listen_port)
            # Send acknowledgment back to laptop
            self.send_to_team(team_id, {'type': 'REGISTER_ACK', 'status': 'connected'})
        
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
        
        elif msg_type == 'DISCOVERY_RESPONSE':
            # Robot responding to discovery broadcast
            listen_port = message.get('listen_port')
            self.register_team(team_id, message, addr, listen_port)
            # Send acknowledgment back to laptop
            self.send_to_team(team_id, {'type': 'REGISTER_ACK', 'status': 'connected'})
    
    def register_team(self, team_id: int, message: dict, addr: tuple, listen_port: int):
        """Register a new team"""
        if team_id not in self.teams:
            # New team - create entry
            self.teams[team_id] = {
                'team_id': team_id,
                'team_name': message.get('team_name', f'Team {team_id}'),
                'robot_name': message.get('robot_name', f'Robot {team_id}'),
                'points': 0,
                'kills': 0,
                'deaths': 0,
                'ready': False,
                'addr': addr,
                'laptop_ip': addr[0],  # Store laptop IP separately
                'listen_port': listen_port,  # Store laptop's listen port
                'last_heartbeat': time.time(),
                'video_port': self.config['video_ports_start'] + team_id - 1
            }
            print(f"[GV] ✅ New team registered: {self.teams[team_id]['team_name']} (ID: {team_id}) on port {listen_port}")
        else:
            # Team already exists - update laptop connection info
            if listen_port is not None:
                self.teams[team_id]['laptop_ip'] = addr[0]
                self.teams[team_id]['listen_port'] = listen_port
                self.teams[team_id]['last_heartbeat'] = time.time()
                print(f"[GV] 🔄 Team {team_id} reconnected: {addr[0]}:{listen_port}")
    
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
        
        # Mark defender as disabled for configured duration
        disable_until = time.time() + self.config['robot_disable_duration']
        self.disabled_robots[defender_id] = disable_until
        
        # Notify defender they are disabled
        disable_message = {
            'type': 'ROBOT_DISABLED',
            'disabled_by': self.teams[attacker_id]['team_name'],
            'disabled_by_id': attacker_id,
            'duration': self.config['robot_disable_duration'],
            'disabled_until': disable_until
        }
        self.send_to_team(defender_id, disable_message)
        
        # Add to hit log with timestamp
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_entry = f"[{timestamp}] {self.teams[attacker_id]['team_name']} HIT {self.teams[defender_id]['team_name']} (Disabled for {self.config['robot_disable_duration']}s)"
        
        # Store hit with timestamp
        hit_data['timestamp'] = timestamp
        self.hit_log.append(hit_data)
        
        self.hit_log_text.insert(tk.END, log_entry + "\n")
        self.hit_log_text.see(tk.END)
        
        # Send points update to both teams
        self.send_points_update(attacker_id)
        self.send_points_update(defender_id)
        
        print(f"[GV] Hit: Team {attacker_id} → Team {defender_id} (disabled until {disable_until})")
    
    def send_to_team(self, team_id: int, message: dict):
        """Send message to a specific team's laptop"""
        if team_id not in self.teams:
            return
        
        team = self.teams[team_id]
        if 'listen_port' not in team or team['listen_port'] is None:
            return
        if 'laptop_ip' not in team or team['laptop_ip'] is None:
            return
        
        try:
            data = json.dumps(message).encode('utf-8')
            # Send to laptop's IP and listen port
            laptop_addr = (team['laptop_ip'], team['listen_port'])
            self.sock.sendto(data, laptop_addr)
        except Exception as e:
            print(f"[GV] Failed to send to team {team_id}: {e}")
    
    def send_points_update(self, team_id: int):
        """Send points update to a team's laptop"""
        if team_id not in self.teams:
            return
        
        team = self.teams[team_id]
        message = {
            'type': 'POINTS_UPDATE',
            'points': team['points'],
            'kills': team['kills'],
            'deaths': team['deaths']
        }
        
        # Send to laptop using send_to_team
        self.send_to_team(team_id, message)
    
    def send_ready_check(self):
        """Send ready check to all teams"""
        message = {'type': 'READY_CHECK'}
        self.broadcast_message(message)
        print("[GV] Sent ready check")
    
    def start_game(self):
        """Start the game with team selection"""
        # Check if any teams are connected
        if not self.teams:
            messagebox.showwarning("No Teams", "No teams are connected!")
            return
        
        # Open team selection dialog
        self.open_team_selection_dialog()
    
    def open_team_selection_dialog(self):
        """Open dialog to select teams for the match"""
        selection_dialog = tk.Toplevel(self.root)
        selection_dialog.title("🎮 Select Teams for Match")
        selection_dialog.geometry("500x500")
        selection_dialog.configure(bg='#2a2a2a')
        selection_dialog.transient(self.root)
        selection_dialog.grab_set()
        
        # Title
        tk.Label(selection_dialog, text="Select Teams for Match (1-4 teams)",
                font=('Arial', 16, 'bold'), bg='#2a2a2a', fg='#00ff00').pack(pady=15)
        
        tk.Label(selection_dialog, text="Select which teams will participate in this round:",
                font=('Arial', 11), bg='#2a2a2a', fg='white').pack(pady=5)
        
        # Scrollable frame for team checkboxes
        canvas = tk.Canvas(selection_dialog, bg='#2a2a2a', highlightthickness=0, height=250)
        scrollbar = tk.Scrollbar(selection_dialog, orient="vertical", command=canvas.yview)
        scrollable_frame = tk.Frame(canvas, bg='#2a2a2a')
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=20, pady=10)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y, pady=10)
        
        # Create checkboxes for each team
        team_vars = {}
        sorted_teams = sorted(self.teams.items(), key=lambda x: x[0])
        
        for team_id, team in sorted_teams:
            frame = tk.Frame(scrollable_frame, bg='#3a3a3a', relief=tk.RAISED, borderwidth=1)
            frame.pack(fill=tk.X, pady=3, padx=5)
            
            var = tk.BooleanVar(value=False)
            team_vars[team_id] = var
            
            ready_icon = "✅" if team['ready'] else "⏳"
            status = "🟢" if time.time() - team['last_heartbeat'] < 5 else "🔴"
            
            cb = tk.Checkbutton(
                frame,
                text=f"{ready_icon} {status} Team {team_id}: {team['team_name']} ({team['robot_name']})",
                variable=var,
                font=('Arial', 11),
                bg='#3a3a3a',
                fg='white',
                selectcolor='#2a2a2a',
                activebackground='#3a3a3a',
                activeforeground='white'
            )
            cb.pack(anchor=tk.W, padx=10, pady=5)
        
        # Error label
        error_label = tk.Label(selection_dialog, text="",
                              font=('Arial', 10), bg='#2a2a2a', fg='red')
        error_label.pack(pady=5)
        
        # Match name entry
        name_frame = tk.Frame(selection_dialog, bg='#2a2a2a')
        name_frame.pack(pady=10)
        
        tk.Label(name_frame, text="Match Name (optional):",
                font=('Arial', 11), bg='#2a2a2a', fg='white').pack(side=tk.LEFT, padx=5)
        
        match_name_var = tk.StringVar(value=f"match_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
        match_name_entry = tk.Entry(name_frame, textvariable=match_name_var,
                                    font=('Arial', 11), width=30,
                                    bg='#3a3a3a', fg='white', insertbackground='white')
        match_name_entry.pack(side=tk.LEFT, padx=5)
        
        # Buttons
        btn_frame = tk.Frame(selection_dialog, bg='#2a2a2a')
        btn_frame.pack(pady=15)
        
        def start_selected_game():
            # Get selected teams
            selected_teams = [tid for tid, var in team_vars.items() if var.get()]
            
            if len(selected_teams) == 0:
                error_label.config(text="❌ Please select at least 1 team!")
                return
            
            if len(selected_teams) > 4:
                error_label.config(text="❌ Maximum 4 teams allowed!")
                return
            
            # Store match name for later
            self.current_match_name = match_name_var.get().strip()
            if not self.current_match_name:
                self.current_match_name = f"match_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            
            # Store participating teams
            self.participating_teams = selected_teams
            
            # Close dialog
            selection_dialog.destroy()
            
            # Start game with selected teams
            self.start_game_with_teams(selected_teams)
        
        tk.Button(btn_frame, text="▶️ Start Match", command=start_selected_game,
                 font=('Arial', 12, 'bold'), bg='#4CAF50', fg='white',
                 width=15, height=2).pack(side=tk.LEFT, padx=5)
        
        tk.Button(btn_frame, text="✗ Cancel", command=selection_dialog.destroy,
                 font=('Arial', 12, 'bold'), bg='#f44336', fg='white',
                 width=12, height=2).pack(side=tk.LEFT, padx=5)
    
    def start_game_with_teams(self, selected_team_ids):
        """Start the game with specific teams"""
        # Check if teams are ready (optional)
        ready_teams = sum(1 for tid in selected_team_ids if self.teams[tid]['ready'])
        if ready_teams < len(selected_team_ids):
            result = messagebox.askyesno("Not All Ready",
                                        f"Only {ready_teams}/{len(selected_team_ids)} selected teams are ready. Start anyway?")
            if not result:
                return
        
        # Start game
        self.game_active = True
        self.game_start_time = time.time()
        self.game_time_remaining = self.config['game_duration']
        self.game_ended_time = 0  # Reset game ended time
        
        # Clear disabled robots
        self.disabled_robots.clear()
        
        # Reset scores ONLY for participating teams
        for team_id in selected_team_ids:
            self.teams[team_id]['points'] = 0
            self.teams[team_id]['kills'] = 0
            self.teams[team_id]['deaths'] = 0
        
        # Clear hit log
        self.hit_log = []
        self.hit_log_text.delete(1.0, tk.END)
        
        # Send game start message WITH DURATION to participating teams only
        message = {
            'type': 'GAME_START',
            'duration': self.config['game_duration']
        }
        for team_id in selected_team_ids:
            self.send_to_team(team_id, message)
        
        # Update UI
        team_names = ", ".join([self.teams[tid]['team_name'] for tid in selected_team_ids])
        self.game_status_label.config(text=f"Status: GAME ACTIVE\n({len(selected_team_ids)} teams)", fg='lime')
        self.start_game_btn.config(state=tk.DISABLED)
        self.end_game_btn.config(state=tk.NORMAL)
        self.ready_check_btn.config(state=tk.DISABLED)
        
        print(f"[GV] Game started with teams: {selected_team_ids}")
        print(f"[GV] Duration: {self.config['game_duration']}s")
        print(f"[GV] Match name: {self.current_match_name}")
    
    def end_game(self):
        """End the game and save results"""
        self.game_active = False
        self.game_ended_time = time.time()  # Track when game ended for referee grace period
        
        # Send game end message to participating teams
        message = {'type': 'GAME_END'}
        if hasattr(self, 'participating_teams'):
            for team_id in self.participating_teams:
                self.send_to_team(team_id, message)
        else:
            self.broadcast_message(message)
        
        # Update UI
        self.game_status_label.config(text="Status: Game Ended", fg='yellow')
        self.start_game_btn.config(state=tk.NORMAL)
        self.end_game_btn.config(state=tk.DISABLED)
        self.ready_check_btn.config(state=tk.NORMAL)
        
        # Save results to file
        self.save_match_results()
        
        # Show final results
        self.show_final_results()
        
        print("[GV] Game ended!")
    
    def save_match_results(self):
        """Save match results to a text file"""
        if not hasattr(self, 'current_match_name'):
            self.current_match_name = f"match_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        if not hasattr(self, 'participating_teams'):
            self.participating_teams = list(self.teams.keys())
        
        # Ask for custom filename
        filename_dialog = tk.Toplevel(self.root)
        filename_dialog.title("💾 Save Match Results")
        filename_dialog.geometry("500x200")
        filename_dialog.configure(bg='#2a2a2a')
        filename_dialog.transient(self.root)
        filename_dialog.grab_set()
        
        tk.Label(filename_dialog, text="Save Match Results",
                font=('Arial', 16, 'bold'), bg='#2a2a2a', fg='#00ff00').pack(pady=15)
        
        tk.Label(filename_dialog, text="Enter filename for results:",
                font=('Arial', 11), bg='#2a2a2a', fg='white').pack(pady=5)
        
        name_frame = tk.Frame(filename_dialog, bg='#2a2a2a')
        name_frame.pack(pady=10)
        
        filename_var = tk.StringVar(value=self.current_match_name)
        filename_entry = tk.Entry(name_frame, textvariable=filename_var,
                                  font=('Arial', 12), width=35,
                                  bg='#3a3a3a', fg='white', insertbackground='white')
        filename_entry.pack(side=tk.LEFT, padx=5)
        
        tk.Label(name_frame, text=".txt",
                font=('Arial', 12), bg='#2a2a2a', fg='white').pack(side=tk.LEFT)
        
        def save_file():
            filename = filename_var.get().strip()
            if not filename:
                messagebox.showwarning("No Filename", "Please enter a filename!")
                return
            
            if not filename.endswith('.txt'):
                filename += '.txt'
            
            try:
                # Sort participating teams by points
                sorted_teams = sorted(
                    [(tid, self.teams[tid]) for tid in self.participating_teams],
                    key=lambda x: x[1]['points'],
                    reverse=True
                )
                
                # Create results content
                content = "=" * 60 + "\n"
                content += "🏆 LASER TAG MATCH RESULTS\n"
                content += "=" * 60 + "\n\n"
                content += f"Match Name: {self.current_match_name}\n"
                content += f"Date/Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                content += f"Duration: {self.config['game_duration']} seconds\n"
                content += f"Participating Teams: {len(self.participating_teams)}\n"
                content += "\n" + "=" * 60 + "\n"
                content += "FINAL STANDINGS\n"
                content += "=" * 60 + "\n\n"
                
                for rank, (team_id, team) in enumerate(sorted_teams, 1):
                    kd_ratio = team['kills'] / team['deaths'] if team['deaths'] > 0 else team['kills']
                    content += f"Rank {rank}: Team {team_id} - {team['team_name']}\n"
                    content += f"  Robot: {team['robot_name']}\n"
                    content += f"  Points: {team['points']}\n"
                    content += f"  Kills: {team['kills']}\n"
                    content += f"  Deaths: {team['deaths']}\n"
                    content += f"  K/D Ratio: {kd_ratio:.2f}\n"
                    content += "\n"
                
                content += "=" * 60 + "\n"
                content += "MATCH STATISTICS\n"
                content += "=" * 60 + "\n\n"
                
                total_points = sum(team['points'] for _, team in sorted_teams)
                total_kills = sum(team['kills'] for _, team in sorted_teams)
                
                content += f"Total Points Scored: {total_points}\n"
                content += f"Total Eliminations: {total_kills}\n"
                content += f"Total Hit Events: {len(self.hit_log)}\n"
                
                if sorted_teams:
                    winner = sorted_teams[0]
                    content += f"\n🏆 WINNER: Team {winner[0]} - {winner[1]['team_name']} with {winner[1]['points']} points!\n"
                
                content += "\n" + "=" * 60 + "\n"
                content += "HIT LOG\n"
                content += "=" * 60 + "\n\n"
                
                for hit in self.hit_log:
                    attacker_id = hit.get('attacking_team')
                    defender_id = hit.get('defending_team')
                    if attacker_id in self.teams and defender_id in self.teams:
                        timestamp = hit.get('timestamp', 'N/A')
                        content += f"[{timestamp}] Team {attacker_id} ({self.teams[attacker_id]['team_name']}) → "
                        content += f"Team {defender_id} ({self.teams[defender_id]['team_name']})\n"
                
                content += "\n" + "=" * 60 + "\n"
                content += "END OF REPORT\n"
                content += "=" * 60 + "\n"
                
                # Write to file
                with open(filename, 'w') as f:
                    f.write(content)
                
                messagebox.showinfo("Success", f"Match results saved to:\n{filename}")
                filename_dialog.destroy()
                
            except Exception as e:
                messagebox.showerror("Error", f"Failed to save results:\n{e}")
        
        btn_frame = tk.Frame(filename_dialog, bg='#2a2a2a')
        btn_frame.pack(pady=15)
        
        tk.Button(btn_frame, text="💾 Save", command=save_file,
                 font=('Arial', 11, 'bold'), bg='#4CAF50', fg='white',
                 width=12, height=2).pack(side=tk.LEFT, padx=5)
        
        tk.Button(btn_frame, text="Skip", command=filename_dialog.destroy,
                 font=('Arial', 11, 'bold'), bg='#607D8B', fg='white',
                 width=12, height=2).pack(side=tk.LEFT, padx=5)
    
    def show_final_results(self):
        """Show final results dialog"""
        results_window = tk.Toplevel(self.root)
        results_window.title("🏆 Final Results")
        results_window.geometry("600x500")
        results_window.configure(bg='#2d2d2d')
        
        tk.Label(results_window, text="🏆 FINAL RESULTS 🏆",
                font=('Arial', 18, 'bold'), bg='#2d2d2d', fg='gold').pack(pady=20)
        
        # Show match name
        if hasattr(self, 'current_match_name'):
            tk.Label(results_window, text=f"Match: {self.current_match_name}",
                    font=('Arial', 12), bg='#2d2d2d', fg='cyan').pack(pady=5)
        
        # Sort participating teams by points
        if hasattr(self, 'participating_teams'):
            sorted_teams = sorted(
                [self.teams[tid] for tid in self.participating_teams if tid in self.teams],
                key=lambda t: t['points'],
                reverse=True
            )
            tk.Label(results_window, text=f"Participating Teams: {len(sorted_teams)}",
                    font=('Arial', 11), bg='#2d2d2d', fg='white').pack(pady=2)
        else:
            sorted_teams = sorted(self.teams.values(), key=lambda t: t['points'], reverse=True)
        
        results_text = scrolledtext.ScrolledText(results_window,
                                                font=('Courier', 11),
                                                bg='#1a1a1a', fg='white',
                                                height=15)
        results_text.pack(fill=tk.BOTH, expand=True, padx=20, pady=(10, 20))
        
        for rank, team in enumerate(sorted_teams, 1):
            kd_ratio = team['kills'] / team['deaths'] if team['deaths'] > 0 else team['kills']
            line = f"{rank}. {team['team_name']:20s} {team['points']:4d} pts  K/D: {team['kills']}/{team['deaths']} ({kd_ratio:.2f})\n"
            results_text.insert(tk.END, line)
        
        results_text.config(state=tk.DISABLED)
    
    def broadcast_message(self, message: dict):
        """Broadcast message to all teams' laptops"""
        for team_id in self.teams.keys():
            self.send_to_team(team_id, message)
    
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
        
        # Check for robots that should be re-enabled
        robots_to_enable = []
        for team_id, disable_until in list(self.disabled_robots.items()):
            if current_time >= disable_until:
                robots_to_enable.append(team_id)
        
        # Send re-enable notifications
        for team_id in robots_to_enable:
            del self.disabled_robots[team_id]
            enable_message = {
                'type': 'ROBOT_ENABLED',
                'timestamp': current_time
            }
            self.send_to_team(team_id, enable_message)
            print(f"[GV] Team {team_id} re-enabled")
        
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
        """Open team selection dialog first"""
        # Create team selection dialog
        selection_dialog = tk.Toplevel(self.root)
        selection_dialog.title("🎮 Select Teams for Camera View")
        selection_dialog.geometry("450x400")
        selection_dialog.configure(bg='#2a2a2a')
        selection_dialog.transient(self.root)
        selection_dialog.grab_set()
        
        # Title
        tk.Label(selection_dialog, text="Select Teams for Camera View",
                font=('Arial', 16, 'bold'), bg='#2a2a2a', fg='#00ff00').pack(pady=15)
        
        tk.Label(selection_dialog, text="Enter Team IDs (1-254) - Leave empty for unused slots:",
                font=('Arial', 11), bg='#2a2a2a', fg='white').pack(pady=5)
        
        # Available teams display
        if self.teams:
            available_text = "Available Teams: " + ", ".join([f"{tid} ({self.teams[tid]['team_name']})" 
                                                              for tid in sorted(self.teams.keys())])
        else:
            available_text = "No teams connected yet - You can still open the viewer"
        
        tk.Label(selection_dialog, text=available_text,
                font=('Arial', 9), bg='#2a2a2a', fg='cyan', wraplength=400).pack(pady=5)
        
        # Input frame
        input_frame = tk.Frame(selection_dialog, bg='#2a2a2a')
        input_frame.pack(pady=20)
        
        # Create 4 entry fields
        entries = []
        for i in range(4):
            row_frame = tk.Frame(input_frame, bg='#2a2a2a')
            row_frame.pack(pady=5)
            
            tk.Label(row_frame, text=f"Camera {i+1} - Team ID:",
                    font=('Arial', 11), bg='#2a2a2a', fg='white', width=18).pack(side=tk.LEFT, padx=5)
            
            entry = tk.Entry(row_frame, font=('Arial', 12), width=8,
                           bg='#3a3a3a', fg='white', insertbackground='white',
                           justify='center')
            entry.pack(side=tk.LEFT, padx=5)
            entries.append(entry)
            
            # Pre-fill with first 4 available teams
            available_teams = sorted(self.teams.keys())
            if i < len(available_teams):
                entry.insert(0, str(available_teams[i]))
        
        # Info label
        tk.Label(selection_dialog, text="💡 Tip: You can open with 1-4 teams",
                font=('Arial', 9, 'italic'), bg='#2a2a2a', fg='#888888').pack(pady=5)
        
        # Error label
        error_label = tk.Label(selection_dialog, text="",
                              font=('Arial', 10), bg='#2a2a2a', fg='red')
        error_label.pack(pady=5)
        
        # Buttons
        btn_frame = tk.Frame(selection_dialog, bg='#2a2a2a')
        btn_frame.pack(pady=20)
        
        def open_feeds():
            # Get team IDs from entries
            selected_teams = []
            try:
                for entry in entries:
                    value = entry.get().strip()
                    if value:  # Allow empty entries
                        team_id = int(value)
                        if team_id < 1 or team_id > 254:
                            error_label.config(text=f"❌ Team ID must be between 1-254!")
                            return
                        if team_id in selected_teams:
                            error_label.config(text=f"❌ Team {team_id} selected multiple times!")
                            return
                        selected_teams.append(team_id)
                
                if len(selected_teams) == 0:
                    error_label.config(text="❌ Please enter at least one team ID!")
                    return
                
                # Close dialog and open camera viewer
                selection_dialog.destroy()
                self.open_embedded_camera_viewer(selected_teams)
                
            except ValueError:
                error_label.config(text="❌ Please enter valid numbers!")
        
        tk.Button(btn_frame, text="📹 Open Camera Feeds", command=open_feeds,
                 font=('Arial', 12, 'bold'), bg='#4CAF50', fg='white',
                 width=18, height=2).pack(side=tk.LEFT, padx=5)
        
        tk.Button(btn_frame, text="✗ Cancel", command=selection_dialog.destroy,
                 font=('Arial', 12, 'bold'), bg='#f44336', fg='white',
                 width=12, height=2).pack(side=tk.LEFT, padx=5)
    
    def open_embedded_camera_viewer(self, team_ids):
        """Open embedded camera viewer with GStreamer via PyGObject"""
        try:
            import gi
            gi.require_version('Gst', '1.0')
            gi.require_version('GstVideo', '1.0')
            from gi.repository import Gst, GLib, GstVideo
            from PIL import Image, ImageTk
            import numpy as np
        except ImportError as e:
            messagebox.showerror("Missing Dependencies", 
                               "PyGObject or GStreamer not installed!\n\n" +
                               f"Error: {e}\n\n" +
                               "Run: sudo apt install python3-gi gir1.2-gstreamer-1.0")
            return
        except ValueError as e:
            messagebox.showerror("GStreamer Error", 
                               f"GStreamer initialization failed!\n\n{e}")
            return
        
        # Initialize GStreamer
        Gst.init(None)
        
        # Create camera viewer window
        cam_window = tk.Toplevel(self.root)
        cam_window.title("📹 Live Camera Monitor - Embedded Feeds")
        cam_window.configure(bg='#000000')
        
        # Maximize window (cross-platform)
        cam_window.attributes('-zoomed', True)  # Linux/Unix
        cam_window.update_idletasks()
        
        # Get screen dimensions
        screen_width = cam_window.winfo_screenwidth()
        screen_height = cam_window.winfo_screenheight()
        
        # Calculate maximum dimensions for each quadrant
        TITLE_HEIGHT = 60
        CONTROL_HEIGHT = 50
        INFO_BAR_HEIGHT = 50
        BOTTOM_BAR_HEIGHT = 35
        
        GRID_HEIGHT = screen_height - TITLE_HEIGHT - CONTROL_HEIGHT
        GRID_WIDTH = screen_width
        
        # Each quadrant gets half the grid space
        QUADRANT_WIDTH = GRID_WIDTH // 2
        QUADRANT_HEIGHT = GRID_HEIGHT // 2
        
        # Video area within quadrant (maximize, minimal padding)
        VIDEO_WIDTH = QUADRANT_WIDTH - 20  # Small margin for borders
        VIDEO_HEIGHT = QUADRANT_HEIGHT - INFO_BAR_HEIGHT - BOTTOM_BAR_HEIGHT - 15
        
        print(f"[Camera] Screen: {screen_width}x{screen_height}")
        print(f"[Camera] Video size per feed: {VIDEO_WIDTH}x{VIDEO_HEIGHT}")
        
        # Title bar
        title_frame = tk.Frame(cam_window, bg='#1a1a1a', height=TITLE_HEIGHT)
        title_frame.pack(fill=tk.X)
        title_frame.pack_propagate(False)
        
        tk.Label(title_frame, text="📹 LIVE CAMERA FEEDS - EMBEDDED VIEW", 
                font=('Arial', 18, 'bold'), bg='#1a1a1a', fg='#00ff00').pack(pady=10)
        
        # Create 2x2 grid for cameras
        grid_frame = tk.Frame(cam_window, bg='#000000')
        grid_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Configure grid - ALWAYS configure both rows and columns for 2x2 grid
        grid_frame.grid_rowconfigure(0, weight=1, uniform="row")
        grid_frame.grid_rowconfigure(1, weight=1, uniform="row")
        grid_frame.grid_columnconfigure(0, weight=1, uniform="col")
        grid_frame.grid_columnconfigure(1, weight=1, uniform="col")
        
        # Video capture objects and display labels
        video_pipelines = {}
        video_labels = {}
        status_labels = {}
        retry_buttons = {}
        video_frames = {}  # Store latest frames
        
        def on_new_sample(sink, team_id):
            """Callback when new video frame arrives"""
            sample = sink.emit('pull-sample')
            if sample:
                buffer = sample.get_buffer()
                caps = sample.get_caps()
                
                # Get video info
                structure = caps.get_structure(0)
                width = structure.get_value('width')
                height = structure.get_value('height')
                
                # Get buffer data
                success, map_info = buffer.map(Gst.MapFlags.READ)
                if success:
                    # Convert to numpy array
                    frame_data = np.ndarray(
                        shape=(height, width, 3),
                        dtype=np.uint8,
                        buffer=map_info.data
                    )
                    
                    # Store frame for display
                    video_frames[team_id] = frame_data.copy()
                    
                    buffer.unmap(map_info)
            
            return Gst.FlowReturn.OK
        
        def connect_to_stream(team_id, video_port):
            """Helper function to create GStreamer pipeline for a video stream"""
            try:
                # Create GStreamer pipeline - OPTIMIZED FOR LOW LATENCY
                pipeline_str = (
                    f"udpsrc port={video_port} "
                    f"caps=\"application/x-rtp,media=video,clock-rate=90000,encoding-name=H264,payload=96\" ! "
                    "rtpjitterbuffer latency=0 drop-on-latency=true ! "  # Minimal buffering
                    "rtph264depay ! "
                    "h264parse ! "
                    "avdec_h264 max-threads=4 ! "  # Use multiple threads for decoding
                    "videoconvert ! "
                    "video/x-raw,format=RGB ! "
                    "appsink name=sink emit-signals=true max-buffers=1 drop=true sync=false"  # No sync, drop old frames
                )
                
                print(f"[Camera] Creating pipeline for Team {team_id} on port {video_port}...")
                print(f"[Camera] Pipeline: {pipeline_str}")
                
                pipeline = Gst.parse_launch(pipeline_str)
                
                # Get appsink element
                sink = pipeline.get_by_name('sink')
                sink.connect('new-sample', on_new_sample, team_id)
                
                # Start pipeline
                ret = pipeline.set_state(Gst.State.PLAYING)
                if ret == Gst.StateChangeReturn.FAILURE:
                    print(f"[Camera] Failed to start pipeline for Team {team_id}")
                    status_labels[team_id].config(text="❌ Pipeline Failed", fg='red')
                    video_labels[team_id].config(text="❌ Pipeline Start Failed\n\nClick Retry", fg='red')
                    return False
                
                video_pipelines[team_id] = pipeline
                status_labels[team_id].config(text="✅ Pipeline Started", fg='lime')
                print(f"[Camera] Team {team_id} pipeline started!")
                return True
                    
            except Exception as e:
                print(f"[Camera] Error creating pipeline for Team {team_id}: {e}")
                status_labels[team_id].config(text=f"❌ Error", fg='red')
                video_labels[team_id].config(
                    text=f"❌ Pipeline Error\n\n{str(e)[:50]}\n\nClick Retry",
                    fg='red'
                )
                return False
        
        # Create camera feeds for selected teams
        for idx, team_id in enumerate(team_ids):
            # Calculate grid position (2x2 grid)
            row = idx // 2
            col = idx % 2
            
            # Container frame for each camera
            container = tk.Frame(grid_frame, bg='#1a1a1a', 
                               highlightbackground='#00ff00', highlightthickness=2)
            container.grid(row=row, column=col, sticky='nsew', padx=3, pady=3)
            
            # Check if team exists
            if team_id in self.teams:
                team = self.teams[team_id]
                team_name = team['team_name']
                video_port = team['video_port']
            else:
                # Team not connected yet, but we can still set up the slot
                team_name = f"Team {team_id}"
                video_port = self.config['video_ports_start'] + team_id - 1
            
            # Info header (compact to save space)
            info_frame = tk.Frame(container, bg='#1a1a1a', height=INFO_BAR_HEIGHT)
            info_frame.pack(fill=tk.X)
            info_frame.pack_propagate(False)
            
            tk.Label(info_frame, text=f"🤖 {team_name} (Team {team_id})",
                    font=('Arial', 10, 'bold'), bg='#1a1a1a', fg='#00ff00').pack(pady=2)
            
            tk.Label(info_frame, text=f"Port: {video_port}",
                    font=('Courier', 8), bg='#1a1a1a', fg='cyan').pack()
            
            # Video display area - let it fill the container naturally
            video_label = tk.Label(container, bg='#000000', text="📺 Connecting...",
                                 font=('Arial', 14), fg='yellow')
            video_label.pack(fill=tk.BOTH, expand=True)
            video_labels[team_id] = video_label
            
            # Bottom control bar (compact to save space)
            bottom_bar = tk.Frame(container, bg='#1a1a1a', height=BOTTOM_BAR_HEIGHT)
            bottom_bar.pack(fill=tk.X)
            bottom_bar.pack_propagate(False)
            
            # Status label
            status_label = tk.Label(bottom_bar, text="⏳ Initializing...",
                                  font=('Arial', 8), bg='#1a1a1a', fg='yellow')
            status_label.pack(side=tk.LEFT, padx=5, pady=2)
            status_labels[team_id] = status_label
            
            # Retry button for this specific feed
            def make_retry_func(tid, vport):
                def retry():
                    status_labels[tid].config(text="🔄 Retrying...", fg='yellow')
                    video_labels[tid].config(text="🔄 Reconnecting...", fg='yellow')
                    
                    # Stop old pipeline if exists
                    if tid in video_pipelines:
                        try:
                            video_pipelines[tid].set_state(Gst.State.NULL)
                            del video_pipelines[tid]
                        except:
                            pass
                    
                    # Clear frame
                    if tid in video_frames:
                        del video_frames[tid]
                    
                    # Try to reconnect
                    connect_to_stream(tid, vport)
                return retry
            
            retry_btn = tk.Button(bottom_bar, text="🔄 Retry", 
                                 command=make_retry_func(team_id, video_port),
                                 bg='#FF9800', fg='white', font=('Arial', 7, 'bold'),
                                 width=6, height=1)
            retry_btn.pack(side=tk.RIGHT, padx=5, pady=2)
            retry_buttons[team_id] = retry_btn
            
            # Try initial connection
            connect_to_stream(team_id, video_port)
        
        # Fill empty slots to maintain grid structure
        for slot in range(len(team_ids), 4):
            row = slot // 2
            col = slot % 2
            empty_container = tk.Frame(grid_frame, bg='#1a1a1a', 
                                      highlightbackground='#333333', highlightthickness=2)
            empty_container.grid(row=row, column=col, sticky='nsew', padx=3, pady=3)
            tk.Label(empty_container, text="-- Empty Slot --", 
                    font=('Arial', 14), bg='#1a1a1a', fg='#444444').pack(expand=True)
        
        # Control panel at bottom
        control_frame = tk.Frame(cam_window, bg='#1a1a1a')
        control_frame.pack(fill=tk.X, pady=(5, 0))
        
        def reconnect_all():
            """Reconnect all video streams"""
            for team_id in list(video_labels.keys()):
                status_labels[team_id].config(text="🔄 Reconnecting...", fg='yellow')
                video_labels[team_id].config(text="🔄 Reconnecting...", fg='yellow')
                
                # Stop old pipeline if exists
                if team_id in video_pipelines:
                    try:
                        video_pipelines[team_id].set_state(Gst.State.NULL)
                        del video_pipelines[team_id]
                    except:
                        pass
                
                # Clear frame
                if team_id in video_frames:
                    del video_frames[team_id]
                
                # Get video port
                if team_id in self.teams:
                    video_port = self.teams[team_id]['video_port']
                else:
                    video_port = self.config['video_ports_start'] + team_id - 1
                
                # Try to reconnect
                connect_to_stream(team_id, video_port)
        
        tk.Button(control_frame, text="🔄 Reconnect All", command=reconnect_all,
                 bg='#FF9800', fg='white', font=('Arial', 10, 'bold'),
                 width=15).pack(side=tk.LEFT, padx=10)
        
        info_label = tk.Label(control_frame, 
                             text="💡 Embedded video feeds using GStreamer + PyGObject",
                             font=('Arial', 9), bg='#1a1a1a', fg='#888888')
        info_label.pack(side=tk.RIGHT, padx=10)
        
        # FPS tracking
        fps_label = tk.Label(control_frame, text="FPS: --",
                            font=('Arial', 10), bg='#1a1a1a', fg='cyan')
        fps_label.pack(side=tk.LEFT, padx=10)
        
        # Video display update loop
        last_frame_time = time.time()
        frame_count = 0
        
        def update_video_display():
            """Update video displays with latest frames"""
            nonlocal last_frame_time, frame_count
            
            if not cam_window.winfo_exists():
                return
            
            frame_count += 1
            current_time = time.time()
            
            # Update FPS counter every second
            if current_time - last_frame_time >= 1.0:
                fps = frame_count / (current_time - last_frame_time)
                fps_label.config(text=f"FPS: {fps:.1f}")
                frame_count = 0
                last_frame_time = current_time
            
            # Update each video label with latest frame
            for team_id in video_labels.keys():
                if team_id in video_frames:
                    try:
                        frame = video_frames[team_id]
                        
                        # Get actual label dimensions (after window is rendered)
                        label = video_labels[team_id]
                        label_width = label.winfo_width()
                        label_height = label.winfo_height()
                        
                        # Use actual dimensions if available, otherwise use calculated values
                        if label_width > 10 and label_height > 10:
                            display_width = label_width
                            display_height = label_height
                        else:
                            # Fallback to calculated dimensions for initial render
                            display_width = VIDEO_WIDTH
                            display_height = VIDEO_HEIGHT
                        
                        # Resize using PIL - FASTER BILINEAR instead of LANCZOS for lower latency
                        img = Image.fromarray(frame)
                        img = img.resize((display_width, display_height), Image.Resampling.BILINEAR)
                        
                        # Add overlays
                        from PIL import ImageDraw, ImageFont
                        draw = ImageDraw.Draw(img)
                        
                        # Add timestamp
                        timestamp = datetime.now().strftime("%H:%M:%S")
                        try:
                            font_small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 16)
                            font_large = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 48)
                        except:
                            font_small = ImageFont.load_default()
                            font_large = ImageFont.load_default()
                        
                        draw.text((10, 10), timestamp, fill=(0, 255, 0), font=font_small)
                        
                        # Check if robot is disabled
                        if team_id in self.disabled_robots:
                            disable_until = self.disabled_robots[team_id]
                            if current_time < disable_until:
                                # Robot is still disabled - show red overlay
                                time_left = int(disable_until - current_time) + 1
                                
                                # Semi-transparent red overlay
                                from PIL import Image as PILImage
                                overlay = PILImage.new('RGBA', img.size, (255, 0, 0, 100))
                                img = img.convert('RGBA')
                                img = PILImage.alpha_composite(img, overlay)
                                img = img.convert('RGB')
                                draw = ImageDraw.Draw(img)
                                
                                # Large DISABLED text (no emoji)
                                text = "DISABLED"
                                
                                # Get actual text dimensions for proper centering
                                left, top, right, bottom = draw.textbbox((0, 0), text, font=font_large)
                                text_width = right - left
                                text_height = bottom - top
                                
                                # Center on the RESIZED image dimensions (display_width, display_height)
                                x = (display_width - text_width) // 2
                                y = (display_height - text_height) // 2 - 40
                                
                                # Black shadow for text
                                draw.text((x+3, y+3), text, fill=(0, 0, 0), font=font_large)
                                draw.text((x, y), text, fill=(255, 0, 0), font=font_large)
                                
                                # Time remaining
                                time_text = f"{time_left}s"
                                left, top, right, bottom = draw.textbbox((0, 0), time_text, font=font_large)
                                time_width = right - left
                                time_x = (display_width - time_width) // 2
                                time_y = y + text_height + 20
                                draw.text((time_x+3, time_y+3), time_text, fill=(0, 0, 0), font=font_large)
                                draw.text((time_x, time_y), time_text, fill=(255, 255, 0), font=font_large)
                                
                                status_labels[team_id].config(text=f"🔴 DISABLED ({time_left}s)", fg='red')
                            else:
                                # Disabled period expired - remove from dict
                                del self.disabled_robots[team_id]
                                status_labels[team_id].config(text="🟢 Live", fg='lime')
                        else:
                            status_labels[team_id].config(text="🟢 Live", fg='lime')
                        
                        # Convert to PhotoImage
                        photo = ImageTk.PhotoImage(image=img)
                        
                        # Update label
                        video_labels[team_id].config(image=photo, text="")
                        video_labels[team_id].image = photo  # Keep reference
                    except Exception as e:
                        print(f"[Camera] Display error for team {team_id}: {e}")
                        status_labels[team_id].config(text="⚠️ Display Error", fg='orange')
            
            # Schedule next update - FASTER for lower latency (60 FPS target)
            if cam_window.winfo_exists():
                cam_window.after(16, update_video_display)  # ~60 FPS (was 33ms/30fps)
        
        # Start display updates immediately
        cam_window.after(100, update_video_display)  # Start faster (was 500ms)
        
        # GStreamer main loop (process events) - MORE FREQUENT
        def gst_mainloop():
            """Process GStreamer events"""
            if cam_window.winfo_exists():
                # Process pending events
                context = GLib.MainContext.default()
                while context.pending():
                    context.iteration(False)
                cam_window.after(5, gst_mainloop)  # Check more frequently (was 10ms)
        
        gst_mainloop()
        
        # Cleanup function
        def on_close():
            print("[Camera] Closing camera viewer...")
            for pipeline in video_pipelines.values():
                try:
                    pipeline.set_state(Gst.State.NULL)
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
