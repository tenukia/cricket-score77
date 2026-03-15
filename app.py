import streamlit as st
import json
import os
from datetime import datetime
import pandas as pd
import plotly.graph_objects as go
from collections import defaultdict
import time

# --- PAGE CONFIG ---
st.set_page_config(
    page_title="Pro Cricket League",
    page_icon="🏏",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- CONSTANTS ---
DB_FILE = "data.json"
HISTORY_FILE = "history.json"
ACTION_HISTORY_FILE = "action_history.json"
ADMIN_PIN = "sidhu-amg"  # Change this in production

# --- SESSION STATE INITIALIZATION ---
def initialize_session_state():
    """Initialize all session state variables"""
    if "authenticated" not in st.session_state:
        st.session_state["authenticated"] = False
    if "last_update" not in st.session_state:
        st.session_state["last_update"] = time.time()
    if "last_rerun" not in st.session_state:
        st.session_state["last_rerun"] = 0
    if "ball_by_ball" not in st.session_state:
        st.session_state["ball_by_ball"] = []
    if "match_events" not in st.session_state:
        st.session_state["match_events"] = []
    if "action_history" not in st.session_state:
        st.session_state["action_history"] = []
    if "debug_messages" not in st.session_state:
        st.session_state["debug_messages"] = []

# Initialize session state immediately
initialize_session_state()

# --- PERSISTENT AUTHENTICATION ---
def check_persistent_auth():
    """Check for persistent authentication using query params"""
    # Check if there's a auth token in query params
    try:
        query_params = st.query_params
        if "auth" in query_params and query_params["auth"] == "admin":
            st.session_state["authenticated"] = True
            # Clear the query param for security
            st.query_params.clear()
    except Exception:
        # Fallback if query_params not available
        pass

# Check persistent auth on every run
check_persistent_auth()

# --- DATA MANAGEMENT CLASS ---
class CricketDataManager:
    @staticmethod
    def load_data():
        if os.path.exists(DB_FILE):
            with open(DB_FILE, "r") as f:
                try:
                    d = json.load(f)
                    defaults = {
                        "team_a": "Team A", "team_b": "Team B", "max_overs": 20, "innings": 1,
                        "score": 0, "wickets": 0, "balls": 0, "overs": 0.0, "target": 0,
                        "team_a_squad": [], "team_b_squad": [], "batting_stats": {}, "bowling_stats": {},
                        "out_players": [], "current_striker": "None", "current_non_striker": "None", 
                        "current_bowler": "None", "is_finished": False, "winner": "", "toss_winner": "",
                        "match_start_time": "", "partnership_runs": 0, "partnership_balls": 0,
                        "run_rate": 0.0, "required_run_rate": 0.0, "extras": 0
                    }
                    for key, val in defaults.items():
                        if key not in d: d[key] = val
                    return d
                except: 
                    return CricketDataManager.get_default_data()
        return CricketDataManager.get_default_data()
    
    @staticmethod
    def get_default_data():
        return {
            "team_a": "Team A", "team_b": "Team B", "max_overs": 20, "innings": 1,
            "score": 0, "wickets": 0, "balls": 0, "overs": 0.0, "target": 0,
            "team_a_squad": [], "team_b_squad": [], "batting_stats": {}, "bowling_stats": {},
            "out_players": [], "current_striker": "None", "current_non_striker": "None", 
            "current_bowler": "None", "is_finished": False, "winner": "", "toss_winner": "",
            "match_start_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), 
            "partnership_runs": 0, "partnership_balls": 0, "run_rate": 0.0,
            "required_run_rate": 0.0, "extras": 0
        }
    
    @staticmethod
    def save_data(data, action_type="DATA_UPDATE", description="Data updated"):
        # Load current data before saving for undo functionality
        current_data = CricketDataManager.load_data()
        
        # Save the new data with comprehensive error handling
        try:
            with open(DB_FILE, "w") as f:
                json.dump(data, f, indent=4)
        except PermissionError:
            raise Exception("❌ Permission denied: Cannot write to data file. Check file permissions.")
        except OSError as e:
            if "No space left" in str(e):
                raise Exception("❌ Disk full: Cannot save data. Free up disk space.")
            elif "Device full" in str(e):
                raise Exception("❌ Disk full: Cannot save data. Free up disk space.")
            else:
                raise Exception(f"❌ File system error: {e}")
        except Exception as e:
            raise Exception(f"❌ Save failed: {e}")
        
        # Save action for undo (only if data actually changed)
        if current_data != data:
            CricketDataManager.save_action(action_type, description, current_data)
    
    @staticmethod
    def save_to_history(data):
        history_file = "history.json"
        history = []
        
        # Load existing history with error handling
        if os.path.exists(history_file):
            try:
                with open(history_file, "r") as f:
                    history = json.load(f)
            except PermissionError:
                st.error("❌ Cannot read history: File locked by another process.")
                return
            except json.JSONDecodeError:
                st.warning("⚠️ History file corrupted, creating new history.")
                history = []
            except Exception as e:
                st.error(f"❌ History load failed: {e}")
                history = []
        
        # Calculate economy rates and strike rates
        batting_performance = []
        for player, stats in data["batting_stats"].items():
            strike_rate = (stats["r"] / stats["b"] * 100) if stats["b"] > 0 else 0
            batting_performance.append({
                "player": player,
                "runs": stats["r"],
                "balls": stats["b"],
                "strike_rate": round(strike_rate, 2)
            })
        
        bowling_performance = []
        for player, stats in data["bowling_stats"].items():
            overs_bowled = stats["balls"] // 6 + (stats["balls"] % 6) / 10
            economy = stats["r"] / overs_bowled if overs_bowled > 0 else 0
            bowling_performance.append({
                "player": player,
                "overs": overs_bowled,
                "maidens": stats.get("maidens", 0),
                "runs": stats["r"],
                "wickets": stats["w"],
                "economy": round(economy, 2)
            })
        
        match_summary = {
            "match_id": len(history) + 1,
            "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "teams": f"{data['team_a']} vs {data['team_b']}",
            "winner": data['winner'],
            "score": f"{data['score']}/{data['wickets']} ({data['overs']} ov)",
            "batting_stats": batting_performance,
            "bowling_stats": bowling_performance,
            "man_of_match": CricketDataManager.get_man_of_match(data)
        }
        
        # Save with file locking and error handling
        if not history or history[-1].get("match_id") != match_summary["match_id"]:
            history.append(match_summary)
            try:
                # Use file locking to prevent concurrent access
                import fcntl
                with open(history_file, "w") as f:
                    fcntl.flock(f.fileno(), fcntl.LOCK_EX)
                    json.dump(history, f, indent=4)
                    fcntl.flock(f.fileno(), fcntl.LOCK_UN)
            except ImportError:
                # Fallback for Windows systems
                with open(history_file, "w") as f:
                    json.dump(history, f, indent=4)
            except PermissionError:
                st.error("❌ Cannot save history: File is locked or permission denied.")
            except OSError as e:
                if "No space left" in str(e) or "Device full" in str(e):
                    st.error("❌ Disk full: Cannot save history. Free up disk space.")
                else:
                    st.error(f"❌ History save failed: {e}")
            except Exception as e:
                st.error(f"❌ Unexpected error saving history: {e}")
    
    @staticmethod
    def get_man_of_match(data):
        # Simple logic for MOM - can be enhanced
        top_score = 0
        mom = "TBD"
        for player, stats in data["batting_stats"].items():
            if stats["r"] > top_score:
                top_score = stats["r"]
                mom = player
        for player, stats in data["bowling_stats"].items():
            if stats["w"] > 3:  # 3+ wickets
                mom = player
        return mom
    
    @staticmethod
    def load_history():
        if os.path.exists(HISTORY_FILE):
            with open(HISTORY_FILE, "r") as f:
                try: 
                    return json.load(f)
                except: 
                    return []
        return []
    
    @staticmethod
    def save_action(action_type, description, previous_data):
        """Save action to history for undo functionality"""
        action_history = []
        
        # Load existing action history with memory management
        try:
            if os.path.exists(ACTION_HISTORY_FILE):
                with open(ACTION_HISTORY_FILE, "r") as f:
                    action_history = json.load(f)
                    
                    # Memory management: limit history size
                    if len(action_history) > 50:  # Reduced from 100 to prevent memory overflow
                        action_history = action_history[-50:]  # Keep only last 50 actions
                        st.warning("⚠️ Action history trimmed to prevent memory overflow.")
        except json.JSONDecodeError:
            st.warning("⚠️ Action history corrupted, starting fresh.")
            action_history = []
        except Exception as e:
            st.error(f"❌ Action history load failed: {e}")
            action_history = []
        
        # Validate player names in previous_data
        if previous_data:
            for stats_type in ["batting_stats", "bowling_stats"]:
                if stats_type in previous_data:
                    invalid_players = []
                    for player_name in previous_data[stats_type].keys():
                        if not player_name or not isinstance(player_name, str):
                            invalid_players.append(player_name)
                    
                    if invalid_players:
                        st.warning(f"⚠️ Invalid player names found: {invalid_players}")
        
        action = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "action_type": action_type,
            "description": description,
            "previous_data": previous_data.copy() if previous_data else {}
        }
        
        action_history.append(action)
        
        # Keep only last 10 actions (reduced for performance)
        if len(action_history) > 10:
            action_history = action_history[-10:]
        
        # Save with error handling
        try:
            with open(ACTION_HISTORY_FILE, "w") as f:
                json.dump(action_history, f, indent=4)
        except PermissionError:
            st.error("❌ Cannot save action: File locked or permission denied.")
        except OSError as e:
            if "No space left" in str(e) or "Device full" in str(e):
                st.error("❌ Disk full: Cannot save action history.")
            else:
                st.error(f"❌ Action save failed: {e}")
        except Exception as e:
            st.error(f"❌ Unexpected error saving action: {e}")
        
        # Update session state with memory management
        try:
            st.session_state["action_history"] = action_history
        except Exception:
            pass  # Fallback if session state unavailable
    
    @staticmethod
    def load_action_history():
        """Load action history from file"""
        if os.path.exists(ACTION_HISTORY_FILE):
            with open(ACTION_HISTORY_FILE, "r") as f:
                try:
                    return json.load(f)
                except:
                    return []
        return []
    
    @staticmethod
    def undo_last_action():
        """Undo the last action"""
        action_history = CricketDataManager.load_action_history()
        if not action_history:
            return False, "No actions to undo"
        
        last_action = action_history[-1]
        previous_data = last_action["previous_data"]
        
        # Restore previous data
        try:
            with open(DB_FILE, "w") as f:
                json.dump(previous_data, f, indent=4)
        except Exception as e:
            return False, f"Failed to restore data: {e}"
        
        # Restore ball_by_ball data from session state or recreate it
        try:
            # Calculate ball_by_ball from restored data
            restored_ball_by_ball = []
            if previous_data and "balls" in previous_data:
                # Recreate ball_by_ball data based on restored match state
                total_balls = previous_data["balls"]
                current_over = total_balls // 6 + 1 if total_balls > 0 else 1
                
                # For now, create empty ball_by_ball to ensure correct over display
                # The actual ball history will be rebuilt as new balls are played
                restored_ball_by_ball = []
            
            # Update session state
            st.session_state["ball_by_ball"] = restored_ball_by_ball
            
            # Save ball_by_ball to file
            with open("ball_by_ball.json", "w") as f:
                json.dump(restored_ball_by_ball, f, indent=4)
                
        except Exception as e:
            # If ball_by_ball restore fails, at least clear it to prevent wrong display
            try:
                st.session_state["ball_by_ball"] = []
                with open("ball_by_ball.json", "w") as f:
                    json.dump([], f, indent=4)
            except:
                pass
        
        # Remove the last action from history
        action_history = action_history[:-1]
        try:
            with open(ACTION_HISTORY_FILE, "w") as f:
                json.dump(action_history, f, indent=4)
        except Exception as e:
            return False, f"Failed to update action history: {e}"
        
        st.session_state["action_history"] = action_history
        return True, f"Undone: {last_action['description']}"

# --- CSS STYLING ---
def apply_custom_css():
    st.markdown("""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@400;600;700;800&display=swap');
        
        * {
            font-family: 'Montserrat', sans-serif;
        }
        
        .main-header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            padding: 25px;
            border-radius: 15px;
            color: white;
            text-align: center;
            margin-bottom: 20px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.2);
        }
        
        .main-score {
            background: linear-gradient(135deg, #141E30 0%, #243B55 100%);
            padding: 40px;
            border-radius: 25px;
            color: white;
            text-align: center;
            border: 3px solid #ff4b4b;
            box-shadow: 0 20px 40px rgba(0,0,0,0.3);
            margin-bottom: 20px;
        }
        
        .target-box {
            background: linear-gradient(90deg, #ff4b4b, #ff6b6b);
            color: white;
            padding: 20px;
            border-radius: 15px;
            font-weight: bold;
            margin-top: 15px;
            font-size: 20px;
            animation: pulse 2s infinite;
        }
        
        @keyframes pulse {
            0% { transform: scale(1); }
            50% { transform: scale(1.02); }
            100% { transform: scale(1); }
        }
        
        .winner-box {
            background: linear-gradient(90deg, #28a745, #1e7e34);
            color: white;
            padding: 40px;
            border-radius: 25px;
            text-align: center;
            font-size: 48px;
            font-weight: 800;
            margin: 20px 0;
            border: 5px solid gold;
            animation: glow 2s ease-in-out infinite;
        }
        
        @keyframes glow {
            0% { box-shadow: 0 0 5px gold; }
            50% { box-shadow: 0 0 30px gold; }
            100% { box-shadow: 0 0 5px gold; }
        }
        
        .player-box {
            background: white;
            padding: 25px;
            border-radius: 20px;
            border: 2px solid #667eea;
            text-align: center;
            box-shadow: 0 5px 15px rgba(0,0,0,0.1);
            transition: all 0.3s ease;
        }
        
        .player-box:hover {
            transform: translateY(-5px);
            box-shadow: 0 10px 25px rgba(102, 126, 234, 0.4);
        }
        
        .stat-card {
            background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
            color: white;
            padding: 20px;
            border-radius: 15px;
            text-align: center;
            font-weight: bold;
            font-size: 18px;
        }
        
        .commentary-box {
            background: #1a1a1a;
            color: #fff;
            padding: 15px;
            border-radius: 10px;
            border-left: 5px solid #ff4b4b;
            margin: 10px 0;
        }
        
        .run-rate-indicator {
            width: 100%;
            height: 10px;
            background: #eee;
            border-radius: 5px;
            margin: 10px 0;
        }
        
        .run-rate-fill {
            height: 100%;
            background: linear-gradient(90deg, #00b09b, #96c93d);
            border-radius: 5px;
            transition: width 0.5s ease;
        }
        
        .over-balls {
            display: flex;
            justify-content: center;
            align-items: center;
            gap: 12px;
            flex-wrap: wrap;
        }
        
        .ball-circle {
            width: 35px;
            height: 35px;
            border-radius: 50%;
            border: 2px solid #fff;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 9px;
            font-weight: bold;
            color: #000;
            background: rgba(255, 255, 255, 0.1);
        }
        
        .ball-unplayed {
            background: rgba(255, 255, 255, 0.1);
            color: transparent;
        }
        
        .ball-played {
            background: #888;
            color: #fff;
        }
        
        .ball-four {
            background: #28a745;
            color: #fff;
        }
        
        .ball-six {
            background: #6f42c1;
            color: #fff;
        }
        
        .ball-wicket {
            background: #dc3545;
            color: #fff;
        }
        
        .ball-extra {
            background: #fd7e14;
            color: #fff;
        }
        
        .ball-numbers {
            display: flex;
            justify-content: center;
            gap: 12px; /* Match the gap of over-balls */
            margin-top: 5px; /* Small margin to separate from balls */
        }
        
        .ball-numbers div {
            width: 35px; /* Match ball-circle width */
            text-align: center;
            font-size: 10px;
            color: #ccc;
        }
        
        .over-container {
            background: linear-gradient(135deg, #141E30 0%, #243B55 100%);
            padding: 15px;
            border-radius: 15px;
            border: 2px solid #ff4b4b;
            margin-top: -10px;
        }
        </style>
    """, unsafe_allow_html=True)

# --- UTILITY FUNCTIONS ---
def calculate_run_rate(score, balls):
    overs = balls / 6
    return round(score / overs if overs > 0 else 0, 2)

def format_overs(balls):
    return f"{balls // 6}.{balls % 6}"

def add_match_event(event_type, description, data):
    st.session_state["match_events"].append({
        "time": datetime.now().strftime("%H:%M:%S"),
        "type": event_type,
        "description": description,
        "data": data
    })

def generate_over_balls_display(data):
    """Generate HTML for current over balls display"""
    try:
        ball_by_ball_data = st.session_state.get("ball_by_ball", [])
    except Exception as e:
        st.error(f"Error accessing session state: {e}")
        return ""

    # Always show 6 circles, even if no balls bowled
    if not ball_by_ball_data:
        balls_html = ""
        ball_numbers_html = ""
        for i in range(6):
            balls_html += '<div class="ball-circle ball-unplayed"></div>'
            ball_numbers_html += f'<div>{i+1}</div>'
        
        return f'''
        <div class="over-container">
            <div class="over-balls">
                {balls_html}
            </div>
            <div class="ball-numbers">
                {ball_numbers_html}
            </div>
        </div>
    '''
    
    # Get current over number
    total_balls = data["balls"]
    current_over = total_balls // 6 + 1
    
    # Filter balls from current over
    current_over_balls = []
    for ball in st.session_state["ball_by_ball"]:
        if ball["over"] == current_over:
            current_over_balls.append(ball)
    
    # If no balls in current over, show empty circles
    if not current_over_balls:
        balls_html = ""
        ball_numbers_html = ""
        for i in range(6):
            balls_html += '<div class="ball-circle ball-unplayed"></div>'
            ball_numbers_html += f'<div>{i+1}</div>'
        
        return f'''
        <div class="over-container">
            <div class="over-balls">
                {balls_html}
            </div>
            <div class="ball-numbers">
                {ball_numbers_html}
            </div>
        </div>
    '''
    
    # Generate HTML for balls
    balls_html = ""
    ball_numbers_html = ""
    
    # Count legal balls and extras
    legal_ball_count = 0
    total_display_balls = 0
    
    # Process balls in order
    for ball in current_over_balls:
        if ball["ball_type"] not in ["Wide", "No Ball"]:
            legal_ball_count += 1
            total_display_balls += 1
            
            # Determine ball class and content
            ball_class = "ball-circle "
            ball_content = ""
            
            if ball["ball_type"] == "Wide":
                ball_class += "ball-extra"
                ball_content = "Wd"
            elif ball["ball_type"] == "No Ball":
                ball_class += "ball-extra"
                ball_content = "Nb"
            elif ball["ball_type"] == "Bye":
                ball_class += "ball-played"
                ball_content = f"Bye{ball['runs']}"
            elif ball["ball_type"] == "Leg Bye":
                ball_class += "ball-played"
                ball_content = f"LB{ball['runs']}"
            elif ball.get("is_wicket", False):
                ball_class += "ball-wicket"
                ball_content = "W"
            elif ball["runs"] == 4:
                ball_class += "ball-four"
                ball_content = "4"
            elif ball["runs"] == 6:
                ball_class += "ball-six"
                ball_content = "6"
            elif ball["runs"] == 0:
                ball_class += "ball-played"
                ball_content = "•"
            else:  # 1, 2, 3 runs
                ball_class += "ball-played"
                ball_content = str(ball["runs"])
            
            balls_html += f'<div class="{ball_class}">{ball_content}</div>'
            ball_numbers_html += f'<div>{total_display_balls}</div>'
            
            # Stop if we have 6 legal balls
            if legal_ball_count >= 6:
                break
        else:
            # Handle Wide and No Ball as extras
            total_display_balls += 1
            ball_class = "ball-circle ball-extra"
            ball_content = "Wd" if ball["ball_type"] == "Wide" else "Nb"
            
            balls_html += f'<div class="{ball_class}">{ball_content}</div>'
            ball_numbers_html += f'<div>{total_display_balls}</div>'
    
    # Add remaining unplayed balls (up to 6 legal balls)
    remaining_legal = 6 - legal_ball_count
    for i in range(remaining_legal):
        balls_html += '<div class="ball-circle ball-unplayed"></div>'
        ball_numbers_html += f'<div>{total_display_balls + i + 1}</div>'
    
    return f'''
        <div class="over-container">
            <div class="over-balls">
                {balls_html}
            </div>
            <div class="ball-numbers">
                {ball_numbers_html}
            </div>
        </div>
    '''

# Load data
data = CricketDataManager.load_data()

# Load action history after class is defined
st.session_state["action_history"] = CricketDataManager.load_action_history()

# Load ball_by_ball data from file if exists
if os.path.exists("ball_by_ball.json"):
    try:
        with open("ball_by_ball.json", "r") as f:
            st.session_state["ball_by_ball"] = json.load(f)
    except Exception as e:
        st.warning(f"⚠️ Could not load ball data: {e}")
        st.session_state["ball_by_ball"] = []

apply_custom_css()

# --- SIDEBAR ---
with st.sidebar:
    st.markdown("""
        <div style='text-align: center; padding: 20px;'>
            <h1 style='font-size: 40px;'>🏏</h1>
            <h2 style='color: #667eea;'>Pro Cricket League</h2>
        </div>
    """, unsafe_allow_html=True)
    
    page = st.radio(
        "Navigation",
        ["📺 Live Match", "📊 Statistics", "⚙️ Admin Panel", "📜 History"],
        index=0
    )
    
    st.divider()
    
    # Live match info in sidebar
    if not data["is_finished"]:
        st.info(f"**Current Match:** {data['team_a']} vs {data['team_b']}")
        st.info(f"**Innings:** {data['innings']}/2")
    else:
        st.success(f"**Last Match Winner:** {data['winner']}")

# --- MAIN CONTENT ---
if page == "⚙️ Admin Panel":
    st.markdown("<div class='main-header'><h1>⚙️ Admin Control Room</h1></div>", unsafe_allow_html=True)
    
    if not st.session_state["authenticated"]:
        with st.form("login_form"):
            pwd = st.text_input("Admin PIN", type="password")
            submitted = st.form_submit_button("Login")
            if submitted and pwd == ADMIN_PIN:
                st.session_state["authenticated"] = True
                # Set persistent auth
                try:
                    st.query_params["auth"] = "admin"
                except Exception:
                    pass  # Fallback if query_params not available
                st.rerun()
            elif submitted:
                st.error("Invalid PIN")
    else:
        # Admin Header with Logout
        col_logout1, col_logout2 = st.columns([3, 1])
        with col_logout1:
            st.success("🔓 Admin Access Granted")
        with col_logout2:
            if st.button("🚪 LOGOUT", type="secondary", use_container_width=True):
                st.session_state["authenticated"] = False
                try:
                    st.query_params.clear()
                except Exception:
                    pass  # Fallback if query_params not available
                st.rerun()
        
        st.divider()
        
        # Debug Messages Section
        st.subheader("🔍 Debug Messages")
        if st.session_state.get("debug_messages"):
            st.write("**Recent Ball Submissions:**")
            for msg in st.session_state["debug_messages"][-10:]:  # Show last 10 messages
                st.write(f"• {msg}")
            if st.button("Clear Debug Messages"):
                st.session_state["debug_messages"] = []
                st.rerun()
        else:
            st.info("No debug messages yet. Submit some balls to see debug info.")
        
        # Undo Section at the top
        st.subheader("🔄 Undo Actions")
        action_history = st.session_state.get("action_history", [])
        
        if action_history:
            col_undo1, col_undo2 = st.columns([2, 1])
            with col_undo1:
                st.info(f"📝 Recent Actions: {len(action_history)} available")
                # Show last 4 actions
                recent_actions = action_history[-4:] if len(action_history) >= 4 else action_history
                for i, action in enumerate(reversed(recent_actions)):
                    st.write(f"{i+1}. {action['description']} - {action['timestamp']}")
            
            with col_undo2:
                if st.button("↩️ UNDO LAST ACTION", type="secondary", use_container_width=True):
                    success, message = CricketDataManager.undo_last_action()
                    if success:
                        st.success(message)
                        st.rerun()
                    else:
                        st.error(message)
        else:
            st.info("ℹ️ No actions to undo")
        
        st.divider()
        
        tabs = st.tabs(["🏗️ Team Setup", "🏏 Match Control", "📊 Advanced Stats", "🎮 Live Commentary"])
        
        with tabs[0]:
            col1, col2 = st.columns(2)
            
            with col1:
                st.subheader(f"⚔️ {data['team_a']} - Team")
                with st.form("team_a_form"):
                    new_player = st.text_input(f"Add Player to {data['team_a']}")
                    if st.form_submit_button("➕ Add Player"):
                        if new_player and new_player not in data["team_a_squad"]:
                            data["team_a_squad"].append(new_player)
                            CricketDataManager.save_data(data, "ADD_PLAYER", f"Added {new_player} to {data['team_a']}")
                            st.success(f"Added {new_player} to {data['team_a']}")
                            st.rerun()
                
                # Display team A squad
                for player in data["team_a_squad"]:
                    col_a1, col_a2 = st.columns([4, 1])
                    with col_a1:
                        st.write(f"• {player}")
                    with col_a2:
                        if st.button("❌", key=f"del_a_{player}"):
                            data["team_a_squad"].remove(player)
                            CricketDataManager.save_data(data, "DELETE_PLAYER", f"Removed {player} from {data['team_a']}")
                            st.rerun()
            
            with col2:
                st.subheader(f"⚔️ {data['team_b']} - Team")
                with st.form("team_b_form"):
                    new_player = st.text_input(f"Add Player to {data['team_b']}")
                    if st.form_submit_button("➕ Add Player"):
                        if new_player and new_player not in data["team_b_squad"]:
                            data["team_b_squad"].append(new_player)
                            CricketDataManager.save_data(data, "ADD_PLAYER", f"Added {new_player} to {data['team_b']}")
                            st.success(f"Added {new_player} to {data['team_b']}")
                            st.rerun()
                
                # Display team B squad
                for player in data["team_b_squad"]:
                    col_b1, col_b2 = st.columns([4, 1])
                    with col_b1:
                        st.write(f"• {player}")
                    with col_b2:
                        if st.button("❌", key=f"del_b_{player}"):
                            data["team_b_squad"].remove(player)
                            CricketDataManager.save_data(data, "DELETE_PLAYER", f"Removed {player} from {data['team_b']}")
                            st.rerun()
            
            st.divider()
            
            # Match settings
            with st.expander("⚙️ Match Settings", expanded=True):
                col_set1, col_set2, col_set3 = st.columns(3)
                with col_set1:
                    new_team_a = st.text_input("Team A Name", value=data["team_a"])
                with col_set2:
                    new_team_b = st.text_input("Team B Name", value=data["team_b"])
                with col_set3:
                    max_overs = st.number_input("Overs per innings", min_value=1, max_value=50, value=data["max_overs"])
                
                if st.button("Update Match Settings", use_container_width=True):
                    data["team_a"] = new_team_a
                    data["team_b"] = new_team_b
                    data["max_overs"] = max_overs
                    CricketDataManager.save_data(data, "SETTINGS_UPDATE", "Updated match settings")
                    st.success("Settings Updated!")
                    st.rerun()
        
        with tabs[1]:
            col_control1, col_control2 = st.columns(2)
            
            with col_control1:
                st.subheader("🔄 Innings Control")
                if st.button("Start 2nd Innings", type="primary", use_container_width=True):
                    data["target"] = data["score"] + 1
                    data["score"] = 0
                    data["wickets"] = 0
                    data["balls"] = 0
                    data["overs"] = 0.0
                    data["innings"] = 2
                    data["out_players"] = []
                    data["batting_stats"] = {}
                    data["bowling_stats"] = {}
                    data["is_finished"] = False
                    data["winner"] = ""
                    data["partnership_runs"] = 0
                    data["partnership_balls"] = 0
                    add_match_event("INNINGS", f"2nd Innings started. Target: {data['target']}", {})
                    CricketDataManager.save_data(data, "START_2ND_INNINGS", f"Started 2nd innings with target {data['target']}")
                    st.rerun()
            
            with col_control2:
                st.subheader("🔄 Match Control")
                if st.button("Reset Match", type="secondary", use_container_width=True):
                    if os.path.exists(DB_FILE):
                        os.remove(DB_FILE)
                    # Clear ball_by_ball data and file
                    st.session_state["ball_by_ball"] = []
                    st.session_state["match_events"] = []
                    # Delete ball_by_ball.json file to clear circles
                    if os.path.exists("ball_by_ball.json"):
                        os.remove("ball_by_ball.json")
                    st.success("Match Reset Complete!")
                    st.rerun()
            
            st.divider()
            
            # Ball Entry Section
            if not data["is_finished"]:
                st.subheader("🎯 Ball Entry")
                
                batting_team = data["team_a_squad"] if data["innings"] == 1 else data["team_b_squad"]
                bowling_team = data["team_b_squad"] if data["innings"] == 1 else data["team_a_squad"]
                
                available_batsmen = [p for p in batting_team if p not in data["out_players"]]
                
                if len(available_batsmen) >= 2:
                    col_ball1, col_ball2, col_ball3 = st.columns(3)
                    
                    with col_ball1:
                        striker = st.selectbox("Striker", available_batsmen, 
                                             index=available_batsmen.index(data["current_striker"]) if data["current_striker"] in available_batsmen else 0)
                    
                    with col_ball2:
                        non_striker_options = [p for p in available_batsmen if p != striker]
                        non_striker = st.selectbox("Non-Striker", non_striker_options,
                                                 index=non_striker_options.index(data["current_non_striker"]) if data["current_non_striker"] in non_striker_options else 0)
                    
                    with col_ball3:
                        bowler = st.selectbox("Bowler", bowling_team,
                                            index=bowling_team.index(data["current_bowler"]) if data["current_bowler"] in bowling_team else 0)
                    
                    # Ball result with advanced options
                    col_result1, col_result2 = st.columns(2)
                    
                    with col_result1:
                        ball_type = st.selectbox("Ball Type", ["Normal", "Wide", "No Ball", "Bye", "Leg Bye"])
                    
                    with col_result2:
                        if ball_type == "Normal":
                            runs = st.selectbox("Runs", [0, 1, 2, 3, 4, 6, "Wicket"])
                        else:
                            runs = st.selectbox("Runs", [0, 1, 2, 4])
                    
                    if st.button("Submit Ball", type="primary", use_container_width=True):
                        # Initialize stats if needed
                        if striker not in data["batting_stats"]:
                            data["batting_stats"][striker] = {"r": 0, "b": 0, "4s": 0, "6s": 0}
                        if bowler not in data["bowling_stats"]:
                            data["bowling_stats"][bowler] = {"o": 0.0, "w": 0, "r": 0, "balls": 0, "maidens": 0, "over_runs": 0}
                        
                        # Process the ball
                        is_wicket = (runs == "Wicket")
                        actual_runs = 0
                        
                        if ball_type == "Wide":
                            actual_runs = int(runs) + 1
                            data["extras"] += 1
                            data["score"] += actual_runs
                            data["bowling_stats"][bowler]["r"] += actual_runs
                            data["bowling_stats"][bowler]["over_runs"] = data["bowling_stats"][bowler].get("over_runs", 0) + actual_runs
                        elif ball_type == "No Ball":
                            actual_runs = int(runs) + 1
                            data["extras"] += 1
                            data["score"] += actual_runs
                            data["bowling_stats"][bowler]["r"] += actual_runs
                            data["bowling_stats"][bowler]["over_runs"] = data["bowling_stats"][bowler].get("over_runs", 0) + actual_runs
                            if not is_wicket:
                                data["batting_stats"][striker]["r"] += int(runs)
                                data["batting_stats"][striker]["b"] += 1
                                if int(runs) == 4:
                                    data["batting_stats"][striker]["4s"] += 1
                                elif int(runs) == 6:
                                    data["batting_stats"][striker]["6s"] += 1
                        elif ball_type in ["Bye", "Leg Bye"]:
                            actual_runs = int(runs)
                            data["extras"] += actual_runs
                            data["score"] += actual_runs
                            data["bowling_stats"][bowler]["over_runs"] = data["bowling_stats"][bowler].get("over_runs", 0) + actual_runs
                        elif is_wicket:
                            data["wickets"] += 1
                            data["out_players"].append(striker)
                            data["bowling_stats"][bowler]["w"] += 1
                            data["batting_stats"][striker]["b"] += 1
                            add_match_event("WICKET", f"{striker} is out! Bowled by {bowler}", {"batsman": striker, "bowler": bowler})
                        else:
                            actual_runs = int(runs)
                            data["score"] += actual_runs
                            
                            # Ensure striker exists in batting stats
                            if striker not in data["batting_stats"]:
                                data["batting_stats"][striker] = {"r": 0, "b": 0, "4s": 0, "6s": 0}
                            
                            data["batting_stats"][striker]["r"] += actual_runs
                            data["batting_stats"][striker]["b"] += 1
                            if actual_runs == 4:
                                data["batting_stats"][striker]["4s"] += 1
                                add_match_event("FOUR", f"{striker} hits a FOUR! {actual_runs} runs", {})
                            elif actual_runs == 6:
                                data["batting_stats"][striker]["6s"] += 1
                                add_match_event("SIX", f"{striker} hits a SIX! {actual_runs} runs", {})
                            
                            # Ensure bowler exists in bowling stats
                            if bowler not in data["bowling_stats"]:
                                data["bowling_stats"][bowler] = {"r": 0, "w": 0, "balls": 0}
                            
                            data["bowling_stats"][bowler]["r"] += actual_runs
                            data["bowling_stats"][bowler]["over_runs"] = data["bowling_stats"][bowler].get("over_runs", 0) + actual_runs
                        
                        # Update balls and overs (only for legal deliveries)
                        if ball_type not in ["Wide", "No Ball"]:
                            data["balls"] += 1
                            data["bowling_stats"][bowler]["balls"] += 1
                            
                            # Check for maiden over (over_runs == 0 means maiden)
                            if data["balls"] % 6 == 0 and data["balls"] > 0:
                                if data["bowling_stats"][bowler].get("over_runs", 0) == 0:
                                    data["bowling_stats"][bowler]["maidens"] = data["bowling_stats"][bowler].get("maidens", 0) + 1
                                # Reset over_runs for next over
                                data["bowling_stats"][bowler]["over_runs"] = 0
                            
                            # Update partnership
                            if not is_wicket:
                                data["partnership_runs"] += actual_runs
                                data["partnership_balls"] += 1
                        
                        # Create ball record for all ball types
                        current_balls = data["balls"]
                        ball_record = {
                            "over": current_balls // 6 + 1,
                            "ball": current_balls % 6 if current_balls % 6 != 0 else 6,
                            "bowler": bowler,
                            "striker": striker,
                            "runs": actual_runs,
                            "is_wicket": is_wicket,
                            "ball_type": ball_type
                        }
                        st.session_state["ball_by_ball"].append(ball_record)
                        # Save ball_by_ball to file for persistence
                        try:
                            with open("ball_by_ball.json", "w") as f:
                                json.dump(st.session_state["ball_by_ball"], f, indent=4)
                        except Exception as e:
                            # Only show error in admin panel
                            if page == "⚙️ Admin Panel":
                                st.error(f"⚠️ Could not save ball data: {e}")
                            # Continue without saving to file (data stays in session)
                        
                        data["overs"] = data["balls"] // 6 + (data["balls"] % 6) / 10
                        data["run_rate"] = calculate_run_rate(data["score"], data["balls"])
                        
                        # Check match end conditions
                        if data["innings"] == 2:
                            if data["score"] >= data["target"]:
                                data["is_finished"] = True
                                data["winner"] = data["team_b"]
                                add_match_event("MATCH_END", f"{data['team_b']} wins by {10 - data['wickets']} wickets!", {})
                                CricketDataManager.save_to_history(data)
                            elif data["wickets"] >= len(batting_team) - 1:  # All out
                                data["is_finished"] = True
                                data["winner"] = data["team_a"]
                                add_match_event("MATCH_END", f"{data['team_a']} wins by {data['target'] - data['score']} runs!", {})
                                CricketDataManager.save_to_history(data)
                            elif data["balls"] >= data["max_overs"] * 6:
                                data["is_finished"] = True
                                if data["score"] >= data["target"]:
                                    data["winner"] = data["team_b"]
                                else:
                                    data["winner"] = data["team_a"]
                                add_match_event("MATCH_END", f"{data['winner']} wins!", {})
                                CricketDataManager.save_to_history(data)
                        
                        # Update current players
                        data["current_striker"] = striker
                        data["current_non_striker"] = non_striker
                        data["current_bowler"] = bowler
                        
                        # Swap strike if runs are odd
                        if actual_runs % 2 == 1 and not is_wicket and ball_type not in ["Wide", "No Ball"]:
                            data["current_striker"], data["current_non_striker"] = data["current_non_striker"], data["current_striker"]
                            add_match_event("STRIKE", f"Strike swapped! {data['current_striker']} on strike", {})
                        
                        # End of over - swap strike
                        if data["balls"] % 6 == 0 and data["balls"] > 0:
                            data["current_striker"], data["current_non_striker"] = data["current_non_striker"], data["current_striker"]
                            add_match_event("OVER_END", f"Over {int(data['balls']/6)} completed. Strike swapped.", {})
                        
                        # Add commentary for the ball
                        if is_wicket:
                            comment = f"WICKET! {striker} is out!"
                        elif actual_runs == 0:
                            comment = f"No run. {bowler} to {striker}"
                        else:
                            comment = f"{actual_runs} run{'s' if actual_runs > 1 else ''}. {striker} scores"
                        
                        add_match_event("BALL", comment, ball_record)
                        
                        CricketDataManager.save_data(data, "BALL_SUBMITTED", f"Ball: {actual_runs} runs ({ball_type})")
                        st.rerun()
                
                else:
                    st.error("Not enough players available! Need at least 2 batsmen.")
            else:
                st.success(f"Match Complete! Winner: {data['winner']}")
        
        with tabs[2]:
            st.subheader("📊 Advanced Statistics")
            
            if data["batting_stats"] or data["bowling_stats"]:
                col_adv1, col_adv2 = st.columns(2)
                
                with col_adv1:
                    st.write("**Batting Stats with Strike Rates**")
                    bat_df = pd.DataFrame([
                        {
                            "Player": k,
                            "Runs": v["r"],
                            "Balls": v["b"],
                            "4s": v.get("4s", 0),
                            "6s": v.get("6s", 0),
                            "SR": round(v["r"] / v["b"] * 100 if v["b"] > 0 else 0, 2)
                        }
                        for k, v in data["batting_stats"].items()
                    ])
                    if not bat_df.empty:
                        st.dataframe(bat_df, use_container_width=True)
                    else:
                        st.info("No batting data available")
                
                with col_adv2:
                    st.write("**Bowling Stats with Economy**")
                    bowl_df = pd.DataFrame([
                        {
                            "Player": k,
                            "Overs": round(v["balls"] / 6 + (v["balls"] % 6) / 10, 1),
                            "Maidens": v.get("maidens", 0),
                            "Runs": v["r"],
                            "Wkts": v["w"],
                            "Econ": round(v["r"] / (v["balls"] / 6) if v["balls"] > 0 else 0, 2)
                        }
                        for k, v in data["bowling_stats"].items()
                    ])
                    if not bowl_df.empty:
                        st.dataframe(bowl_df, use_container_width=True)
                    else:
                        st.info("No bowling data available")
                
                # Visualization
                if not bat_df.empty:
                    fig = go.Figure(data=[
                        go.Bar(name='Runs', x=bat_df['Player'], y=bat_df['Runs'], marker_color='#FF6B6B'),
                        go.Bar(name='Balls', x=bat_df['Player'], y=bat_df['Balls'], marker_color='#4ECDC4')
                    ])
                    fig.update_layout(
                        title="Batting Performance",
                        barmode='group',
                        template='plotly_dark',
                        xaxis_title="Batsmen",
                        yaxis_title="Count"
                    )
                    st.plotly_chart(fig, use_container_width=True)
                
                # Worm graph for ball-by-ball progression
                if st.session_state["ball_by_ball"]:
                    st.subheader("📈 Match Progression")
                    cumulative_runs = []
                    ball_numbers = []
                    total = 0
                    for i, ball in enumerate(st.session_state["ball_by_ball"]):
                        if not ball.get('is_wicket', False):
                            total += ball.get('runs', 0)
                        cumulative_runs.append(total)
                        ball_numbers.append(i + 1)
                    
                    fig2 = go.Figure()
                    fig2.add_trace(go.Scatter(
                        x=ball_numbers,
                        y=cumulative_runs,
                        mode='lines+markers',
                        name='Runs',
                        line=dict(color='#FFD93D', width=3),
                        marker=dict(size=6)
                    ))
                    fig2.update_layout(
                        title="Run Progression (Ball by Ball)",
                        xaxis_title="Balls",
                        yaxis_title="Total Runs",
                        template='plotly_dark'
                    )
                    st.plotly_chart(fig2, use_container_width=True)
            else:
                st.info("No statistics available yet")
        
        with tabs[3]:
            st.subheader("📝 Live Commentary")
            
            # Display recent events
            if st.session_state["match_events"]:
                for event in reversed(st.session_state["match_events"][-15:]):
                    if event["type"] == "WICKET":
                        st.markdown(f"<div class='commentary-box' style='border-left-color: #ff0000;'>🔴 {event['time']} - {event['description']}</div>", unsafe_allow_html=True)
                    elif event["type"] == "FOUR":
                        st.markdown(f"<div class='commentary-box' style='border-left-color: #00ff00;'>🟢 {event['time']} - {event['description']}</div>", unsafe_allow_html=True)
                    elif event["type"] == "SIX":
                        st.markdown(f"<div class='commentary-box' style='border-left-color: #ffff00;'>🟡 {event['time']} - {event['description']}</div>", unsafe_allow_html=True)
                    elif event["type"] == "OVER_END":
                        st.markdown(f"<div class='commentary-box' style='border-left-color: #00ffff;'>🔵 {event['time']} - {event['description']}</div>", unsafe_allow_html=True)
                    else:
                        st.markdown(f"<div class='commentary-box'>⚪ {event['time']} - {event['description']}</div>", unsafe_allow_html=True)
            else:
                st.info("No commentary available yet")
            
            # Add custom commentary
            with st.form("commentary_form"):
                custom_comment = st.text_area("Add Custom Commentary", placeholder="Enter your commentary here...")
                if st.form_submit_button("Add Commentary"):
                    add_match_event("COMMENTARY", custom_comment, {})
                    st.success("Commentary added!")
                    st.rerun()

elif page == "📺 Live Match":
    # --- LIVE MATCH VIEWER PAGE ---
    
    if data["is_finished"] and data["winner"]:
        st.markdown(f"<div class='winner-box'>🏆 {data['winner'].upper()} WON THE MATCH! 🏆</div>", unsafe_allow_html=True)
        st.balloons()
        st.snow()
    
    # Match Header
    st.markdown(f"""
        <div class='main-header'>
            <h1>{data['team_a']} vs {data['team_b']}</h1>
            <p style='font-size: 20px;'>Live from Pro Cricket Stadium • {data['max_overs']} Overs Match</p>
        </div>
    """, unsafe_allow_html=True)
    
    # Main Score Display
    batting_team = data["team_a"] if data["innings"] == 1 else data["team_b"]
    bowling_team = data["team_b"] if data["innings"] == 1 else data["team_a"]
    
    # Calculate required runs if in second innings
    target_text = ""
    required_run_rate = 0
    if data["innings"] == 2 and not data["is_finished"] and data["target"] > 0:
        runs_needed = data["target"] - data["score"]
        balls_left = (data["max_overs"] * 6) - data["balls"]
        wickets_left = 10 - data["wickets"]
        if runs_needed > 0 and balls_left > 0:
            required_run_rate = (runs_needed / balls_left) * 6
            target_text = f"""
                <div class='target-box'>
                    🎯 TARGET: {data['target']} | NEED {runs_needed} RUNS IN {balls_left} BALLS
                    <br>Required Run Rate: {required_run_rate:.2f} | Current Run Rate: {data['run_rate']:.2f} | WKTS LEFT: {wickets_left}
                </div>
            """
    
    st.markdown(f"""
        <div class="main-score">
            <h2 style='color: #fff;'>{batting_team} - Batting</h2>
            <h1 style='font-size: 100px; margin: 10px 0;'>{data['score']}/{data['wickets']}</h1>
            <p style='font-size: 24px;'>Overs: {data['overs']:.1f} / {data['max_overs']}</p>
            <p style='font-size: 20px;'>Current Run Rate: {data['run_rate']:.2f}</p>
        </div>
    """, unsafe_allow_html=True)
    
    # Display over balls separately after the main score banner
    try:
        over_balls_html = generate_over_balls_display(data)
        if over_balls_html:
            st.markdown(over_balls_html, unsafe_allow_html=True)
    except Exception as e:
        # Silent fallback for viewer page
        if page == "⚙️ Admin Panel":
            st.error(f"⚠️ Over display error: {e}")
        else:
            # Show simple fallback for viewer
            st.markdown("""
            <div style="background: #333; padding: 10px; border-radius: 10px; text-align: center; color: #ccc; margin: 10px 0;">
                ⚠️ Live score temporarily unavailable
            </div>
            """, unsafe_allow_html=True)
    
    # Display target box separately if it exists
    if target_text:
        st.markdown(target_text, unsafe_allow_html=True)
    
    # Current Players Display
    if not data["is_finished"]:
        st.markdown("### 🎯 Current Players")
        col_p1, col_p2, col_p3, col_p4 = st.columns(4)
        
        # Get striker stats
        striker_stats = data['batting_stats'].get(data['current_striker'], {})
        striker_runs = striker_stats.get('r', 0)
        striker_balls = striker_stats.get('b', 0)
        striker_sr = round(striker_runs / striker_balls * 100, 2) if striker_balls > 0 else 0
        
        with col_p1:
            st.markdown(f"""
                <div class="player-box">
                    <h3>🏏 Striker</h3>
                    <h2>{data['current_striker']}</h2>
                    <p>{striker_runs} runs from {striker_balls} balls</p>
                    <p>SR: {striker_sr}</p>
                </div>
            """, unsafe_allow_html=True)
        
        # Get non-striker stats
        non_striker_stats = data['batting_stats'].get(data['current_non_striker'], {})
        non_striker_runs = non_striker_stats.get('r', 0)
        non_striker_balls = non_striker_stats.get('b', 0)
        non_striker_sr = round(non_striker_runs / non_striker_balls * 100, 2) if non_striker_balls > 0 else 0
        
        with col_p2:
            st.markdown(f"""
                <div class="player-box">
                    <h3>🏃 Non-Striker</h3>
                    <h2>{data['current_non_striker']}</h2>
                    <p>{non_striker_runs} runs from {non_striker_balls} balls</p>
                </div>
            """, unsafe_allow_html=True)
        
        # Get bowler stats
        bowler_stats = data['bowling_stats'].get(data['current_bowler'], {})
        bowler_wickets = bowler_stats.get('w', 0)
        bowler_runs = bowler_stats.get('r', 0)
        bowler_balls = bowler_stats.get('balls', 0)
        bowler_overs = round(bowler_balls / 6 + (bowler_balls % 6) / 10, 1)
        
        with col_p3:
            st.markdown(f"""
                <div class="player-box">
                    <h3>🎯 Bowler</h3>
                    <h2>{data['current_bowler']}</h2>
                    <p>{bowler_wickets}/{bowler_runs} in {bowler_overs} overs</p>
                </div>
            """, unsafe_allow_html=True)
        
        with col_p4:
            partnership = f"{data['partnership_runs']} ({data['partnership_balls']})"
            st.markdown(f"""
                <div class="player-box">
                    <h3>🤝 Partnership</h3>
                    <h2>{partnership}</h2>
                </div>
            """, unsafe_allow_html=True)
    
    # Run Rate Indicator for second innings
    if data["innings"] == 2 and data["target"] > 0:
        progress = min(100, (data["score"] / data["target"]) * 100)
        st.markdown(f"""
            <div class="run-rate-indicator">
                <div class="run-rate-fill" style="width: {progress}%;"></div>
            </div>
            <p style='text-align: center;'>Progress towards target: {progress:.1f}%</p>
        """, unsafe_allow_html=True)
    
    st.divider()
    
    # Detailed Stats Tabs
    tab_match, tab_bat, tab_bowl, tab_squad, tab_commentary = st.tabs(["📊 Match Stats", "🏏 Batting", "🎯 Bowling", "👥 Team", "📝 Commentary"])
    
    with tab_match:
        col_info1, col_info2 = st.columns(2)
        
        with col_info1:
            st.subheader("📋 Match Information")
            info_data = {
                "Teams": f"{data['team_a']} vs {data['team_b']}",
                "Batting Team": f"{batting_team}",
                "Overs Left": f"{data['max_overs'] - data['overs']:.1f}",
                "Wickets in Hand": f"{10 - data['wickets']}",
                "Current Run Rate": f"{data['run_rate']:.2f}",
                "Extra Runs": f"{data['extras']}"
            }
            if data["innings"] == 2:
                info_data["Target Score"] = f"{data['target']}"
                info_data["Required Run Rate"] = f"{required_run_rate:.2f}"
            
            df_info = pd.DataFrame(info_data.items(), columns=["Match Details", "Value"])
            st.table(df_info)
        
        with col_info2:
            st.subheader("Recent Events")
            if st.session_state["match_events"]:
                for event in st.session_state["match_events"][-5:]:
                    st.info(f"{event['time']} - {event['description']}")
            else:
                st.info("No recent events")
    
    with tab_bat:
        st.subheader(f"🏏 {batting_team} - Batting Scorecard")
        
        batting_data = []
        for player, stats in data["batting_stats"].items():
            strike_rate = (stats["r"] / stats["b"] * 100) if stats["b"] > 0 else 0
            batting_data.append({
                "Batsman": player,
                "R": stats["r"],
                "B": stats["b"],
                "4s": stats.get("4s", 0),
                "6s": stats.get("6s", 0),
                "SR": round(strike_rate, 2)
            })
        
        if batting_data:
            df_bat = pd.DataFrame(batting_data)
            st.dataframe(df_bat, use_container_width=True)
        else:
            st.info("No batting data available")
    
    with tab_bowl:
        st.subheader(f"🎯 {bowling_team} - Bowling Scorecard")
        
        bowling_data = []
        for player, stats in data["bowling_stats"].items():
            overs = stats["balls"] // 6 + (stats["balls"] % 6) / 10
            economy = stats["r"] / overs if overs > 0 else 0
            bowling_data.append({
                "Bowler": player,
                "O": round(overs, 1),
                "M": stats.get("maidens", 0),
                "R": stats["r"],
                "W": stats["w"],
                "Econ": round(economy, 2)
            })
        
        if bowling_data:
            bowl_df = pd.DataFrame(bowling_data)
            st.dataframe(bowl_df, use_container_width=True)
        else:
            st.info("No bowling data available")
    
    with tab_squad:
        col_sq1, col_sq2 = st.columns(2)
        
        with col_sq1:
            st.subheader(f"{batting_team} Team")
            batting_squad = data["team_a_squad"] if data["innings"] == 1 else data["team_b_squad"]
            for player in batting_squad:
                if player in data["out_players"]:
                    st.markdown(f"~~{player}~~ ❌")
                elif player in [data["current_striker"], data["current_non_striker"]]:
                    st.markdown(f"**{player}** 🏏 (Batting)")
                else:
                    st.write(f"• {player}")
        
        with col_sq2:
            st.subheader(f"{bowling_team} Team")
            bowling_squad = data["team_b_squad"] if data["innings"] == 1 else data["team_a_squad"]
            for player in bowling_squad:
                if player == data["current_bowler"]:
                    st.markdown(f"**{player}** 🎯 (Bowling)")
                else:
                    st.write(f"• {player}")
    
    with tab_commentary:
        st.subheader("📝 Live Commentary")
        if st.session_state["match_events"]:
            for event in reversed(st.session_state["match_events"][-20:]):
                if event["type"] == "WICKET":
                    st.error(f"{event['time']} - {event['description']}")
                elif event["type"] in ["FOUR", "SIX"]:
                    st.success(f"{event['time']} - {event['description']}")
                else:
                    st.info(f"{event['time']} - {event['description']}")
        else:
            st.info("No commentary available")

elif page == "📊 Statistics":
    st.markdown("<div class='main-header'><h1>📊 Match Statistics</h1></div>", unsafe_allow_html=True)
    
    col_stat1, col_stat2 = st.columns(2)
    
    with col_stat1:
        st.subheader("🏆 Highest Run Scorers")
        if data["batting_stats"]:
            top_batsmen = sorted(data["batting_stats"].items(), key=lambda x: x[1]["r"], reverse=True)[:5]
            for player, stats in top_batsmen:
                strike_rate = (stats['r'] / stats['b'] * 100) if stats['b'] > 0 else 0
                st.metric(
                    player, 
                    f"{stats['r']} runs", 
                    f"{stats['b']} balls, SR: {strike_rate:.1f}"
                )
        else:
            st.info("No batting data")
    
    with col_stat2:
        st.subheader("🎯 Best Bowlers")
        if data["bowling_stats"]:
            top_bowlers = sorted(data["bowling_stats"].items(), key=lambda x: x[1]["w"], reverse=True)[:5]
            for player, stats in top_bowlers:
                overs = stats['balls'] // 6 + (stats['balls'] % 6) / 10
                economy = stats['r'] / overs if overs > 0 else 0
                st.metric(
                    player, 
                    f"{stats['w']} wickets", 
                    f"{stats['r']} runs, Econ: {economy:.1f}"
                )
        else:
            st.info("No bowling data")
    
    # Match Summary
    st.subheader("📊 Innings Summary")
    summary_data = {
        "Runs Scored": f"{data['score']}",
        "Wickets Lost": f"{data['wickets']}",
        "Overs Completed": f"{data['overs']:.1f}",
        "Current Run Rate": f"{data['run_rate']:.2f}",
        "Extras (Wd/Nb/Bye/Leg Bye)": f"{data['extras']}",
        "Current Partnership": f"{data['partnership_runs']} runs ({data['partnership_balls']} balls)"
    }
    
    df_summary = pd.DataFrame(summary_data.items(), columns=["Innings Stats", "Value"])
    st.table(df_summary)
    
    # Ball-by-ball analysis
    if st.session_state["ball_by_ball"]:
        st.subheader("🎯 Ball by Ball Analysis")
        ball_df = pd.DataFrame(st.session_state["ball_by_ball"])
        st.dataframe(ball_df, use_container_width=True)

elif page == "📜 History":
    st.markdown("<div class='main-header'><h1>📜 Match History</h1></div>", unsafe_allow_html=True)
    
    match_history = CricketDataManager.load_history()
    
    if match_history:
        for match in reversed(match_history[-10:]):  # Show last 10 matches
            with st.expander(f"🏏 Match {match['match_id']}: {match['teams']} - {match['date']}"):
                col_hist1, col_hist2 = st.columns(2)
                
                with col_hist1:
                    st.success(f"**Winner:** {match['winner']}")
                    st.info(f"**Final Score:** {match['score']}")
                    st.info(f"**Man of the Match:** {match.get('man_of_match', 'TBD')}")
                
                with col_hist2:
                    st.write("**Top Performers**")
                    if match.get('batting_stats'):
                        if match['batting_stats']:
                            top_bat = max(match['batting_stats'], key=lambda x: x['runs'])
                            st.write(f"🏏 Best Bat: {top_bat['player']} - {top_bat['runs']}({top_bat['balls']}) SR: {top_bat['strike_rate']}")
                    
                    if match.get('bowling_stats'):
                        if match['bowling_stats']:
                            top_bowl = max(match['bowling_stats'], key=lambda x: x['wickets'])
                            st.write(f"🎯 Best Bowl: {top_bowl['player']} - {top_bowl['wickets']}/{top_bowl['runs']} Econ: {top_bowl['economy']}")
                
                # Detailed stats in tabs
                tab_hist_bat, tab_hist_bowl = st.tabs(["Batting Details", "Bowling Details"])
                
                with tab_hist_bat:
                    if match.get('batting_stats'):
                        df_hist_bat = pd.DataFrame(match['batting_stats'])
                        st.dataframe(df_hist_bat, use_container_width=True)
                    else:
                        st.info("No batting stats available")
                
                with tab_hist_bowl:
                    if match.get('bowling_stats'):
                        df_hist_bowl = pd.DataFrame(match['bowling_stats'])
                        st.dataframe(df_hist_bowl, use_container_width=True)
                    else:
                        st.info("No bowling stats available")
    else:
        st.info("No match history available yet. Complete a match to see history!")

# Auto-refresh for live match page with optimization
if page == "📺 Live Match" and not data["is_finished"]:
    # Rate limiting to prevent infinite refresh loops
    current_time = time.time()
    last_rerun = st.session_state.get("last_rerun", 0)
    
    # Only refresh if 5 seconds have passed since last rerun
    if current_time - st.session_state["last_update"] > 5 and current_time - last_rerun > 6:
        st.session_state["last_update"] = current_time
        st.session_state["last_rerun"] = current_time
        time.sleep(0.1)  # Small delay to prevent multiple refreshes
        st.rerun()
    elif current_time - st.session_state["last_update"] <= 5:
        # Update time but don't rerun (prevents rapid refreshes)
        st.session_state["last_update"] = current_time
