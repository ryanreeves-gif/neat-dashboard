import streamlit as st
import pandas as pd
import plotly.express as px

# --- 1. Page Configuration & Dark Theme Styling ---
st.set_page_config(
    page_title="Neat Room Analytics & Middleware Dashboard",
    page_icon="🏢",
    layout="wide"
)

st.markdown("""
    <style>
    .stApp {
        background-color: #0e1117;
        color: #ffffff;
    }
    .stMetric {
        background-color: #1e222d;
        padding: 14px;
        border-radius: 8px;
        border: 1px solid #2e3440;
    }
    </style>
""", unsafe_allow_html=True)


# --- 2. Data Loading & Caching Engine ---
@st.cache_data(ttl=600)
def load_data():
    url = "https://docs.google.com/spreadsheets/d/e/2PACX-1vSnuQD0k37rAqGskyHXOhri32cd8nsV8yiEFDLF7nuqKBkEdDfgkdrtYtx2Tw1pXyU_N3bADMcVD8iX/pub?output=csv"
    
    try:
        data = pd.read_csv(url)
    except Exception as e:
        st.error("Telemetry stream disconnect. Please check the published spreadsheet URL.")
        st.stop()

    data.columns = data.columns.str.strip()
    
    # Enforce UK date parsing
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

    # Calculated metrics for energy & usage cards
    data['Hour'] = data['Timestamp'].dt.hour
    data['Day'] = data['Timestamp'].dt.strftime('%A')
    
    is_weekday = data['Day'].isin(['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday'])
    is_daytime = (data['Hour'] >= 8) & (data['Hour'] < 19)
    
    data['Is_Work_Hour'] = is_weekday & is_daytime
    data['Unproductive_Time'] = data['Is_Work_Hour'] & (data['Occupancy'] == 0)
    data['HVAC_Work_Waste'] = (data['Occupancy'] == 0) & (data['Temperature'] > 22.0) & data['Is_Work_Hour']
    data['Vampire_Lighting'] = (data['Occupancy'] == 0) & (data['Light Level'] > 50)
    
    return data


# --- 3. Execute Data Load Before Sidebar Rendering ---
raw_data = load_data()
data = raw_data.dropna(subset=['Timestamp']).copy()


# --- 4. Sidebar Controls ---
st.sidebar.title("neat. Controls")

if st.sidebar.button("🔄 Refresh Telemetry"):
    st.cache_data.clear()
    st.rerun()

st.sidebar.markdown("---")
st.sidebar.header("Filter Options")

if not data.empty:
    min_date = data['Timestamp'].min().date()
    max_date = data['Timestamp'].max().date()
else:
    min_date = pd.Timestamp.today().date()
    max_date = pd.Timestamp.today().date()

date_range = st.sidebar.date_input(
    "Select Date Range",
    value=(min_date, max_date),
    min_value=min_date,
    max_value=max_date
)

if isinstance(date_range, tuple) and len(date_range) == 2:
    start_date, end_date = date_range
else:
    start_date = min_date
    end_date = max_date

locations = data['Location'].unique().tolist() if 'Location' in data.columns else []
selected_locations = st.sidebar.multiselect("Locations", options=locations, default=locations)

time_filter = st.sidebar.radio(
    "Operating Hours Filter",
    options=["Office Hours (Mon-Fri, 8 AM - 7 PM)", "24/7 (All Hours)"],
    index=0
)


# --- 5. Data Filtering Logic ---
start_datetime = pd.to_datetime(start_date)
end_datetime = pd.to_datetime(end_date) + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)

filtered_df = data[
    (data['Timestamp'] >= start_datetime) & 
    (data['Timestamp'] <= end_datetime)
].copy()

if selected_locations and 'Location' in filtered_df.columns:
    filtered_df = filtered_df[filtered_df['Location'].isin(selected_locations)]

if time_filter == "Office Hours (Mon-Fri, 8 AM - 7 PM)":
    is_weekday = filtered_df['Timestamp'].dt.dayofweek < 5
    is_work_hours = (filtered_df['Timestamp'].dt.hour >= 8) & (filtered_df['Timestamp'].dt.hour < 19)
    filtered_df = filtered_df[is_weekday & is_work_hours]


# --- 6. Main Dashboard Header & Overview Cards ---
st.title("🏢 Neat Room Analytics & Middleware Dashboard")
st.markdown("Real-time telemetry ingestion, space utilization, and IoT environmental insights.")

st.subheader("🌐 Environmental Telemetry Overview")
e1, e2, e3, e4 = st.columns(4)

total_rooms = filtered_df['Room Name'].nunique() if not filtered_df.empty else 0
avg_occ = filtered_df['Occupancy'].mean() if not filtered_df.empty else 0.0
avg_temp = filtered_df['Temperature'].mean() if not filtered_df.empty else 0.0
avg_voc = filtered_df['VOC'].mean() if not filtered_df.empty else 0.0

e1.metric("Active Rooms Monitored", f"{total_rooms}")
e2.metric("Avg Room Occupancy", f"{avg_occ:.1f} people")
e3.metric("Avg Room Temperature", f"{avg_temp:.1f} °C")
e4.metric("Avg Air Quality (VOC)", f"{avg_voc:.0f} ppb")

st.markdown("---")

# --- 7. Space Utilization & Energy Efficiency Cards ---
st.subheader("⚡ Space Utilization & Energy Efficiency Insights")
u1, u2, u3, u4 = st.columns(4)

ghost_hours = (filtered_df['Unproductive_Time'].sum() / 6) if not filtered_df.empty else 0.0
hvac_waste_hours = (filtered_df['HVAC_Work_Waste'].sum() / 6) if not filtered_df.empty else 0.0
vampire_light_hours = (filtered_df['Vampire_Lighting'].sum() / 6) if not filtered_df.empty else 0.0
peak_occ = filtered_df['Occupancy'].max() if not filtered_df.empty else 0

u1.metric("Ghost Meeting Waste", f"{ghost_hours:.1f} hrs", help="Work hours where booked/active rooms had 0 occupants")
u2.metric("HVAC Overheating Waste", f"{hvac_waste_hours:.1f} hrs", help="Empty rooms heated above 22°C during work hours")
u3.metric("Vampire Lighting", f"{vampire_light_hours:.1f} hrs", help="Lights left on (>50 lux) in empty rooms")
u4.metric("Peak Recorded Occupancy", f"{int(peak_occ)} people", help="Maximum occupants recorded across all rooms")

st.markdown("---")


# --- 8. Telemetry Trends Chart ---
st.subheader("📈 Full IoT Telemetry Trends")

metric_choice = st.selectbox(
    "Select Telemetry Metric",
    options=["Occupancy", "Temperature", "Humidity", "VOC", "Light Level"]
)

if not filtered_df.empty:
    smoothed_df = (
        filtered_df.groupby([
            pd.Grouper(key='Timestamp', freq='1h'), 
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
        title=f"Telemetry Trends — {metric_choice} ({time_filter})",
        template="plotly_dark",
        line_shape='spline'
    )

    fig.update_traces(line=dict(width=2))
    fig.update_layout(
        xaxis_title="Timeline", 
        yaxis_title=metric_choice, 
        legend_title="Room Name",
        hovermode="x unified"
    )

    st.plotly_chart(fig, use_container_width=True)
else:
    st.warning("No data found matching the selected date range and filter criteria.")

st.markdown("---")


# --- 9. Room-by-Room Usage & Capacity Breakdown ---
st.subheader("📊 Room Utilization & Capacity Analysis")

if not filtered_df.empty:
    col_chart, col_table = st.columns([1, 1])

    # Aggregated room metrics
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
            title="Average Occupancy vs Room Capacity",
            labels={'value': 'Count / People', 'variable': 'Metric'},
            template="plotly_dark"
        )
        st.plotly_chart(fig_rooms, use_container_width=True)

    with col_table:
        st.markdown("**Room Metric Breakdown**")
        st.dataframe(
            room_stats[['Room Name', 'Location', 'Capacity', 'Avg_Occupancy', 'Capacity_Util_%', 'Avg_Temp', 'Avg_VOC']],
            use_container_width=True,
            hide_index=True
        )


# --- 10. Platform Distribution & Meeting Tech Insights ---
st.markdown("---")
st.subheader("💻 Meeting Ecosystem & Platform Usage")

if not filtered_df.empty and 'Platform' in filtered_df.columns:
    c_plat1, c_plat2 = st.columns([1, 1])
    
    platform_counts = filtered_df['Platform'].value_counts().reset_index()
    platform_counts.columns = ['Platform', 'Count']

    with c_plat1:
        fig_platform = px.pie(
            platform_counts,
            names='Platform',
            values='Count',
            title="Platform Share (Active Sessions)",
            hole=0.4,
            template="plotly_dark"
        )
        st.plotly_chart(fig_platform, use_container_width=True)

    with c_plat2:
        fig_plat_bar = px.bar(
            platform_counts,
            x='Platform',
            y='Count',
            color='Platform',
            title="Telecommunication Engine Distribution",
            template="plotly_dark"
        )
        st.plotly_chart(fig_plat_bar, use_container_width=True)


# --- 11. Raw Telemetry Inspector ---
st.markdown("---")
with st.expander("🔍 Inspect Raw Ingested Telemetry Data"):
    st.dataframe(filtered_df, use_container_width=True)
    
    csv_data = filtered_df.to_csv(index=False).encode('utf-8')
    st.download_button(
        label="📥 Download Filtered Telemetry CSV",
        data=csv_data,
        file_name="neat_telemetry_export.csv",
        mime="text/csv"
    )
