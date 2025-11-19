import streamlit as st
import requests
import re
import math
import pandas as pd
import altair as alt
from datetime import datetime, timedelta

# --- PART 0: SHADCN/UI THEME (ZINC) ---
st.set_page_config(page_title="Box Office Model", page_icon="🎬", layout="wide")

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

    :root {
        --background: #FFFFFF;
        --foreground: #09090B;
        --card: #FFFFFF;
        --card-foreground: #09090B;
        --border: #E4E4E7;
        --input: #E4E4E7;
        --ring: #18181B;
        --radius: 0.5rem;
    }

    .stApp {
        background-color: var(--background);
        color: var(--foreground);
        font-family: 'Inter', sans-serif;
    }
    
    [data-testid="stSidebar"] {
        background-color: #FAFAFA;
        border-right: 1px solid var(--border);
        min-width: 400px !important;
        max-width: 400px !important;
    }

    [data-testid="stMetric"], [data-testid="stExpander"] {
        background-color: var(--card);
        color: var(--card-foreground);
        border-radius: var(--radius);
        border: 1px solid var(--border);
        box-shadow: 0 1px 2px 0 rgba(0, 0, 0, 0.05);
        padding: 16px;
    }
    
    h1, h2, h3 {
        font-family: 'Inter', sans-serif;
        font-weight: 700;
        letter-spacing: -0.025em;
        color: var(--foreground);
    }
    
    .status-badge {
        display: inline-flex;
        align-items: center;
        border-radius: 9999px;
        padding: 0.25rem 0.75rem;
        font-size: 0.75rem;
        font-weight: 600;
        line-height: 1;
        margin-bottom: 12px;
    }
    .status-success { background-color: #DCFCE7; color: #14532D; border: 1px solid #bbf7d0; }
    .status-warning { background-color: #FEF9C3; color: #713F12; border: 1px solid #fef08a; }
    .status-neutral { background-color: #F3F4F6; color: #374151; border: 1px solid #E5E7EB; }
    
    /* Tuning Advice Box */
    .tuning-box {
        background-color: #F8FAFC;
        border-left: 4px solid #3B82F6;
        padding: 1rem;
        border-radius: 4px;
        margin-top: 1rem;
        font-size: 0.9rem;
    }

</style>
""", unsafe_allow_html=True)

# --- PART 1: CACHED DATA TOOLS ---
@st.cache_data(ttl=3600)
def get_live_data(wiki_title, yt_id, yt_fallback, rt_slug):
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

    rt_score = None 
    if rt_slug:
        try:
            url = f"https://www.rottentomatoes.com/m/{rt_slug}"
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36'}
            response = requests.get(url, headers=headers)
            match = re.search(r'tomatometerscore="(\d+)"', response.text)
            if not match: match = re.search(r'"ratingValue":\s*"(\d+)"', response.text)
            if not match: match = re.search(r'class="percentage">\s*(\d+)%', response.text)

            if match:
                rt_score = int(match.group(1))
        except:
            pass

    return wiki_views, yt_views, rt_score

def calculate_box_office(interest, total_aware, theaters, rt_score, buzz, comp, trailer_views, intl_multiplier):
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
    raw_opening = weighted_gross * qual_mult * buzz * comp

    if raw_opening > 150_000_000:
        final_opening = 150_000_000 + (math.sqrt(raw_opening - 150_000_000) * 3500)
    else:
        final_opening = raw_opening
    
    legs = 2.7
    if rt_score > 80: legs += 0.5
    elif rt_score < 50: legs -= 0.6
    if theaters < 2000: legs += 0.4
    
    dom_total = final_opening * legs
    global_total = dom_total * intl_multiplier
        
    return final_opening, dom_total, global_total

# --- PART 2: PRESETS (MIXED UPCOMING & HISTORICAL) ---
presets = {
    # --- UPCOMING ---
    "Eternity (A24)": {
        "type": "upcoming",
        "aware": 21, "interest": 34, "theaters": 2400, "buzz": 1.2, "comp": 0.85, 
        "wiki": "Eternity_(2025_film)", "yt_id": "irXTps1REHU", "yt_fallback": 9300000,
        "rt_slug": "eternity_2025", "source_label": "Official Trailer", "source_status": "success",
        "tracking_source": "Real Data (The Quorum)",
        "competitors": "Wicked: Part Two, Zootopia 2",
        "intl_multiplier": 1.8, 
        "benchmarks": {"Priscilla": 5.0, "Age of Adaline": 13.2, "Me Before You": 18.7}
    },
    "Wicked: Part Two": {
        "type": "upcoming",
        "aware": 77, "interest": 50, "theaters": 4200, "buzz": 1.5, "comp": 0.8, 
        "wiki": "Wicked_(2024_film)", "yt_id": "vt98AlBDI9Y", "yt_fallback": 113000000,
        "rt_slug": "wicked_part_two", "source_label": "Official Trailer", "source_status": "success",
        "tracking_source": "Real Data (The Quorum)",
        "competitors": "Zootopia 2, Eternity",
        "intl_multiplier": 1.6, 
        "benchmarks": {"Frozen II": 130.0, "Barbie": 162.0, "Wonka": 39.0}
    },
    
    # --- HISTORICAL / BACKTESTING ---
    "Barbie (Historical)": {
        "type": "historical",
        "actual_opening": 162.0, # Millions
        "aware": 95, "interest": 75, "theaters": 4243, "buzz": 1.8, "comp": 0.8, 
        "wiki": "Barbie_(film)", "yt_id": "pBk4NYhWNMM", "yt_fallback": 80000000,
        "rt_slug": "barbie", "source_label": "Historical Data", "source_status": "neutral",
        "tracking_source": "Historical NRG Reports",
        "competitors": "Oppenheimer",
        "intl_multiplier": 2.1,
        "benchmarks": {"Actual Opening": 162.0, "Mario Bros": 146.3}
    },
    "Five Nights at Freddy's (Historical)": {
        "type": "historical",
        "actual_opening": 80.0,
        "aware": 60, "interest": 55, "theaters": 3675, "buzz": 1.6, "comp": 0.9, 
        "wiki": "Five_Nights_at_Freddy's_(film)", "yt_id": "0VH9WCFV6Xw", "yt_fallback": 50000000,
        "rt_slug": "five_nights_at_freddys", "source_label": "Historical Data", "source_status": "neutral",
        "tracking_source": "Historical NRG Reports",
        "competitors": "Taylor Swift: Eras Tour (Holdover)",
        "intl_multiplier": 1.8,
        "benchmarks": {"Actual Opening": 80.0, "Halloween": 76.2}
    },
    "The Fall Guy (Historical)": {
        "type": "historical",
        "actual_opening": 27.7,
        "aware": 65, "interest": 45, "theaters": 4002, "buzz": 1.0, "comp": 0.9, 
        "wiki": "The_Fall_Guy_(2024_film)", "yt_id": "j7jPnwVGdZ8", "yt_fallback": 25000000,
        "rt_slug": "the_fall_guy_2024", "source_label": "Historical Data", "source_status": "neutral",
        "tracking_source": "Historical NRG Reports",
        "competitors": "Tarot, Challengers",
        "intl_multiplier": 2.0,
        "benchmarks": {"Actual Opening": 27.7, "Bullet Train": 30.0}
    }
}

# --- APP UI ---
st.title("🎬 Box Office Model")
st.markdown("---")

selected_preset = st.selectbox("Select Movie Project:", list(presets.keys()), index=0)
data = presets[selected_preset]

live_wiki, live_yt, live_rt = get_live_data(data['wiki'], data['yt_id'], data['yt_fallback'], data['rt_slug'])

# --- SIDEBAR ---
st.sidebar.markdown("### 📡 Live Signal Tracking")
badge_class = "status-success" if data['source_status'] == "success" else "status-neutral"
st.sidebar.markdown(f'<span class="status-badge {badge_class}">{data["source_label"]}</span>', unsafe_allow_html=True)

col_a, col_b = st.sidebar.columns(2)
with col_a:
    st.metric("Wiki Views", f"{live_wiki:,}", help="30-Day Daily Avg")
with col_b:
    st.metric("Trailer Views", f"{live_yt/1000000:.1f}M", help="YouTube View Count")

st.sidebar.markdown("---")
st.sidebar.markdown("### 🎛️ Scenario Inputs")

theaters = st.sidebar.number_input("Theater Count", 100, 5000, value=data['theaters'], step=100)

if "Real" in data['tracking_source']:
    st.sidebar.caption(f"✅ Source: {data['tracking_source']}")
else:
    st.sidebar.caption(f"⚠️ Source: {data['tracking_source']}")
total_aware = st.sidebar.slider("Total Awareness (%)", 0, 100, value=data['aware'])
interest = st.sidebar.slider("Definite Interest (%)", 0, 100, value=data['interest'])

st.sidebar.markdown("---")

if live_rt:
    rt_label = f"Rotten Tomatoes Score (Live)"
    rt_default = live_rt
else:
    rt_label = "Estimated Rotten Tomatoes Score"
    rt_default = 70

rt_score = st.sidebar.slider(rt_label, 0, 100, value=rt_default)
buzz = st.sidebar.slider("Social Buzz Multiplier", 0.5, 2.0, value=float(data['buzz']))
comp = st.sidebar.slider("Competition Factor", 0.5, 1.0, value=float(data['comp']))
st.sidebar.caption(f"**Opening Against:** {data['competitors']}")

# --- CALCULATIONS ---
opening, dom_total, global_total = calculate_box_office(interest, total_aware, theaters, rt_score, buzz, comp, live_yt, data['intl_multiplier'])

# --- MAIN DASHBOARD ---
# If Historical, we show a Split View (Model vs Actual)
if data.get('type') == 'historical':
    actual = data['actual_opening'] * 1_000_000
    delta = opening - actual
    percent_error = (delta / actual) * 100
    
    st.info(f"🕰️ **BACKTEST MODE:** Comparing model prediction against actual 2023/2024 results.")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Model Prediction", f"${opening/1_000_000:.2f}M")
    with col2:
        st.metric("Actual Opening", f"${data['actual_opening']}M", delta=f"{percent_error:.1f}% Error", delta_color="inverse")
    with col3:
        if abs(percent_error) < 15:
            st.success("✅ Model Accurate")
        elif abs(percent_error) < 30:
            st.warning("⚠️ Moderate Drift")
        else:
            st.error("❌ Model Failed")

    # AUTO-TUNER LOGIC
    advice = ""
    if percent_error < -20:
        advice = "📉 **Diagnosis:** The model was too conservative. <br> **Fix:** For films like this (High Awareness), consider increasing the base Interest multiplier."
    elif percent_error > 20:
        advice = "📈 **Diagnosis:** The model was too optimistic. <br> **Fix:** The 'Social Buzz' or 'Trailer Views' might be weighting 'Empty Hype' too heavily vs. actual ticket sales."
    else:
        advice = "✨ **Diagnosis:** The model logic holds up well for this genre."
        
    st.markdown(f"""<div class="tuning-box">{advice}</div>""", unsafe_allow_html=True)

else:
    # Standard Future View
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Predicted Opening", f"${opening/1_000_000:.2f}M")
    with col2:
        st.metric("Proj. Domestic", f"${dom_total/1_000_000:.2f}M")
    with col3:
        st.metric("Proj. Global", f"${global_total/1_000_000:.2f}M")

st.markdown("---")

# --- CHART ---
col_chart, col_info = st.columns([2, 1])

with col_chart:
    st.markdown(f"#### 📊 Benchmark Comparison")
    
    chart_data = data['benchmarks'].copy()
    chart_data["PREDICTION"] = opening / 1_000_000
    
    # If historical, highlight the ACTUAL bar too
    if data.get('type') == 'historical':
        chart_data["ACTUAL"] = data['actual_opening']

    df = pd.DataFrame({
        "Movie": list(chart_data.keys()),
        "Gross": list(chart_data.values())
    })

    base = alt.Chart(df).encode(
        x=alt.X('Gross', title='Opening Weekend ($M)', axis=alt.Axis(grid=False)),
        y=alt.Y('Movie', sort='-x', title=None, axis=alt.Axis(labelLimit=200)),
        tooltip=['Movie', 'Gross']
    )

    # Color Logic: Indigo for Prediction, Green for Actual, Grey for Benchmarks
    bars = base.mark_bar().encode(
        color=alt.condition(
            alt.datum.Movie == 'PREDICTION',
            alt.value('#18181B'),  # Prediction = Black
            alt.condition(
                alt.datum.Movie == 'ACTUAL',
                alt.value('#10B981'), # Actual = Green
                alt.value('#E4E4E7')  # Benchmarks = Grey
            )
        )
    )

    text = base.mark_text(align='left', dx=3).encode(text=alt.Text('Gross', format=',.1f'))
    
    chart = (bars + text).properties(height=300).configure_view(strokeWidth=0)
    st.altair_chart(chart, use_container_width=True)

with col_info:
    with st.expander("🔎 View Methodology", expanded=True):
        st.markdown("""
        **1. Opening Weekend:**
        * Driven by Awareness × Interest.
        * Boosted by Trailer Views (>10M).
        
        **2. The "Reality Cap":**
        * Predictions > $150M are dampened logarithmically to simulate capacity limits.
        
        **3. Historical Backtesting:**
        * Select a "Historical" movie to see how this model would have performed against real results.
        """)
