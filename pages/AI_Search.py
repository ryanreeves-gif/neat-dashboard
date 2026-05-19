import streamlit as st
import pandas as pd
import requests
import time

# 1. Config & Corporate Theme
st.set_page_config(page_title="Neat | AI Search", layout="wide", page_icon="🤖")
st.markdown(
    """
    <style>
    /* Hide default Streamlit branding and raw file navigation */
    #MainMenu {visibility: hidden;} footer {visibility: hidden;} header {visibility: hidden;}
    [data-testid="stSidebarNav"] {display: none !important;}
    
    /* Sleek Corporate Action Card */
    .action-card {
        background-color: #15171c; 
        border: 1px solid #2a2d37;
        border-left: 5px solid #00d2b4; 
        padding: 1.5rem; 
        border-radius: 8px; 
        margin-top: 1rem; 
        margin-bottom: 1.5rem;
        color: white;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }
    .stTextInput input {background-color: #15171c; color: white; border: 1px solid #2a2d37;}
    .stTextInput input:focus {border: 1px solid #00d2b4; box-shadow: none;}
    
    /* Custom Technical Readout Box */
    .tech-box {
        background-color: #1a1c23;
        border: 1px dashed #555;
        padding: 1rem;
        border-radius: 5px;
        margin-top: 1rem;
        font-family: monospace;
        font-size: 0.9rem;
        color: #a0aabf;
    }
    .tech-box b { color: #00d2b4; }
    </style>
    """, unsafe_allow_html=True
)

# 2. Data Loading (Synced Logic)
@st.cache_data(ttl=600)
def load_data():
    url = "https://docs.google.com/spreadsheets/d/1bconB0u70BZv0aTblhhEA8_q56rlO6KAU1RG0P8yOjE/export?format=csv"
    data = pd.read_csv(url)
    data.columns = data.columns.str.strip()
    data['Timestamp'] = pd.to_datetime(data['Timestamp'], errors='coerce')
    platform_mapping = {
        'msteams': 'Microsoft Teams', 'zoom': 'Zoom', 'google_meet': 'Google Meet',
        'apphub': 'Neat App Hub', 'usb': 'BYOD (USB Mode)', 'avos': 'App Hub Partner', 'none': 'Unprovisioned'
    }
    data['Platform'] = data['Platform'].replace(platform_mapping)
    return data

df = load_data()
valid_dates = df['Timestamp'].dropna()

if valid_dates.empty:
    st.error("No valid timestamps found.")
    st.stop()

# 3. GLOBALLY SYNCED SIDEBAR & BRANDED NAVIGATION
if 'saved_loc' not in st.session_state: st.session_state['saved_loc'] = "All"
if 'saved_dates' not in st.session_state: st.session_state['saved_dates'] = (valid_dates.min().date(), valid_dates.max().date())
if 'saved_rooms' not in st.session_state: st.session_state['saved_rooms'] = []
if 'ai_query' not in st.session_state: st.session_state['ai_query'] = ""

def save_selections():
    st.session_state['saved_loc'] = st.session_state['loc_filter']
    st.session_state['saved_dates'] = st.session_state['date_filter']
    st.session_state['saved_rooms'] = st.session_state['room_filter']

with st.sidebar:
    st.markdown("<h1 style='color: #00d2b4; font-size: 3.5rem; margin-bottom: 0; padding-bottom: 0; line-height: 1;'>neat.</h1>", unsafe_allow_html=True)
    st.markdown("<p style='color: #888; font-size: 0.9rem; font-weight: 600; letter-spacing: 1px; margin-top: 0; margin-bottom: 30px;'>ENTERPRISE OPERATIONS</p>", unsafe_allow_html=True)
    
    st.markdown("<p style='color: #00d2b4; font-size: 0.8rem; font-weight: bold; margin-bottom: 5px;'>MENU</p>", unsafe_allow_html=True)
    st.page_link("app.py", label="Analytics", icon="📊")
    st.page_link("pages/Administration.py", label="Admin", icon="🛠️")
    st.page_link("pages/AI_Search.py", label="AI Search", icon="🤖")
    
    st.markdown("---")
    st.markdown("<p style='color: #00d2b4; font-size: 0.8rem; font-weight: bold; margin-bottom: 5px;'>GLOBAL FILTERS</p>", unsafe_allow_html=True)
    loc_opts = ["All"] + sorted(df['Location'].dropna().unique().tolist())
    loc_sel = st.selectbox("📍 Location", loc_opts, index=loc_opts.index(st.session_state['saved_loc']), key="loc_filter", on_change=save_selections)
    date_sel = st.date_input("📅 Date Range", value=st.session_state['saved_dates'], key="date_filter", on_change=save_selections)
    room_opts = sorted(df['Room Name'].dropna().unique().tolist())
    room_sel = st.multiselect("🚪 Rooms", room_opts, default=st.session_state['saved_rooms'], key="room_filter", on_change=save_selections)
    
    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("🔄 Refresh Telemetry", use_container_width=True, type="primary"):
        st.cache_data.clear()
        st.rerun()

# 4. Filter Logic
mask = df.copy()
if isinstance(date_sel, tuple) and len(date_sel) == 2:
    mask = mask[(mask['Timestamp'].dt.date >= date_sel[0]) & (mask['Timestamp'].dt.date <= date_sel[1])]
elif isinstance(date_sel, tuple) and len(date_sel) == 1:
    mask = mask[mask['Timestamp'].dt.date == date_sel[0]]
else:
    mask = mask[mask['Timestamp'].dt.date == date_sel]

if loc_sel != "All": mask = mask[mask['Location'] == loc_sel]
if room_sel: mask = mask[mask['Room Name'].isin(room_sel)]
snap = mask.sort_values('Timestamp').drop_duplicates('Room Name', keep='last')

# 5. Dashboard UI
st.title("🤖 AI Insights & Workflows")
st.write("Execute plain-English intent parameters to activate building intelligence layers and remote API pipelines.")

# --- THE COMMAND CENTER MATRIX ---
st.markdown("<p style='color: #00d2b4; font-size: 0.85rem; font-weight: bold; letter-spacing: 1px; margin-bottom: 10px;'>SUGGESTED OPERATIONAL SCENARIOS</p>", unsafe_allow_html=True)
btn_col1, btn_col2, btn_col3, btn_col4 = st.columns(4)

with btn_col1:
    if st.button("🔍 Run Climate Waste Audit", use_container_width=True):
        st.session_state['ai_query'] = "Analyze climate anomalies and find hot empty rooms"
with btn_col2:
    if st.button("🚪 Check Real Estate Efficiency", use_container_width=True):
        st.session_state['ai_query'] = "Analyze room sizing and structural optimization strategy"
with btn_col3:
    if st.button("🔌 Triage Hardware Breaches", use_container_width=True):
        st.session_state['ai_query'] = "Show me offline devices across the fleet"
with btn_col4:
    if st.button("🌬️ Review App Hub Deployments", use_container_width=True):
        st.session_state['ai_query'] = "Identify spaces running partner software modules"

st.write("<br>", unsafe_allow_html=True)

# Main query search bar locked to session state
query = st.text_input("💬 Ask the Assistant:", value=st.session_state['ai_query'], placeholder="Click an action button above or type your own query...")

if query:
    q = query.lower()
    
    # --- ENTERPRISE REASONING LOG (WOW FACTOR) ---
    with st.status("🧠 Agent Reasoning Cycle Initiated...", expanded=True) as status:
        st.write("1. Parsing natural language intent structure...")
        time.sleep(0.4)
        st.write("2. Querying Neat Pulse edge graph and extracting real-time IoT matrix...")
        time.sleep(0.5)
        st.write("3. Running heuristic correlation rules across data clusters...")
        time.sleep(0.4)
        status.update(label="✅ Analysis Complete. Insights Generated.", state="complete")
    
    # -----------------------------------------------
    # SCENARIO A: CLIMATE CONTROLS (HOT / COLD)
    # -----------------------------------------------
    if any(word in q for word in ["hot", "cold", "temp", "climate", "hvac"]):
        is_cold_search = "cold" in q or "overcool" in q or "freeze" in q
        if is_cold_search:
            waste_rooms = snap[(snap['Temperature'] < 19.0) & (snap['Occupancy'] == 0)]
            issue_text = "overcooling"
        else:
            waste_rooms = snap[(snap['Temperature'] > 22.0) & (snap['Occupancy'] == 0)]
            issue_text = "overheating"
        
        if not waste_rooms.empty:
            st.error(f"🚨 Identified {len(waste_rooms)} empty room(s) currently {issue_text} and causing HVAC waste:")
            st.dataframe(waste_rooms[['Room Name', 'Location', 'Temperature', 'Occupancy']].style.format({'Temperature': '{:.1f}°C'}), hide_index=True, use_container_width=True)
            
            st.markdown(f"<div class='action-card'><b>AI Recommendation:</b> We have detected empty rooms that are currently {issue_text}, causing energy waste. Adjust parameters via ServiceNow integration or execute an absolute HVAC cutoff below.</div>", unsafe_allow_html=True)
            
            col1, col2, col3 = st.columns([1.5, 1, 1])
            with col1: target_temp = st.slider("Select Target Temperature", 18.0, 26.0, 21.0, 0.5, format="%f°C")
            with col2:
                st.write("<br>", unsafe_allow_html=True)
                if st.button(f"🌡️ Adjust to {target_temp}°C", type="secondary"):
                    with st.spinner("Writing to BMS..."):
                        time.sleep(1.2)
                        st.success("✅ Success! Target parameters sent.")
                        st.markdown(f"<div class='tech-box'><b>[BACnet IP FRAME]</b> Outbound REST packet converted to BACnet Priority 8 object frame override at Niagara station server. Target setpoint synchronized to {target_temp}°C.</div>", unsafe_allow_html=True)
            with col3:
                st.write("<br>", unsafe_allow_html=True)
                if st.button("🛑 Turn OFF HVAC", type="primary"):
                    with st.spinner("Powering down..."):
                        time.sleep(1.2)
                        st.success("✅ Success! HVAC set to Eco Mode.")
                        st.markdown("<div class='tech-box'><b>[BACnet IP FRAME]</b> Relinquished priority frame. Dispatched point command: <code>Unoccupied_Economy_State = True</code> to underlying VAV zones.</div>", unsafe_allow_html=True)
        else:
            st.success("✅ All empty rooms are operating inside optimal, green thermal boundaries.")

    # -----------------------------------------------
    # SCENARIO B: NEW SPACE OPTIMIZATION (C-SUITE FOCUS)
    # -----------------------------------------------
    elif any(word in q for word in ["size", "real estate", "efficiency", "structural", "utilization"]):
        st.info("📊 Executing Fleet-Wide Square Footage Optimization Audit...")
        
        # Simulating finding large rooms with low avg occupancy
        large_rooms = snap[snap['Capacity'] > 8]
        
        st.markdown("""
        <div class='action-card'>
            <h3>🏢 Real Estate Strategy Briefing: Conference Room Underutilization</h3>
            Our algorithms cross-referenced room capacity layout metrics against actual active usage density over the target period.
            <br><br>
            <b>Core Finding:</b> Your large boardrooms (9-20 max capacity) are currently experiencing a <b>78% space-efficiency defecit</b>. 
            Meetings in these rooms average only <b>2.3 participants</b>, meaning you are paying premium real estate costs to heat, cool, and light empty square footage.
        </div>
        """, unsafe_allow_html=True)
        
        col1, col2 = st.columns(2)
        with col1:
            st.write("#### ⚠️ Top Structural Waste Offenders")
            st.dataframe(large_rooms[['Room Name', 'Location', 'Capacity']], hide_index=True, use_container_width=True)
            
        with col2:
            st.write("#### 🛠️ AI Realignment Blueprint")
            st.success("💡 <b>Structural ROI Recommendation:</b>")
            st.write("Partition the underutilized 'London Board 32' and 'Oslo Executive' spaces into **3 separate agile huddle rooms (1-4 cap)**.")
            st.write("This realignment increases overall building collaboration capacity by **300%** and captures an estimated **£42,000/year** in reclaimed real estate utility value.")
            
            if st.button("📋 Export Real Estate Blueprint to ServiceNow Facilities", type="primary"):
                with st.spinner("Generating Facilities Change Request..."):
                    time.sleep(1.5)
                    st.success("✅ Change Request Ticket Created: CR-2026-9982 dispatched to Corporate Architecture Planning.")

    # -----------------------------------------------
    # SCENARIO C: OFFLINE TRIAGE
    # -----------------------------------------------
    elif any(word in q for word in ["offline", "down", "reboot", "hardware"]):
        offline = snap[snap['Device Status'] == 'Offline']
        if not offline.empty:
            st.error(f"🚨 Found {len(offline)} offline device(s) in current scope.")
            st.dataframe(offline[['Room Name', 'Location', 'Notes']], hide_index=True, use_container_width=True)
            st.markdown("<div class='action-card'><b>AI Recommendation:</b> Network link drops detected. Suggest remote hardware reset via managed port power cycle.</div>", unsafe_allow_html=True)
            
            if st.button("🔌 Execute Remote Reboot (Simulated API)", type="primary"):
                with st.spinner("Authenticating with Neat API..."):
                    time.sleep(1.2)
                    st.success("API Command Sent: PoE network switch frame cycled successfully.")
        else:
            st.success("✅ Fleet infrastructure map reporting 100% stable online connectivity.")

    # -----------------------------------------------
    # SCENARIO D: PLATFORMS
    # -----------------------------------------------
    elif any(word in q for word in ["app hub", "partner", "avos", "software", "modules"]):
        partners = snap[snap['Platform'] == 'App Hub Partner']
        st.info(f"Found {len(partners)} specialized App Hub Partner spaces operating custom workplace software ecosystems.")
        st.dataframe(partners[['Room Name', 'Location', 'Platform']], hide_index=True, use_container_width=True)
        st.markdown("<div class='action-card'><b>Proactive Suggestion:</b> Ensure these endpoints are flagged on separate VLAN profiles to maximize local software telemetry performance.</div>", unsafe_allow_html=True)

    else:
        st.write("System core engine online. Select an operational scenario matrix item above or analyze specific fleet vectors.")
