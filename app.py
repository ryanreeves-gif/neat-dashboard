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
        padding: 12px;
        border-radius: 8px;
        border: 1px solid #2e3440;
    }
    </style>
""", unsafe_allow_html=True)

# --- 2. Data Loading & Caching Engine ---
@st.cache_data(ttl=600)
def load_data():
    # Direct live feed from published personal Google Sheet
    url = "https://docs.google.com/spreadsheets/d/e/2PACX-1vSnuQD0k37rAqGskyHXOhri32cd8nsV8yiEFDLF7nuqKBkEdDfgkdrtYtx2Tw1pXyU_N3bADMcVD8iX/pub?output=csv"
    
    try:
        data = pd.read_csv(url)
    except Exception as e:
        st.error("Telemetry stream disconnect. Please check the published spreadsheet URL.")
        st.stop()

    data.columns = data.columns.str.strip()
    
    # Enforce UK date parsing (dayfirst=True) to fix monthly date drops
    data['Timestamp'] = pd.to_datetime(data['Timestamp'], dayfirst=True, errors='coerce')
    
    platform_mapping = {
        'msteams': 'Microsoft Teams', 'zoom': 'Zoom', 'google_meet': 'Google Meet',
        'apphub': 'Neat App Hub', 'usb': 'BYOD (USB Mode)', 'avos': 'App Hub Partner', 'none': 'Unprovisioned'
    }
    if 'Platform' in data.columns:
        data['Platform'] = data['Platform'].replace(platform_mapping)

    if 'Capacity' in data.columns:
        data['Capacity'] = pd.to_numeric(data['Capacity'], errors='coerce')
        data['Capacity'] = data.groupby('Room Name')['Capacity'].transform('max')
        data['Capacity'] = data['Capacity'].fillna(4)
    else:
        data['Capacity'] = 4.0

    # Clean numeric columns
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
    fig = px.line(
        smoothed_df,
        x='Timestamp',
        y=metric_choice,
        color='Room Name',
        title=f"Telemetry Trends — {metric_choice} ({time_filter})",
        template="plotly_dark",
        line_shape='spline'  # Pass spline curve directly into Plotly Express
    )

    # Cleanly set line thickness
    fig.update_traces(line=dict(width=2))
    
    fig.update_layout(
        xaxis_title="Timeline", 
        yaxis_title=metric_choice, 
        legend_title="Room Name",
        hovermode="x unified"
    )

    st.plotly_chart(fig, use_container_width=True)
    st.rerun()

st.sidebar.markdown("---")
st.sidebar.header("Filter Options")

# Date Range Picker
min_date = data['Timestamp'].min().date()
max_date = data['Timestamp'].max().date()

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

# Location Filter
locations = data['Location'].unique().tolist() if 'Location' in data.columns else []
selected_locations = st.sidebar.multiselect("Locations", options=locations, default=locations)

# Operating Hours Filter Toggle
time_filter = st.sidebar.radio(
    "Operating Hours Filter",
    options=["Office Hours (Mon-Fri, 8 AM - 7 PM)", "24/7 (All Hours)"],
    index=0
)

# --- 4. Dataset Filtering Logic ---
start_datetime = pd.to_datetime(start_date)
end_datetime = pd.to_datetime(end_date) + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)

filtered_df = data[
    (data['Timestamp'] >= start_datetime) & 
    (data['Timestamp'] <= end_datetime)
].copy()

if selected_locations and 'Location' in filtered_df.columns:
    filtered_df = filtered_df[filtered_df['Location'].isin(selected_locations)]

# Apply Operating Hours Toggle
if time_filter == "Office Hours (Mon-Fri, 8 AM - 7 PM)":
    is_weekday = filtered_df['Timestamp'].dt.dayofweek < 5
    is_work_hours = (filtered_df['Timestamp'].dt.hour >= 8) & (filtered_df['Timestamp'].dt.hour < 19)
    filtered_df = filtered_df[is_weekday & is_work_hours]

# --- 5. Main Dashboard View ---
st.title("🏢 Neat Room Analytics & Middleware Dashboard")
st.markdown("Real-time telemetry ingestion, space utilization, and IoT environmental insights.")

# Top Metric Summary Cards
m1, m2, m3, m4 = st.columns(4)
total_rooms = filtered_df['Room Name'].nunique() if 'Room Name' in filtered_df.columns else 0
avg_occ = filtered_df['Occupancy'].mean() if not filtered_df.empty else 0
avg_temp = filtered_df['Temperature'].mean() if not filtered_df.empty else 0
avg_voc = filtered_df['VOC'].mean() if not filtered_df.empty else 0

m1.metric("Active Rooms", f"{total_rooms}")
m2.metric("Avg Occupancy", f"{avg_occ:.1f} people")
m3.metric("Avg Temperature", f"{avg_temp:.1f} °C")
m4.metric("Avg Air Quality (VOC)", f"{avg_voc:.0f} ppb")

st.markdown("---")

# --- 6. Smoothed IoT Telemetry Trend Chart ---
st.subheader("📈 Full IoT Telemetry Trends")

metric_choice = st.selectbox(
    "Select Telemetry Metric",
    options=["Occupancy", "Temperature", "Humidity", "VOC", "Light Level"]
)

if not filtered_df.empty:
    # Resample to 1-hour averages per room to smooth out 10-minute noise
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
        template="plotly_dark"
    )

    # Convert angular lines into smooth curves
    fig.update_traces(line_shape='spline', line=dict(width=2))
    fig.update_layout(
        xaxis_title="Timeline", 
        yaxis_title=metric_choice, 
        legend_title="Room Name",
        hovermode="x unified"
    )

    st.plotly_chart(fig, use_container_width=True)
else:
    st.warning("No data found matching the selected filters.")
