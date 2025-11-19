import streamlit as st
import requests
from datetime import datetime, timedelta

# --- PART 1: THE TOOLS (Functions) ---

def get_wikipedia_views(article_title):
    """Fetches last 30 days of Wiki page views."""
    headers = {'User-Agent': 'BoxOfficePredictor/1.0'}
    end_date = datetime.now()
    start_date = end_date - timedelta(days=30)
    str_start = start_date.strftime('%Y%m%d')
    str_end = end_date.strftime('%Y%m%d')
    url = f"https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/en.wikipedia/all-access/user/{article_title}/daily/{str_start}/{str_end}"
    
    try:
        data = requests.get(url, headers=headers).json()
        total_views = sum([item['views'] for item in data['items']])
        return int(total_views / len(data['items']))
    except:
        return 0

def calculate_box_office(interest, total_aware, theaters, rt_score, buzz, comp):
    # Base Calculation
    base_gross = (interest * 0.15) * (total_aware * 0.05) * 1_000_000
    capacity_gross = theaters * 3500
    weighted_gross = (base_gross * 0.6) + (capacity_gross * 0.4)
    
    # Multipliers
    quality_mult = 1.15 if rt_score > 80 else (0.85 if rt_score < 50 else 1.0)
    return weighted_gross * quality_mult * buzz * comp

# --- PART 2: REAL DATA PRESETS (The Quorum Data) ---
presets = {
    "Custom / Manual": {"aware": 5, "interest": 35, "theaters": 2200, "buzz": 1.0, "comp": 0.9, "wiki": "Eternity_(2025_film)"},
    "Eternity (Actual Tracking)": {"aware": 21, "interest": 34, "theaters": 2400, "buzz": 1.2, "comp": 0.85, "wiki": "Eternity_(2025_film)"},
    "Wicked (Competitor)": {"aware": 77, "interest": 50, "theaters": 4200, "buzz": 1.5, "comp": 0.8, "wiki": "Wicked_(2024_film)"},
    "Zootopia 2 (Competitor)": {"aware": 68, "interest": 53, "theaters": 4300, "buzz": 1.2, "comp": 0.8, "wiki": "Zootopia_2"},
    "A24 Standard (Baseline)": {"aware": 12, "interest": 28, "theaters": 1500, "buzz": 1.0, "comp": 1.0, "wiki": "A24"},
}

# --- PART 3: APP INTERFACE ---
st.set_page_config(page_title="Eternity Predictor", page_icon="🎬")
st.title("🎬 Eternity: Box Office Predictor")

# Preset Selector
selected_preset = st.selectbox("Select Tracking Data:", list(presets.keys()), index=1)
data = presets[selected_preset]

# Sidebar
st.sidebar.header("1. Live Tracking")
wiki_title = st.sidebar.text_input("Wikipedia Title", value=data['wiki'])
if st.sidebar.button("Fetch Live Wiki Views"):
    with st.spinner("Connecting to Wikipedia..."):
        views = get_wikipedia_views(wiki_title)
        st.sidebar.metric("30-Day Avg Views", f"{views:,}")

st.sidebar.divider()

st.sidebar.header("2. Model Inputs")
# The 'value' parameter sets the default based on the chosen preset
total_aware = st.sidebar.slider("Total Awareness (%)", 0, 100, value=data['aware'])
interest = st.sidebar.slider("Definite Interest (%)", 0, 100, value=data['interest'])
theaters = st.sidebar.number_input("Theater Count", 1000, 4500, value=data['theaters'])
rt_score = st.sidebar.slider("Rotten Tomatoes Score", 0, 100, value=85)
buzz = st.sidebar.select_slider("Social Buzz", options=[0.8, 1.0, 1.2, 1.5], value=data['buzz'])
comp = st.sidebar.select_slider("Competition", options=[0.8, 0.9, 1.0], value=data['comp'])

# Calculations
prediction = calculate_box_office(interest, total_aware, theaters, rt_score, buzz, comp)

# Outputs
st.divider()
col1, col2 = st.columns(2)

with col1:
    st.metric(label="Predicted Opening (3-Day)", value=f"${prediction/1_000_000:.2f}M")

with col2:
    st.write("### Analysis")
    if prediction > 10_000_000:
        st.success("🚀 BREAKOUT HIT")
    elif prediction > 6_000_000:
        st.info("✅ SOLID PERFORMER")
    else:
        st.error("⚠️ UNDERPERFORMER")

# Chart
st.write("### 📊 Benchmark Comparison")
chart_data = {
    "Prediction": prediction / 1_000_000,
    "Priscilla": 5.0,
    "The Iron Claw": 4.9,
    "Age of Adaline (Goal)": 13.2
}
st.bar_chart(chart_data)
