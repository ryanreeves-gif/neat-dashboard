import streamlit as st
import pandas as pd
import plotly.express as px

# 1. Config & Theme
st.set_page_config(page_title="Neat | Dashboard", layout="wide", page_icon="🟢")
st.markdown(
    """
    <style>
    #MainMenu {visibility: hidden;} 
    footer {visibility: hidden;} 
    .ai-box {
        background-color: #1e2129; 
        border-left: 5px solid #00d2b4; 
        padding: 1.5rem; 
        border-radius: 10px; 
        margin-bottom: 2rem;
    } 
    .ai-box h4, .ai-box li, .ai-box p { color: white !important; } 
    [data-testid='stMetricValue'] {color: #00d2b4 !important;}
    </style>
    """, 
    unsafe_allow_html=True
)

# 2. Data Loading & Logic
@st.cache_data(ttl=600)
def load_data():
    url = "https://docs.google.com/spreadsheets/d/1bconB0u70BZv0aTblhhEA8_q56rlO6KAU1RG0P8yOjE/export?format=csv"
    data = pd.read_csv(url)
    data['Timestamp'] = pd.to_datetime(data['Timestamp'], errors='coerce')
    data['Capacity'] = pd.to_numeric(data.get('Capacity', 4), errors='coerce').fillna(4)
    data['Hour'] = data['Timestamp'].dt.hour
    data['Day'] = data['Timestamp'].dt.strftime('%A')
    
    # V2.2 Logic: Precision Work Hours, Nights, and Weekends
    is_weekday = data['Day'].isin(['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday'])
    is_weekend = data['Day'].isin(['Saturday', 'Sunday'])
    is_daytime = (data['Hour'] >= 9) & (data['Hour'] < 18) # 9am to 5:59pm
    
    data['Is_Work_Hour'] = is_weekday & is_daytime
    data['Is_Night_Hour'] = is_weekday & ~is_daytime
    data['Is_Weekend_Hour'] = is_weekend
    
    # Unproductive Time: Empty during Mon-Fri 9am-6pm
    data['Unproductive_Time'] = data['Is_Work_Hour'] & (data['Occupancy'] == 0)
    
    # HVAC Base: Empty but Hot (> 22.0C)
    hvac_base = (data['Occupancy'] == 0) & (data['Temperature'] > 22.0)
    
    # Split HVAC into 3 actionable categories
    data['HVAC_Work_Waste'] = hvac_base & data['Is_Work_Hour']
    data['HVAC_Night_Waste'] = hvac_base & data['Is_Night_Hour']
    data['HVAC_Weekend_Waste'] = hvac_base & data['Is_Weekend_Hour']
    
    return data

df = load_data()
valid_dates = df['Timestamp'].dropna()

if valid_dates.empty:
    st.error("No valid timestamps found.")
    st.stop()

# 3. Sidebar Filters
with st.sidebar:
    st.markdown("<h1 style='color: #00d2b4;'>neat.</h1>", unsafe_allow_html=True)
    loc_sel = st.selectbox("📍 Location", ["All"] + sorted(df['Location'].dropna().unique().tolist()))
    
    min_d = valid_dates.min().date()
    max_d = valid_dates.max().date()
    date_sel = st.date_input("📅 Date Range", value=(min_d, max_d))
    
    room_pool = df[df['Location'] == loc_sel] if loc_sel != "All" else df
    room_sel = st.multiselect("🚪 Rooms", sorted(room_pool['Room Name'].dropna().unique().tolist()))

# 4. Filter Logic
mask = df.copy()
if isinstance(date_sel, tuple) and len(date_sel) == 2:
    mask = mask[(mask['Timestamp'].dt.date >= date_sel[0]) & (mask['Timestamp'].dt.date <= date_sel[1])]
elif isinstance(date_sel, tuple) and len(date_sel) == 1:
    mask = mask[mask['Timestamp'].dt.date == date_sel[0]]

if loc_sel != "All": 
    mask = mask[mask['Location'] == loc_sel]
if room_sel: 
    mask = mask[mask['Room Name'].isin(room_sel)]

snap = mask.sort_values('Timestamp').drop_duplicates('Room Name', keep='last')

# 5. Dashboard UI
st.title("Room Analytics Dashboard")

# Executive Summary
st.markdown(
    """
    <div class="ai-box">
        <h4 style="margin-top:0;">✨ AI Executive Summary</h4>
        <ul>
            <li><b>Real Estate:</b> Unproductive time identified. Consider repurposing consistently empty spaces.</li>
            <li><b>Sustainability:</b> HVAC waste categorized. Adjust building management schedules for Nights and Weekends.</li>
        </ul>
    </div>
    """, 
    unsafe_allow_html=True
)

# 6. Top Metrics (6 Columns)
m1, m2, m3, m4, m5, m6 = st.columns(6)

on_count = len(snap[snap['Device Status'] == 'Online']) if not snap.empty else 0
avg_occ = mask['Occupancy'].mean() if not mask.empty else 0

m1.metric("🟢 Online", on_count)
m2.metric("👥 Avg/Room", f"{avg_occ:.1f}")

# Convert raw data pings into actionable "Hours" safely
mask['Date'] = mask['Timestamp'].dt.date
g_cols = ['Date', 'Hour', 'Room Name']

unproductive_hrs = mask[mask['Unproductive_Time']].groupby(g_cols).ngroups
hvac_work_hrs = mask[mask['HVAC_Work_Waste']].groupby(g_cols).ngroups
hvac_night_hrs = mask[mask['HVAC_Night_Waste']].groupby(g_cols).ngroups
hvac_wknd_hrs = mask[mask['HVAC_Weekend_Waste']].groupby(g_cols).ngroups

m3.metric("📉 Unproductive", f"{unproductive_hrs} Hrs", delta="- Empty (9-6)", delta_color="inverse")
m4.metric("☀️ HVAC (Day)", f"{hvac_work_hrs} Hrs", delta="- Wkdy 9-6", delta_color="inverse")
m5.metric("🌙 HVAC (Night)", f"{hvac_night_hrs} Hrs", delta="- Wkdy Night", delta_color="inverse")
m6.metric("🛋️ HVAC (Wknd)", f"{hvac_wknd_hrs} Hrs", delta="- Sat/Sun", delta_color="inverse")

# 7. Efficiency Cards
st.write("### 🏢 Room Efficiency Analysis")
c1, c2, c3 = st.columns(3)

def draw_card(col, title, df_sub, cap_label):
    with col:
        with st.container(border=True):
            st.write(f"**{title}**")
            avg_p = df_sub['Occupancy'].mean() if not df_sub.empty else 0.0
            avg_cap = df_sub['Capacity'].mean() if not df_sub.empty else 1.0
            
            # Catch NaN or zero capacity issues safely
            if pd.isna(avg_p): avg_p = 0.0
            if pd.isna(avg_cap) or avg_cap <= 0: avg_cap = 1.0
            
            st.metric("Avg People", f"{avg_p:.1f}", delta=f"{cap_label} Max", delta_color="off")
            st.progress(max(0.0, min((avg_p / avg_cap), 1.0)))

draw_card(c1, "Small (1-4)", mask[mask['Capacity'] <= 4], "4")
draw_card(c2, "Medium (5-8)", mask[(mask['Capacity'] > 4) & (mask['Capacity'] <= 8)], "8")
draw_card(c3, "Large (9-20)", mask[mask['Capacity'] > 8], "20")

# 8. Trends Chart
st.write("### 📈 Occupancy Trends")
if not mask.empty and 'Timestamp' in mask.columns and 'Occupancy' in mask.columns:
    fig = px.line(mask, x="Timestamp", y="Occupancy", color="Room Name", line_shape='spline')
    fig.update_layout(margin=dict(l=0, r=0, t=10, b=0), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
    st.plotly_chart(fig, use_container_width=True)
else:
    st.info("Insufficient data to display Occupancy Trends.")
