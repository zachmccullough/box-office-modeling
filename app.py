import streamlit as st
import requests
import re
import math
from datetime import datetime, timedelta

# --- PART 1: CACHED DATA TOOLS ---
@st.cache_data(ttl=3600)
def get_live_data(wiki_title, yt_id, yt_fallback):
    """
    Fetches BOTH Wikipedia and YouTube data in one go.
    Returns a tuple: (wiki_views, yt_views)
    """
    # 1. Wikipedia
    wiki_views = 0
    try:
        headers = {'User-Agent': 'BoxOfficePredictor/1.0'}
        end = datetime.now()
        start = end - timedelta(days=30)
        url = f"https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/en.wikipedia/all-access/user/{wiki_title}/daily/{start.strftime('%Y%m%d')}/{end.strftime('%Y%m%d')}"
        data = requests.get(url, headers=headers).json()
        total = sum([item['views'] for item in data['items']])
        wiki_views = int(total / len(data['items']))
    except:
        wiki_views = 0 # Fail silent

    # 2. YouTube
    yt_views = yt_fallback
    try:
        url = f"https://www.youtube.com/watch?v={yt_id}"
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        response = requests.get(url, headers=headers)
        match = re.search(r'"viewCount":"(\d+)"', response.text)
        if match:
            yt_views = int(match.group(1))
    except:
        pass 

    return wiki_views, yt_views

def calculate_box_office(interest, total_aware, theaters, rt_score, buzz, comp, trailer_views):
    # Base Calculation
    base_gross = (interest * 0.15) * (total_aware * 0.05) * 1_000_000
    
    # Trailer Boost
    trailer_multiplier = 1.0
    if trailer_views > 60_000_000: trailer_multiplier = 1.4
    elif trailer_views > 15_000_000: trailer_multiplier = 1.2
    base_gross = base_gross * trailer_multiplier

    # Blockbuster Adjustment
    if theaters > 3000:
        base_gross = base_gross * 3.0 
        if total_aware > 60: base_gross = base_gross * 1.25

    # Capacity Logic
    cap = 5000 if theaters > 3000 else 3500
    weighted_gross = (base_gross * 0.7) + ((theaters * cap) * 0.3)
    
    # Multipliers
    qual_mult = 1.15 if rt_score > 80 else (0.85 if rt_score < 50 else 1.0)
    raw = weighted_gross * qual_mult * buzz * comp

    # Reality Cap
    if raw > 150_000_000:
        final = 150_000_000 + (math.sqrt(raw - 150_000_000) * 3500)
    else:
        final = raw
        
    return final

# --- PART 2: PRESETS WITH CORRECTED BENCHMARKS ---
presets = {
    "Eternity (A24)": {
        "aware": 21, "interest": 34, "theaters": 2400, "buzz": 1.2, "comp": 0.85, 
        "wiki": "Eternity_(2025_film)", "yt_id": "irXTps1REHU", "yt_fallback": 9300000,
        "benchmarks": {"Priscilla": 5.0, "The Iron Claw": 4.9, "Civil War (A24 Max)": 25.7}
    },
    "Marty Supreme (A24)": {
        "aware": 30, "interest": 40, "theaters": 2200, "buzz": 1.3, "comp": 0.9, 
        "wiki": "Marty_Supreme", "yt_id": "s9gSuKaKcqM", "yt_fallback": 17800000,
        "benchmarks": {"Uncut Gems (Wide)": 9.6, "Lady Bird (Wide)": 5.3, "Challengers": 15.0}
    },
    "Pillion (A24/Element)": {
        "aware": 10, "interest": 20, "theaters": 800, "buzz": 1.0, "comp": 0.95, 
        "wiki": "Pillion_(film)", "yt_id": "aTAacTUKK00", "yt_fallback": 500000,
        "benchmarks": {"Past Lives (Wide)": 5.8, "The Whale (Wide)": 11.0, "Moonlight (Wide)": 1.5}
    },
    "The Moment (A24)": {
        "aware": 15, "interest": 25, "theaters": 2000, "buzz": 1.1, "comp": 0.9, 
        "wiki": "The_Moment_(2026_film)", "yt_id": "ey5YrCNH09g", "yt_fallback": 1500000,
        "benchmarks": {"Ex Machina (Wide)": 5.4, "After Yang": 0.04, "Her (Wide)": 5.3}
    },
    "Wicked: Part Two": {
        "aware": 77, "interest": 50, "theaters": 4200, "buzz": 1.5, "comp": 0.8, 
        "wiki": "Wicked_(2024_film)", "yt_id": "vt98AlBDI9Y", "yt_fallback": 113000000,
        "benchmarks": {"Frozen II": 130.0, "Barbie": 162.0, "Wonka": 39.0}
    },
    "Zootopia 2": {
        "aware": 68, "interest": 53, "theaters": 4300, "buzz": 1.3, "comp": 0.8, 
        "wiki": "Zootopia_2", "yt_id": "xo4rkcC7kFc", "yt_fallback": 25000000,
        "benchmarks": {"Inside Out 2": 154.0, "Super Mario Bros": 146.0, "Moana": 56.6}
    },
    "Elden Ring (Hypothetical)": {
        "aware": 60, "interest": 45, "theaters": 4000, "buzz": 1.4, "comp": 0.8, 
        "wiki": "Elden_Ring", "yt_id": "E3Huy2cdih0", "yt_fallback": 14000000,
        "benchmarks": {"Dune: Part One": 41.0, "Five Nights at Freddy's": 80.0, "Uncharted": 44.0}
    },
}

# --- PART 3: APP INTERFACE ---
st.set_page_config(page_title="Box Office Model", page_icon="🎬")
st.title("🎬 Box Office Model")

# 1. SELECT MOVIE
selected_preset = st.selectbox("Select Movie / Comp:", list(presets.keys()), index=0)
data = presets[selected_preset]

# 2. AUTO-FETCH DATA
live_wiki, live_yt = get_live_data(data['wiki'], data['yt_id'], data['yt_fallback'])

# --- SIDEBAR ---
st.sidebar.header("Live Tracking Data")
st.sidebar.caption("Auto-fetched from API")
col_a, col_b = st.sidebar.columns(2)
with col_a:
    st.metric("Wiki Views", f"{live_wiki:,}", help="30-Day Daily Avg")
with col_b:
    st.metric("Trailer Views", f"{live_yt/1000000:.1f}M", help="Official YouTube Upload")

st.sidebar.divider()
st.sidebar.header("Model Inputs")

total_aware = st.sidebar.slider("Total Awareness (%)", 0, 100, value=data['aware'])
interest = st.sidebar.slider("Definite Interest (%)", 0, 100, value=data['interest'])
theaters = st.sidebar.number_input("Theater Count", 100, 5000, value=data['theaters'])
rt_score = st.sidebar.slider("Rotten Tomatoes Score", 0, 100, value=85)
buzz = st.sidebar.slider("Social Buzz Multiplier", 0.5, 2.0, value=float(data['buzz']))
comp = st.sidebar.slider("Competition Factor", 0.5, 1.0, value=float(data['comp']))

# --- CALCULATIONS ---
prediction = calculate_box_office(interest, total_aware, theaters, rt_score, buzz, comp, live_yt)

# --- DASHBOARD ---
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

# --- DYNAMIC CHART ---
st.write(f"### 📊 Benchmarks: {selected_preset.split('(')[0]}")

# Create chart data dynamically based on the selected movie
chart_data = data['benchmarks'].copy()
chart_data["PREDICTION"] = prediction / 1_000_000

# Sort dict for better visual
sorted_chart = dict(sorted(chart_data.items(), key=lambda item: item[1]))

st.bar_chart(sorted_chart)
st.caption("Benchmarks are Actual Wide Release Opening Weekends in Millions.")
