import streamlit as st
import requests
import re
import math
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

def get_youtube_views(video_id, fallback_views):
    """
    Attempts to scrape the live view count from the YouTube video page.
    Falls back to a hardcoded number if the scrape fails.
    """
    url = f"https://www.youtube.com/watch?v={video_id}"
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
    
    try:
        response = requests.get(url, headers=headers)
        match = re.search(r'"viewCount":"(\d+)"', response.text)
        if match:
            return int(match.group(1))
        else:
            return fallback_views
    except:
        return fallback_views

def calculate_box_office(interest, total_aware, theaters, rt_score, buzz, comp, trailer_views):
    # 1. Base Calculation (Linear)
    base_gross = (interest * 0.15) * (total_aware * 0.05) * 1_000_000
    
    # 2. TRAILER / VIRAL BOOST
    # We tweaked this down slightly so it doesn't over-inflate niche films
    trailer_multiplier = 1.0
    if trailer_views > 60_000_000:
        trailer_multiplier = 1.4  # Mega Viral (Blockbuster only)
    elif trailer_views > 15_000_000:
        trailer_multiplier = 1.2 # Star Power / Viral 
    
    base_gross = base_gross * trailer_multiplier

    # 3. BLOCKBUSTER ADJUSTMENT
    if theaters > 3000:
        base_gross = base_gross * 3.0 
        if total_aware > 60:
            base_gross = base_gross * 1.25

    # 4. Capacity Logic
    cap_per_theater = 5000 if theaters > 3000 else 3500
    capacity_gross = theaters * cap_per_theater
    
    weighted_gross = (base_gross * 0.7) + (capacity_gross * 0.3)
    
    # 5. Multipliers
    quality_mult = 1.15 if rt_score > 80 else (0.85 if rt_score < 50 else 1.0)
    raw_prediction = weighted_gross * quality_mult * buzz * comp

    # 6. REALITY CAP
    if raw_prediction > 150_000_000:
        excess = raw_prediction - 150_000_000
        dampened_excess = math.sqrt(excess) * 3500 
        final_prediction = 150_000_000 + dampened_excess
    else:
        final_prediction = raw_prediction
        
    return final_prediction

# --- PART 2: REAL DATA PRESETS (TUNED DOWN) ---
presets = {
    "Eternity (A24)": {
        "aware": 21, "interest": 34, "theaters": 2400, "buzz": 1.2, "comp": 0.85, 
        "wiki": "Eternity_(2025_film)", 
        "yt_id": "irXTps1REHU", "yt_fallback": 9300000
    },
    "Marty Supreme (A24)": {
        "aware": 30, "interest": 40, "theaters": 2200, "buzz": 1.3, "comp": 0.9, 
        "wiki": "Marty_Supreme", 
        "yt_id": "s9gSuKaKcqM", "yt_fallback": 17800000
    },
    "Pillion (A24/Element)": {
        "aware": 10, "interest": 20, "theaters": 800, "buzz": 1.0, "comp": 0.95, 
        "wiki": "Pillion_(film)", 
        "yt_id": "aTAacTUKK00", "yt_fallback": 500000
    },
    "The Moment (A24)": {
        # TUNED DOWN: Was 35% Aware / 40% Interest (Too high for indie drama)
        "aware": 15, "interest": 25, "theaters": 2000, "buzz": 1.1, "comp": 0.9, 
        "wiki": "The_Moment_(2026_film)", 
        "yt_id": "ey5YrCNH09g", "yt_fallback": 1500000
    },
    "Wicked: Part Two": {
        "aware": 77, "interest": 50, "theaters": 4200, "buzz": 1.5, "comp": 0.8, 
        "wiki": "Wicked_(2024_film)", 
        "yt_id": "vt98AlBDI9Y", "yt_fallback": 113000000
    },
    "Zootopia 2": {
        "aware": 68, "interest": 53, "theaters": 4300, "buzz": 1.3, "comp": 0.8, 
        "wiki": "Zootopia_2", 
        "yt_id": "xo4rkcC7kFc", "yt_fallback": 25000000
    },
    "Elden Ring (Hypothetical)": {
        # TUNED DOWN: Was 75/65. 
        # Lowered Interest because hardcore fantasy isolates casual audiences (unlike Mario)
        "aware": 60, "interest": 45, "theaters": 4000, "buzz": 1.4, "comp": 0.8, 
        "wiki": "Elden_Ring", 
        "yt_id": "E3Huy2cdih0", "yt_fallback": 14000000
    },
}

# --- PART 3: APP INTERFACE ---
st.set_page_config(page_title="Box Office Model", page_icon="🎬")
st.title("🎬 Box Office Model")

# Preset Selector
selected_preset = st.selectbox("Select Movie / Comp:", list(presets.keys()), index=0)
data = presets[selected_preset]

# --- SIDEBAR ---
st.sidebar.header("1. Live Tracking")

# Wikipedia
wiki_title = st.sidebar.text_input("Wikipedia Title", value=data['wiki'])
if st.sidebar.button("Fetch Wiki Views"):
    with st.spinner("Checking Wikipedia..."):
        views = get_wikipedia_views(wiki_title)
        st.sidebar.metric("Wiki Views (30d Avg)", f"{views:,}")

st.sidebar.divider()

# YouTube
st.sidebar.subheader("Official Trailer Views")
current_yt_views = data['yt_fallback']

if st.sidebar.button("Fetch LIVE YouTube Views"):
    with st.spinner("Checking YouTube..."):
        current_yt_views = get_youtube_views(data['yt_id'], data['yt_fallback'])
        st.sidebar.metric("Total Trailer Views", f"{current_yt_views:,}")
        st.sidebar.caption(f"Source: Official Trailer")
else:
    st.sidebar.caption(f"Current Data: {current_yt_views:,} views")

st.sidebar.divider()

st.sidebar.header("2. Model Inputs")
# The 'value' parameter sets the default based on the chosen preset
total_aware = st.sidebar.slider("Total Awareness (%)", 0, 100, value=data['aware'])
interest = st.sidebar.slider("Definite Interest (%)", 0, 100, value=data['interest'])
theaters = st.sidebar.number_input("Theater Count", 100, 5000, value=data['theaters'])
rt_score = st.sidebar.slider("Rotten Tomatoes Score", 0, 100, value=85)

# Multipliers
buzz = st.sidebar.slider("Social Buzz Multiplier", 0.5, 2.0, value=float(data['buzz']))
comp = st.sidebar.slider("Competition Factor", 0.5, 1.0, value=float(data['comp']))

# Calculations
prediction = calculate_box_office(interest, total_aware, theaters, rt_score, buzz, comp, current_yt_views)

# --- MAIN OUTPUT ---
st.divider()
col1, col2 = st.columns(2)

with col1:
    st.metric(label="Predicted Opening (3-Day)", value=f"${prediction/1_000_000:.2f}M")

with col2:
    st.write("### Analysis")
    if prediction > 100_000_000:
        st.success("🦄 MEGA BLOCKBUSTER")
    elif prediction > 30_000_000:
        st.success("🚀 MAJOR HIT")
    elif prediction > 10_000_000:
        st.info("✅ SOLID PERFORMER")
    else:
        st.error("⚠️ NICHE / LIMITED")

# Chart
st.write("### 📊 Benchmark Comparison")
chart_data = {
    "Prediction": prediction / 1_000_000,
    "Priscilla": 5.0,
    "The Iron Claw": 4.9,
    "Civil War (A24 Record)": 25.7,
    "Wicked (Projected)": 125.0 
}
st.bar_chart(chart_data)
