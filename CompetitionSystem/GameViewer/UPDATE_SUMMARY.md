# 🎮 Game Viewer Updates - Team Selection & Results Export

## ✅ Changes Made

### 1. **Camera Viewer - Equal Space Quadrants**
The camera viewer now properly uses equal space for all 4 quadrants:
- Each quadrant dynamically resizes to fill its allocated space
- Video feeds scale to match the label dimensions
- All 4 cameras take equal screen real estate (no wasted space)
- Maintains aspect ratio while maximizing display area

### 2. **Team Selection for Match Start**
New workflow when starting a game:

**Before:**
- Click "Start Game" → All connected teams participate

**After:**
- Click "Start Game" → Team selection dialog opens
- Select 1-4 teams using checkboxes
- Shows ready status (✅/⏳) and online status (🟢/🔴) for each team
- Enter custom match name (optional, auto-generates if blank)
- Only selected teams receive game start messages
- Only selected teams have scores reset

**Features:**
- ✅ Select any 1-4 teams (flexible participation)
- ✅ Visual indicators for ready/online status
- ✅ Custom match naming
- ✅ Scrollable list for many teams
- ✅ Clear error messages

### 3. **Match Results Export to Text File**
When a match ends:

1. **Results dialog appears automatically**
2. **Custom filename prompt:**
   - Pre-filled with match name
   - Can customize before saving
   - Auto-adds `.txt` extension

3. **Comprehensive results file includes:**
   ```
   ═══════════════════════════════════════════════════════
   🏆 LASER TAG MATCH RESULTS
   ═══════════════════════════════════════════════════════
   
   Match Name: finals_round1
   Date/Time: 2025-11-03 14:30:45
   Duration: 120 seconds
   Participating Teams: 4
   
   ═══════════════════════════════════════════════════════
   FINAL STANDINGS
   ═══════════════════════════════════════════════════════
   
   Rank 1: Team 3 - Red Dragons
     Robot: DragonBot
     Points: 500
     Kills: 5
     Deaths: 2
     K/D Ratio: 2.50
   
   [... other teams ...]
   
   ═══════════════════════════════════════════════════════
   MATCH STATISTICS
   ═══════════════════════════════════════════════════════
   
   Total Points Scored: 1200
   Total Eliminations: 12
   Total Hit Events: 12
   
   🏆 WINNER: Team 3 - Red Dragons with 500 points!
   
   ═══════════════════════════════════════════════════════
   HIT LOG
   ═══════════════════════════════════════════════════════
   
   [14:31:23] Team 3 (Red Dragons) → Team 1 (Blue Team)
   [14:31:45] Team 2 (Green Squad) → Team 4 (Yellow Force)
   [... detailed hit log ...]
   ```

## 🎯 New Workflow

### Starting a Match

1. **Connect Teams** - Wait for robots to register
2. **Ready Check** (optional) - Click "📢 Ready Check"
3. **Start Game** - Click "▶️ Start Game"
4. **Select Teams** - Choose 1-4 teams from the list
5. **Name Match** - Enter custom name (e.g., "semifinals_round2")
6. **Begin!** - Click "▶️ Start Match"

### Ending a Match

1. **Time Expires** - Game auto-ends OR click "⏹️ End Game"
2. **Save Results** - Dialog appears with filename prompt
3. **Customize Name** - Edit filename if desired
4. **Save** - Click "💾 Save" to export results
5. **View Results** - Final standings popup appears

## 📊 Example Use Cases

### Tournament Bracket
```
# Quarterfinals
Match 1: Teams 1, 2 → Save as "quarter_match1.txt"
Match 2: Teams 3, 4 → Save as "quarter_match2.txt"

# Semifinals  
Match 3: Teams 1, 3 → Save as "semi_match1.txt"
Match 4: Teams 2, 4 → Save as "semi_match2.txt"

# Finals
Match 5: Teams 1, 2 → Save as "finals.txt"
```

### Practice Rounds
```
# 2v2 Practice
Teams 1, 3 vs Teams 2, 4 → Save as "practice_2v2.txt"

# FFA (Free For All)
Teams 1, 2, 3 → Save as "practice_ffa.txt"

# 1v1 Duel
Teams 5, 7 → Save as "duel_5v7.txt"
```

## 🔧 Technical Details

### Camera Quadrant Sizing
```python
# Before (fixed size)
display_width = 640
display_height = 400

# After (dynamic equal sizing)
label_width = video_label.winfo_width()
label_height = video_label.winfo_height()
display_width = label_width - 10  # Small padding
display_height = label_height - 10
```

### Team Selection Storage
```python
self.participating_teams = [1, 2, 3, 4]  # Selected team IDs
self.current_match_name = "semifinals_round1"  # Custom name
```

### File Structure
- Saved in current directory
- Plain text format (.txt)
- Human-readable formatting
- Includes all match data
- Timestamped hit log

## 💡 Tips

### Match Naming Convention
```
# Recommended formats:
"quarter_match1"
"semi_match2"  
"finals"
"practice_1v1"
"round1_team1v3"
"tournament_final"
```

### Running Multiple Matches
1. Start match with teams 1, 2
2. End match → Save as "match1.txt"
3. Start new match with teams 3, 4
4. End match → Save as "match2.txt"
5. All results preserved in separate files!

### Results Analysis
- Open .txt files in any text editor
- Easy to share via email/Slack
- Can be archived for tournament records
- Parse with scripts if needed

## 🐛 Troubleshooting

### Camera Feeds Not Filling Space?
- Resize the window - feeds auto-adjust
- Maximize window for best results
- Equal space maintained at all window sizes

### Team Selection Not Showing All Teams?
- Scroll down in the selection dialog
- Teams appear as they connect
- Online status updates in real-time

### Results File Not Saving?
- Check file permissions in directory
- Ensure filename is valid (no special chars like / \ : *)
- "Skip" button available if you don't want to save

## 📝 Summary

All requested features implemented:
✅ Camera feeds use equal space (no waste)
✅ Select 1-4 specific teams for each match
✅ Custom match naming
✅ Comprehensive results export to .txt file
✅ Detailed hit log included
✅ Tournament-ready workflow

The Game Viewer is now perfect for running tournaments with multiple rounds and proper result tracking! 🏆
