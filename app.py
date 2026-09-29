import streamlit as st
import pandas as pd
import plotly.express as px

# --- 1. Page Config & Scandinavian Dark Mode CSS (Neat Pulse Design System) ---
st.set_page_config(
    page_title="neat. Pulse Analytics",
    page_icon="🔮",
    layout="wide"
)

st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

    html, body, [class*="css"] {
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    }

    /* Overall App Background */
    .stApp {
        background-color: #121318;
        color: #f0f2f5;
    }

    /* Sidebar Customization */
    [data-testid="stSidebar"] {
        background-color: #171821;
        border-right: 1px solid #232533;
    }

    /* Custom Neat Header */
    .neat-header-container {
        display: flex;
        align-items: center;
        gap: 12px;
        margin-bottom: 24px;
        padding-bottom: 16px;
        border-bottom: 1px solid #232533;
    }
    .neat-logo {
        background: #ffffff;
        color: #121318;
        font-weight: 800;
        font-size: 1.1rem;
        padding: 6px 14px;
        border-radius: 12px;
        letter-spacing: -0.5px;
    }
    .neat-title {
        font-size: 1.6rem;
        font-weight: 700;
        letter-spacing: -0.5px;
        color: #ffffff;
        margin: 0;
    }

    /* Neat Highlight Card Component */
    .neat-card {
        background: #1b1c24;
        border: 1px solid #282a38;
        border-radius: 20px;
        padding: 22px 24px;
        box-shadow: 0 10px 30px rgba(0, 0, 0, 0.25);
        transition: transform 0.2s ease, border-color 0.2s ease;
        margin-bottom: 16px;
        height: 100%;
    }
    .neat-card:hover {
        border-color: #3e4258;
        transform: translateY(-2px);
    }
    .neat-card-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 10px;
    }
    .neat-card-title {
        color: #8e95a7;
        font-size: 0.8rem;
        font-weight: 600;
        letter-spacing: 0.6px;
        text-transform: uppercase;
    }
    .neat-card-value {
        color: #ffffff;
        font-size: 2.2rem;
        font-weight: 700;
        letter-spacing: -0.8px;
        line-height: 1.1;
        margin: 6px 0;
    }
    .neat-card-sub {
        color: #799bf1;
        font-size: 0.82rem;
        font-weight: 500;
    }

    /* Status Badges */
    .neat-badge-pink {
        background: #3c2027;
        color: #f87171;
        font-size: 0.72rem;
        font-weight: 700;
        padding: 4px 10px;
        border-radius: 10px;
        border: 1px solid #5d2834;
    }
    .neat-badge-blue {
        background: #1c2640;
        color: #799bf1;
        font-size: 0.72rem;
        font-weight: 700;
        padding: 4px 10px;
        border-radius: 10px;
        border: 1px solid #2b3a63;
    }
    .neat-badge-green {
        background: #143528;
        color: #34d399;
        font-size: 0.72rem;
        font-weight: 700;
        padding: 4px 10px;
        border-radius: 10px;
        border: 1px solid #1f5440;
    }
    .neat-badge-amber {
        background: #3b2d19;
        color: #fbbf24;
        font-size: 0.72rem;
        font-weight: 700;
        padding: 4px 10px;
        border-radius: 10px;
        border: 1px solid #5e4827;
    }
    </style>
""", unsafe_allow_html=True)


# --- Helper Function to Render Neat Highlight Cards ---
def render_neat_card(title, value, subtext="", badge_text="", badge_type="blue"):
    badge_html = f'<span class="neat-badge-{badge_type}">{badge_text}</span>' if badge_text else ''
    card_html = f"""
    <div class="neat-card">
        <div class="neat-card-header">
            <span class="neat-card-title">{title}</span>
            {badge_html}
        </div>
        <div class="neat-card-value">{value}</div>
        <div class="neat-card-sub">{subtext}</div>
    </div>
    """
    st.markdown(card_html, unsafe_allow_html=True)


# --- 2. Data Ingestion & Caching ---
@st.cache_data(ttl=600)
def load_data():
    url = "https://docs.google.com/spreadsheets/d/e/2PACX-1vSnuQD0k37rAqGskyHXOhri32cd8nsV8yiEFDLF7nuqKBkEdDfgkdrtYtx2Tw1pXyU_N3bADMcVD8iX/pub?output=csv"
    
    try:
        data = pd.read_csv(url)
    except Exception as e:
        st.error("Telemetry stream disconnect. Check published Google Sheet URL.")
        st.stop()

    data.columns = data.columns.str.strip()
    data['Timestamp'] = pd.to_datetime(data['Timestamp'], dayfirst=True, errors='coerce')
    
    platform_mapping = {
        'msteams': 'Microsoft Teams', 'zoom': 'Zoom', 'google_meet': 'Google Meet',
        'apphub': 'Neat App Hub', 'usb': 'BYOD (USB Mode)', 'avos': 'App Hub Partner', 'none': 'Unprovisioned'
    }
    if 'Platform' in data.columns:
        data['Platform'] = data['Platform'].replace(platform_mapping)

    if 'Capacity' in data.columns:
        data['Capacity'] = pd.to_numeric(data['Capacity'], errors='coerce')
        data['Capacity'] = data.groupby('Room Name')['Capacity'].transform('max').fillna(4)
    else:
        data['Capacity'] = 4.0

    for col in ['VOC', 'Light Level', 'Temperature', 'Humidity', 'Occupancy']:
        if col in data.columns:
            data[col] = pd.to_numeric(data[col], errors='coerce').fillna(0)
        else:
            data[col] = 0.0

    data['Hour'] = data['Timestamp'].dt.hour
    data['Day'] = data['Timestamp'].dt.strftime('%A')
    
    is_weekday = data['Day'].isin(['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday'])
    is_daytime = (data['Hour'] >= 8) & (data['Hour'] < 19)
    
    data['Is_Work_Hour'] = is_weekday & is_daytime
    data['Unproductive_Time'] = data['Is_Work_Hour'] & (data['Occupancy'] == 0)
    data['HVAC_Work_Waste'] = (data['Occupancy'] == 0) & (data['Temperature'] > 22.0) & data['Is_Work_Hour']
    data['Vampire_Lighting'] = (data['Occupancy'] == 0) & (data['Light Level'] > 50)
    
    return data


raw_data = load_data()
data = raw_data.dropna(subset=['Timestamp']).copy()


# --- 3. Sidebar Filtering Controls ---
st.sidebar.markdown("### **neat.** Controls")

if st.sidebar.button("🔄 Sync Live Telemetry", use_container_width=True):
    st.cache_data.clear()
    st.rerun()

st.sidebar.markdown("---")
st.sidebar.markdown("##### Filter Parameters")

if not data.empty and 'Timestamp' in data.columns:
    min_date = data['Timestamp'].min().date()
    max_date = data['Timestamp'].max().date()
    default_start = max(min_date, max_date - pd.Timedelta(days=7))
else:
    min_date = pd.Timestamp.today().date()
    max_date = pd.Timestamp.today().date()
    default_start = min_date

date_range = st.sidebar.date_input(
    "Date Range",
    value=(default_start, max_date),
    min_value=min_date,
    max_value=max_date
)

if isinstance(date_range, tuple) and len(date_range) == 2:
    start_date, end_date = date_range
else:
    start_date = default_start
    end_date = max_date

locations = data['Location'].unique().tolist() if 'Location' in data.columns else []
selected_locations = st.sidebar.multiselect("Locations", options=locations, default=locations)

time_filter = st.sidebar.radio(
    "Operating Hours Window",
    options=["Office Hours (Mon-Fri, 8 AM - 7 PM)", "24/7 Full Telemetry"],
    index=0
)


# --- 4. Dataset Filtering Logic (Defensive Implementation) ---
start_datetime = pd.to_datetime(start_date)
end_datetime = pd.to_datetime(end_date) + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)

# Ensure Timestamp is a column and not set as index
if 'Timestamp' not in data.columns and data.index.name == 'Timestamp':
    data = data.reset_index()

if 'Timestamp' in data.columns:
    filtered_df = data[
        (data['Timestamp'] >= start_datetime) & 
        (data['Timestamp'] <= end_datetime)
    ].copy()
else:
    filtered_df = data.copy()

if selected_locations and 'Location' in filtered_df.columns and not filtered_df.empty:
    filtered_df = filtered_df[filtered_df['Location'].isin(selected_locations)]

# HARDCODED BACKGROUND FILTER: Enforce target London Showroom rooms only
TARGET_LONDON_ROOMS = [
    'Arran', 
    'Barra', 
    'Dalmore Microsoft', 
    'Edradour', 
    'Harris', 
    'Longrow', 
    'Macallan', 
    'z Dalmore Google'
]

if 'Room Name' in filtered_df.columns and not filtered_df.empty:
    filtered_df = filtered_df[filtered_df['Room Name'].apply(
        lambda room: any(target.lower() in str(room).lower() for target in TARGET_LONDON_ROOMS)
    )]

# Safe Operating Hours Filter Guard
if time_filter == "Office Hours (Mon-Fri, 8 AM - 7 PM)" and not filtered_df.empty and 'Timestamp' in filtered_df.columns:
    is_weekday = filtered_df['Timestamp'].dt.dayofweek < 5
    is_work_hours = (filtered_df['Timestamp'].dt.hour >= 8) & (filtered_df['Timestamp'].dt.hour < 19)
    filtered_df = filtered_df[is_weekday & is_work_hours]


# --- 5. Main Dashboard Header ---
st.markdown("""
    <div class="neat-header-container">
        <div class="neat-logo">neat.</div>
        <div class="neat-title">Pulse Intelligence & IoT Telemetry</div>
    </div>
""", unsafe_allow_html=True)


# --- 6. Environmental Overview Highlight Cards ---
st.markdown("##### 🌐 Environmental Telemetry Highlights")
c1, c2, c3, c4 = st.columns(4)

total_rooms = filtered_df['Room Name'].nunique() if not filtered_df.empty and 'Room Name' in filtered_df.columns else 0
avg_occ = filtered_df['Occupancy'].mean() if not filtered_df.empty and 'Occupancy' in filtered_df.columns else 0.0
avg_temp = filtered_df['Temperature'].mean() if not filtered_df.empty and 'Temperature' in filtered_df.columns else 0.0
avg_voc = filtered_df['VOC'].mean() if not filtered_df.empty and 'VOC' in filtered_df.columns else 0.0

with c1:
    render_neat_card("Active Spaces", f"{total_rooms}", "Live London devices online", "ONLINE", "green")
with c2:
    render_neat_card("Avg Occupancy", f"{avg_occ:.1f}", "People per active room", "UTILIZATION", "blue")
with c3:
    render_neat_card("Avg Temperature", f"{avg_temp:.1f} °C", "Target setpoint: 21.0 °C", "CLIMATE", "amber")
with c4:
    render_neat_card("Air Quality (VOC)", f"{avg_voc:.0f} ppb", "Indoor environmental index", "AIR QUALITY", "blue")

st.markdown("<br/>", unsafe_allow_html=True)

# --- 7. Space Utilization & Energy Waste Highlight Cards ---
st.markdown("##### ⚡ Space Efficiency & Operational Insights")
u1, u2, u3, u4 = st.columns(4)

ghost_hours = (filtered_df['Unproductive_Time'].sum() / 6) if not filtered_df.empty and 'Unproductive_Time' in filtered_df.columns else 0.0
hvac_waste_hours = (filtered_df['HVAC_Work_Waste'].sum() / 6) if not filtered_df.empty and 'HVAC_Work_Waste' in filtered_df.columns else 0.0
vampire_light_hours = (filtered_df['Vampire_Lighting'].sum() / 6) if not filtered_df.empty and 'Vampire_Lighting' in filtered_df.columns else 0.0
peak_occ = filtered_df['Occupancy'].max() if not filtered_df.empty and 'Occupancy' in filtered_df.columns else 0

with u1:
    render_neat_card("Ghost Meeting Waste", f"{ghost_hours:.1f} hrs", "Booked rooms left vacant", "ATTENTION", "pink")
with u2:
    render_neat_card("HVAC Overheating", f"{hvac_waste_hours:.1f} hrs", "Empty rooms heated >22°C", "ENERGY WASTE", "pink")
with u3:
    render_neat_card("Vampire Lighting", f"{vampire_light_hours:.1f} hrs", "Lights active (>50 lx) when empty", "LIGHTING", "amber")
with u4:
    render_neat_card("Peak Occupancy", f"{int(peak_occ)}", "Maximum concurrent count", "PEAK LOAD", "green")


# --- 8. Telemetry Trends Chart (Neat Palette) ---
st.markdown("<br/>", unsafe_allow_html=True)
st.markdown("##### 📈 IoT Telemetry Trends")

metric_choice = st.selectbox(
    "Select Telemetry Metric",
    options=["Occupancy", "Temperature", "Humidity", "VOC", "Light Level"],
    label_visibility="collapsed"
)

neat_colors = ['#799bf1', '#f87171', '#34d399', '#fbbf24', '#c084fc', '#f472b6', '#38bdf8', '#a7f3d0']

if not filtered_df.empty and 'Timestamp' in filtered_df.columns:
    num_days = (end_date - start_date).days
    freq = '1W' if num_days > 60 else ('1D' if num_days > 14 else '1h')

    smoothed_df = (
        filtered_df.groupby([
            pd.Grouper(key='Timestamp', freq=freq), 
            'Room Name'
        ])[metric_choice]
        .mean()
        .reset_index()
    )

    fig = px.line(
        smoothed_df,
        x='Timestamp',
        y=metric_choice,
        color='Room Name',
        title=f"Telemetry Stream — {metric_choice} ({time_filter})",
        template="plotly_dark",
        line_shape='spline',
        color_discrete_sequence=neat_colors
    )

    fig.update_traces(line=dict(width=2.5))
    fig.update_layout(
        paper_bgcolor="#1b1c24",
        plot_bgcolor="#1b1c24",
        font=dict(family="Inter", color="#8e95a7"),
        xaxis=dict(gridcolor="#282a38", zerolinecolor="#282a38", title="Timeline"),
        yaxis=dict(gridcolor="#282a38", zerolinecolor="#282a38", title=metric_choice),
        legend=dict(title="Room Name", bgcolor="rgba(0,0,0,0)"),
        hovermode="x unified",
        margin=dict(l=20, r=20, t=50, b=20)
    )

    st.plotly_chart(fig, use_container_width=True)
else:
    st.warning("No telemetry records matching the selected date range and parameters.")


# --- 9. Room Utilization & Capacity Analysis ---
st.markdown("##### 📊 Room Utilization vs Capacity")

if not filtered_df.empty and 'Room Name' in filtered_df.columns:
    col_chart, col_table = st.columns([1, 1])

    room_stats = (
        filtered_df.groupby(['Room Name', 'Location'])
        .agg(
            Avg_Occupancy=('Occupancy', 'mean'),
            Peak_Occupancy=('Occupancy', 'max'),
            Capacity=('Capacity', 'max'),
            Avg_Temp=('Temperature', 'mean'),
            Avg_VOC=('VOC', 'mean')
        )
        .reset_index()
    )
    
    room_stats['Capacity_Util_%'] = (room_stats['Avg_Occupancy'] / room_stats['Capacity'] * 100).round(1)
    room_stats['Avg_Occupancy'] = room_stats['Avg_Occupancy'].round(1)
    room_stats['Avg_Temp'] = room_stats['Avg_Temp'].round(1)
    room_stats['Avg_VOC'] = room_stats['Avg_VOC'].round(0)

    with col_chart:
        fig_rooms = px.bar(
            room_stats.sort_values(by='Avg_Occupancy', ascending=False),
            x='Room Name',
            y=['Avg_Occupancy', 'Capacity'],
            barmode='group',
            title="Avg Occupancy vs Capacity",
            labels={'value': 'Count / People', 'variable': 'Metric'},
            template="plotly_dark",
            color_discrete_sequence=['#799bf1', '#34d399']
        )
        fig_rooms.update_layout(
            paper_bgcolor="#1b1c24",
            plot_bgcolor="#1b1c24",
            font=dict(family="Inter", color="#8e95a7"),
            xaxis=dict(gridcolor="#282a38"),
            yaxis=dict(gridcolor="#282a38")
        )
        st.plotly_chart(fig_rooms, use_container_width=True)

    with col_table:
        st.dataframe(
            room_stats[['Room Name', 'Location', 'Capacity', 'Avg_Occupancy', 'Capacity_Util_%', 'Avg_Temp', 'Avg_VOC']],
            use_container_width=True,
            hide_index=True
        )


# --- 10. Platform Ecosystem Distribution ---
st.markdown("<br/>", unsafe_allow_html=True)
st.markdown("##### 💻 Meeting Ecosystem Share")

if not filtered_df.empty and 'Platform' in filtered_df.columns:
    c_plat1, c_plat2 = st.columns([1, 1])
    
    platform_counts = filtered_df['Platform'].value_counts().reset_index()
    platform_counts.columns = ['Platform', 'Count']

    with c_plat1:
        fig_platform = px.pie(
            platform_counts,
            names='Platform',
            values='Count',
            title="Ecosystem Platform Distribution",
            hole=0.5,
            template="plotly_dark",
            color_discrete_sequence=['#799bf1', '#34d399', '#fbbf24', '#f87171']
        )
        fig_platform.update_layout(paper_bgcolor="#1b1c24", font=dict(family="Inter", color="#8e95a7"))
        st.plotly_chart(fig_platform, use_container_width=True)

    with c_plat2:
        fig_plat_bar = px.bar(
            platform_counts,
            x='Platform',
            y='Count',
            color='Platform',
            title="Active Session Engines",
            template="plotly_dark",
            color_discrete_sequence=['#799bf1', '#34d399', '#fbbf24', '#f87171']
        )
        fig_plat_bar.update_layout(
            paper_bgcolor="#1b1c24", 
            plot_bgcolor="#1b1c24", 
            font=dict(family="Inter", color="#8e95a7"),
            xaxis=dict(gridcolor="#282a38"),
            yaxis=dict(gridcolor="#282a38")
        )
        st.plotly_chart(fig_plat_bar, use_container_width=True)


# --- 11. Raw Telemetry Inspector ---
st.markdown("---")
with st.expander("🔍 Raw Telemetry Data Inspector"):
    st.dataframe(filtered_df, use_container_width=True)
    
    csv_data = filtered_df.to_csv(index=False).encode('utf-8')
    st.download_button(
        label="📥 Download Filtered Telemetry CSV",
        data=csv_data,
        file_name="neat_pulse_telemetry.csv",
        mime="text/csv"
    )
