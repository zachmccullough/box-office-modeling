import streamlit as st
import requests
import re
import math
from datetime import datetime, timedelta

# --- PART 0: HIGH-END CONSUMER DESIGN (Light Mode) ---
st.set_page_config(page_title="Box Office Model", page_icon="🎬", layout="wide")

st.markdown("""
<style>
    /* 1. MAIN BACKGROUND & FONT */
    .stApp {
        background-color: #FFFFFF;
        color: #1A1A1C;
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    }
    
    /* 2. SIDEBAR STYLING (WIDER WIDTH FIX) */
    [data-testid="stSidebar"] {
        background-color: #F7F8FA;
        border-right: 1px solid #E2E2E5;
        min-width: 400px !important;
        max-width: 400px !important;
    }
    
    /* 3. METRIC CARDS (Clean White) */
    [data-testid="stMetric"] {
        background-color: #FFFFFF;
        padding: 16px;
        border-radius: 10px;
        border: 1px solid #E2E2E5;
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.04);
    }
    [data-testid="stMetricLabel"] {
        font-size: 0.85rem;
        font-weight: 500;
        color: #6B6F7B;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }
    [data-testid="stMetricValue"] {
        font-size: 1.8rem;
        font-weight: 700;
        color: #1A1A1C;
    }

    /* 4. INPUT FIELDS */
    .stTextInput input, .stNumberInput input, .stSelectbox div[data-baseweb="select"] {
        background-color: #FFFFFF;
        color: #1A1A1C;
        border: 1px solid #E2E2E5;
        border-radius: 8px;
        box-shadow: 0 1px 2px rgba(0, 0, 0, 0.02);
    }
    .stTextInput input:focus, .stNumberInput input:focus, .stSelectbox div[data-baseweb="select"]:focus {
        border-color: #5E6AD2; /* Indigo Accent */
        box-shadow: 0 0 0 3px rgba(94, 106, 210, 0.1);
    }
    
    /* 5. STATUS BADGES */
    .status-badge {
        display: inline-block;
        padding: 4px 10px;
        border-radius: 20px;
        font-size: 0.75rem;
        font-weight: 600;
        margin-bottom: 12px;
    }
    .status-success { background-color: #E6F6EC; color: #057A55; border: 1px solid #DEF7EC; }
    .status-warning { background-color: #FFF8C5; color: #9A6700; border: 1px solid #FBE7A1; }
    
    /* 6. HEADERS & DIVIDERS */
    h1, h2, h3 {
        color: #1A1A1C;
        font-weight: 700;
        letter-spacing: -0.5px;
    }
    hr {
        margin: 2em 0;
        border-color: #E2E2E5;
    }
    
    /* 7. ALERTS */
    .stAlert {
        background-color: #F7F8FA;
        border: 1px solid #E2E2E5;
        color: #1A1A1C;
    }
    
    /* 8. LINKS */
    a { color: #5E6AD2 !important; text-decoration: none; }
    a:hover { text-decoration: underline; }
    
    /* 9. CAPTIONS (Subtle) */
    .caption-text {
        font-size: 0.8rem;
        color: #6B6F7B;
        margin-top: -10px;
        margin-bottom: 15px;
    }

</style>
""", unsafe_allow_html=True)

# --- PART 1: CACHED DATA TOOLS ---
@st.cache_data(ttl=3600)
def get_live_data(wiki_title, yt_id, yt_fallback, rt_slug):
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
        wiki_views = 0

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

    # 3. Rotten Tomatoes
    rt_score = None 
    if rt_slug:
        try:
            url = f"https://www.rottentomatoes.com/m/{rt_slug}"
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36'}
            response = requests.get(url, headers=headers)
            match = re.search(r'tomatometerscore="(\d+)"', response.text)
            if match:
                rt_score = int(match.group(1))
        except:
            pass

    return wiki_views, yt_views, rt_score

def calculate_box_office(interest, total_aware, theaters, rt_score, buzz, comp, trailer_views):
    base_gross = (interest * 0.15) * (total_aware * 0.05) * 1_000_000
    
    trailer_multiplier = 1.0
    if trailer_views > 60_000_000: trailer_multiplier = 1.4
    elif trailer_views > 15_000_000: trailer_multiplier = 1.2
    base_gross = base_gross * trailer_multiplier

    if theaters > 3000:
        base_gross = base_gross * 3.0 
        if total_aware > 60: base_gross = base_gross * 1.25

    cap = 5000 if theaters > 3000 else 3500
    weighted_gross = (base_gross * 0.7) + ((theaters * cap) * 0.3)
    
    qual_mult = 1.15 if rt_score > 80 else (0.85 if rt_score < 50 else 1.0)
    raw = weighted_gross * qual_mult * buzz * comp

    if raw > 150_000_000:
        final = 150_000_000 + (math.sqrt(raw - 150_000_000) * 3500)
    else:
        final = raw
        
    return final

# --- PART 2: PRESETS ---
presets = {
    "Eternity (A24)": {
        "aware": 21, "interest": 34, "theaters": 2400, "buzz": 1.2, "comp": 0.85, 
        "wiki": "Eternity_(2025_film)", "yt_id": "irXTps1REHU", "yt_fallback": 9300000,
        "rt_slug": "eternity_2025", 
        "source_label": "Official Trailer", "source_status": "success",
        "tracking_source": "Real Data (The Quorum)",
        "competitors": "Wicked: Part Two, Zootopia 2",
        "benchmarks": {"Priscilla": 5.0, "Age of Adaline (Goal)": 13.2, "Me Before You (Breakout)": 18.7}
    },
    "Marty Supreme (A24)": {
        "aware": 30, "interest": 40, "theaters": 2200, "buzz": 1.3, "comp": 0.9, 
        "wiki": "Marty_Supreme", "yt_id": "s9gSuKaKcqM", "yt_fallback": 17800000,
        "rt_slug": "marty_supreme",
        "source_label": "Official Trailer", "source_status": "success",
        "tracking_source": "Estimated (Uncut Gems Comps)",
        "competitors": "Avatar: Fire and Ash, SpongeBob",
        "benchmarks": {"Uncut Gems (Wide)": 9.6, "Lady Bird (Wide)": 5.3, "Challengers": 15.0}
    },
    "Pillion (A24/Element)": {
        "aware": 10, "interest": 20, "theaters": 800, "buzz": 1.0, "comp": 0.95, 
        "wiki": "Pillion_(film)", "yt_id": "aTAacTUKK00", "yt_fallback": 500000,
        "rt_slug": "pillion",
        "source_label": "Teaser / First Look", "source_status": "success",
        "tracking_source": "Estimated (Arthouse Niche)",
        "competitors": "Limited Release Competition",
        "benchmarks": {"Past Lives (Wide)": 5.8, "The Whale (Wide)": 11.0, "Moonlight (Wide)": 1.5}
    },
    "The Moment (A24)": {
        "aware": 15, "interest": 25, "theaters": 2000, "buzz": 1.1, "comp": 0.9, 
        "wiki": "The_Moment_(2026_film)", "yt_id": "ey5YrCNH09g", "yt_fallback": 1500000,
        "rt_slug": "the_moment_2026",
        "source_label": "Official Trailer", "source_status": "success",
        "tracking_source": "Estimated (Sci-Fi Comps)",
        "competitors": "Project Hail Mary",
        "benchmarks": {"Ex Machina (Wide)": 5.4, "After Yang": 0.04, "Her (Wide)": 5.3}
    },
    "Wicked: Part Two": {
        "aware": 77, "interest": 50, "theaters": 4200, "buzz": 1.5, "comp": 0.8, 
        "wiki": "Wicked_(2024_film)", "yt_id": "vt98AlBDI9Y", "yt_fallback": 113000000,
        "rt_slug": "wicked_part_two",
        "source_label": "Official Trailer", "source_status": "success",
        "tracking_source": "Real Data (The Quorum)",
        "competitors": "Zootopia 2, Eternity",
        "benchmarks": {"Frozen II": 130.0, "Barbie": 162.0, "Wonka": 39.0}
    },
    "Zootopia 2": {
        "aware": 68, "interest": 53, "theaters": 4300, "buzz": 1.3, "comp": 0.8, 
        "wiki": "Zootopia_2", "yt_id": "xo4rkcC7kFc", "yt_fallback": 25000000,
        "rt_slug": "zootopia_2",
        "source_label": "Official Trailer", "source_status": "success",
        "tracking_source": "Real Data (The Quorum)",
        "competitors": "Wicked: Part Two",
        "benchmarks": {"Inside Out 2": 154.0, "Super Mario Bros": 146.0, "Moana": 56.6}
    },
    "Elden Ring (Hypothetical)": {
        "aware": 60, "interest": 45, "theaters": 4000, "buzz": 1.4, "comp": 0.8, 
        "wiki": "Elden_Ring", "yt_id": "E3Huy2cdih0", "yt_fallback": 14000000,
        "rt_slug": None,
        "source_label": "Proxy (Game Trailer)", "source_status": "warning",
        "tracking_source": "Hypothetical (Gamer Comps)",
        "competitors": "Direct-to-Fan Event",
        "benchmarks": {"Dune: Part One": 41.0, "Five Nights at Freddy's": 80.0, "Uncharted": 44.0}
    },
}

# --- APP UI ---
st.title("🎬 Box Office Model")
st.markdown("---")

# 1. SELECTOR
selected_preset = st.selectbox("Select Movie Project:", list(presets.keys()), index=0)
data = presets[selected_preset]

# 2. AUTO-FETCH
live_wiki, live_yt, live_rt = get_live_data(data['wiki'], data['yt_id'], data['yt_fallback'], data['rt_slug'])

# --- SIDEBAR ---
st.sidebar.markdown("### 📡 Live Signal Tracking")
st.sidebar.caption("Real-time metrics from APIs")

# CUSTOM BADGE FOR SOURCE
badge_class = "status-success" if data['source_status'] == "success" else "status-warning"
st.sidebar.markdown(f'<span class="status-badge {badge_class}">{data["source_label"]}</span>', unsafe_allow_html=True)

col_a, col_b = st.sidebar.columns(2)
with col_a:
    st.metric("Wiki Views", f"{live_wiki:,}", help="30-Day Daily Avg")
with col_b:
    st.metric("Trailer Views", f"{live_yt/1000000:.1f}M", help="YouTube View Count")

st.sidebar.link_button(f"▶ Watch Trailer", f"https://www.youtube.com/watch?v={data['yt_id']}")
st.sidebar.markdown("---")

# --- INPUTS SECTION ---
st.sidebar.markdown("### 🎛️ Scenario Inputs")

# 1. THEATER COUNT (FIXED: ADDED STEP)
st.sidebar.caption("Distribution Strategy")
theaters = st.sidebar.number_input("Theater Count", 100, 5000, value=data['theaters'], step=100)
st.sidebar.markdown("---")

# 2. AWARENESS & INTEREST (FIXED: TIED TO SOURCE)
st.sidebar.markdown("#### 📊 Audience Tracking")

# Dynamic Source Label placed RIGHT above the sliders
if "Real" in data['tracking_source']:
    st.sidebar.caption(f"✅ Source: {data['tracking_source']}")
else:
    st.sidebar.caption(f"⚠️ Source: {data['tracking_source']}")

total_aware = st.sidebar.slider("Total Awareness (%)", 0, 100, value=data['aware'])
interest = st.sidebar.slider("Definite Interest (%)", 0, 100, value=data['interest'])

st.sidebar.markdown("---")

# 3. OTHER FACTORS
rt_label = f"Rotten Tomatoes Score (Live)" if live_rt else "Estimated Score (Unreleased)"
rt_default = live_rt if live_rt else 70
if not live_rt: st.sidebar.caption("⚠️ No live score. Defaulting to Neutral (70).")
rt_score = st.sidebar.slider(rt_label, 0, 100, value=rt_default)

buzz = st.sidebar.slider("Social Buzz Multiplier", 0.5, 2.0, value=float(data['buzz']))

# 4. COMPETITION (FIXED: LIST UNDER SLIDER)
comp = st.sidebar.slider("Competition Factor", 0.5, 1.0, value=float(data['comp']))
# The list is now a caption underneath the slider
st.sidebar.caption(f"**Opening Against:** {data['competitors']}")

# --- CALCULATIONS ---
prediction = calculate_box_office(interest, total_aware, theaters, rt_score, buzz, comp, live_yt)

# --- MAIN DASHBOARD ---
col1, col2 = st.columns([1, 2])

with col1:
    st.metric(label="Predicted Opening (3-Day)", value=f"${prediction/1_000_000:.2f}M")
    
    if prediction > 100_000_000:
        st.success("🦄 MEGA BLOCKBUSTER")
    elif prediction > 30_000_000:
        st.success("🚀 MAJOR HIT")
    elif prediction > 10_000_000:
        st.info("✅ SOLID PERFORMER")
    else:
        st.error("⚠️ NICHE / LIMITED")

with col2:
    st.markdown(f"#### 📊 Benchmark Comparison: {selected_preset.split('(')[0]}")
    chart_data = data['benchmarks'].copy()
    chart_data["PREDICTION"] = prediction / 1_000_000
    sorted_chart = dict(sorted(chart_data.items(), key=lambda item: item[1]))
    st.bar_chart(sorted_chart)

# --- FOOTER ---
with st.expander("🔎 View Methodology"):
    st.markdown("""
    **The Formula:**
    1. **Base Gross:** Derived from `Awareness` × `Interest` (Linear scaling).
    2. **Trailer Boost:** If YouTube views > 10M, we apply a **1.25x** multiplier. If > 50M, **1.5x**.
    3. **Social Buzz:** Multiplied by your manual slider input (e.g., 1.2x).
    4. **Competition:** Dampened by the competition factor (e.g., 0.85x).
    5. **Quality:** If RT Score > 80, **+15%**. If < 50, **-15%**.
    6. **Reality Cap:** For predictions over $150M, we apply logarithmic dampening.
    """)
