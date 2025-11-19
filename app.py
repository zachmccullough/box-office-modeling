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
    [data-testid="stMetricLabel"] {
        font-size: 0.875rem;
        font-weight: 500;
        color: #71717A;
    }
    [data-testid="stMetricValue"] {
        font-size: 1.5rem;
        font-weight: 700;
        letter-spacing: -0.025em;
    }

    .stTextInput input, .stNumberInput input, .stSelectbox div[data-baseweb="select"] {
        background-color: transparent;
        border-radius: var(--radius);
        border: 1px solid var(--input);
        color: var(--foreground);
        font-size: 0.875rem;
        height: 2.5rem;
        transition: all 0.1s;
    }
    .stTextInput input:focus, .stNumberInput input:focus, .stSelectbox div[data-baseweb="select"]:focus-within {
        border-color: var(--ring);
        box-shadow: 0 0 0 2px var(--background), 0 0 0 4px var(--ring);
        outline: none;
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
    
    a { color: var(--foreground) !important; text-decoration: underline; text-decoration-thickness: 1px;}
    a:hover { opacity: 0.8; }

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
    # 1. OPENING WEEKEND
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
    
    # 2. DOMESTIC TOTAL (LEGS)
    legs = 2.7
    if rt_score > 80: legs += 0.5
    elif rt_score < 50: legs -= 0.6
    if theaters < 2000: legs += 0.4
    
    dom_total = final_opening * legs
    
    # 3. GLOBAL TOTAL (Calculated using specific genre multiplier)
    # 1.6x = Domestic Heavy (Musicals, Comedies)
    # 2.5x = Global Appeal (Action, Animation)
    global_total = dom_total * intl_multiplier
        
    return final_opening, dom_total, global_total

# --- PART 2: PRESETS ---
presets = {
    "Eternity (A24)": {
        "aware": 21, "interest": 34, "theaters": 2400, "buzz": 1.2, "comp": 0.85, 
        "wiki": "Eternity_(2025_film)", "yt_id": "irXTps1REHU", "yt_fallback": 9300000,
        "rt_slug": "eternity_2025", 
        "source_label": "Official Trailer", "source_status": "success",
        "tracking_source": "Real Data (The Quorum)",
        "competitors": "Wicked: Part Two, Zootopia 2",
        "intl_multiplier": 1.8, # A24 Romance (US Heavy)
        "benchmarks": {"Priscilla": 5.0, "Age of Adaline (Goal)": 13.2, "Me Before You (Breakout)": 18.7}
    },
    "Marty Supreme (A24)": {
        "aware": 30, "interest": 40, "theaters": 2200, "buzz": 1.3, "comp": 0.9, 
        "wiki": "Marty_Supreme", "yt_id": "s9gSuKaKcqM", "yt_fallback": 17800000,
        "rt_slug": "marty_supreme",
        "source_label": "Official Trailer", "source_status": "success",
        "tracking_source": "Estimated (Uncut Gems Comps)",
        "competitors": "Avatar: Fire and Ash, SpongeBob",
        "intl_multiplier": 1.8, # A24 Biopic (US Heavy)
        "benchmarks": {"Uncut Gems (Wide)": 9.6, "Lady Bird (Wide)": 5.3, "Challengers": 15.0}
    },
    "Pillion (A24/Element)": {
        "aware": 10, "interest": 20, "theaters": 800, "buzz": 1.0, "comp": 0.95, 
        "wiki": "Pillion_(film)", "yt_id": "aTAacTUKK00", "yt_fallback": 500000,
        "rt_slug": "pillion",
        "source_label": "Teaser / First Look", "source_status": "success",
        "tracking_source": "Estimated (Arthouse Niche)",
        "competitors": "Limited Release Competition",
        "intl_multiplier": 1.5, # Arthouse (Very US Heavy)
        "benchmarks": {"Past Lives (Wide)": 5.8, "The Whale (Wide)": 11.0, "Moonlight (Wide)": 1.5}
    },
    "The Moment (A24)": {
        "aware": 15, "interest": 25, "theaters": 2000, "buzz": 1.1, "comp": 0.9, 
        "wiki": "The_Moment_(2026_film)", "yt_id": "ey5YrCNH09g", "yt_fallback": 1500000,
        "rt_slug": "the_moment_2026",
        "source_label": "Official Trailer", "source_status": "success",
        "tracking_source": "Estimated (Sci-Fi Comps)",
        "competitors": "Project Hail Mary",
        "intl_multiplier": 2.0, # Sci-Fi (Travels better than drama)
        "benchmarks": {"Ex Machina (Wide)": 5.4, "After Yang": 0.04, "Her (Wide)": 5.3}
    },
    "Wicked: Part Two": {
        "aware": 77, "interest": 50, "theaters": 4200, "buzz": 1.5, "comp": 0.8, 
        "wiki": "Wicked_(2024_film)", "yt_id": "vt98AlBDI9Y", "yt_fallback": 113000000,
        "rt_slug": "wicked_part_two",
        "source_label": "Official Trailer", "source_status": "success",
        "tracking_source": "Real Data (The Quorum)",
        "competitors": "Zootopia 2, Eternity",
        "intl_multiplier": 1.6, # Musical (Domestic Heavy - Matches Wicked 1)
        "benchmarks": {"Frozen II": 130.0, "Barbie": 162.0, "Wonka": 39.0}
    },
    "Zootopia 2": {
        "aware": 68, "interest": 53, "theaters": 4300, "buzz": 1.3, "comp": 0.8, 
        "wiki": "Zootopia_2", "yt_id": "xo4rkcC7kFc", "yt_fallback": 25000000,
        "rt_slug": "zootopia_2",
        "source_label": "Official Trailer", "source_status": "success",
        "tracking_source": "Real Data (The Quorum)",
        "competitors": "Wicked: Part Two",
        "intl_multiplier": 2.8, # Animation (Massive Global Appeal)
        "benchmarks": {"Inside Out 2": 154.0, "Super Mario Bros": 146.0, "Moana": 56.6}
    },
    "Elden Ring (Hypothetical)": {
        "aware": 60, "interest": 45, "theaters": 4000, "buzz": 1.4, "comp": 0.8, 
        "wiki": "Elden_Ring", "yt_id": "E3Huy2cdih0", "yt_fallback": 14000000,
        "rt_slug": None,
        "source_label": "Proxy (Game Trailer)", "source_status": "warning",
        "tracking_source": "Hypothetical (Gamer Comps)",
        "competitors": "Direct-to-Fan Event",
        "intl_multiplier": 2.2, # Gaming IP (Strong Asia/EU Appeal)
        "benchmarks": {"Dune: Part One": 41.0, "Five Nights at Freddy's": 80.0, "Uncharted": 44.0}
    },
}

# --- APP UI ---
st.title("🎬 Box Office Model")
st.markdown("---")

selected_preset = st.selectbox("Select Movie Project:", list(presets.keys()), index=0)
data = presets[selected_preset]

live_wiki, live_yt, live_rt = get_live_data(data['wiki'], data['yt_id'], data['yt_fallback'], data['rt_slug'])

# --- SIDEBAR ---
st.sidebar.markdown("### 📡 Live Signal Tracking")
st.sidebar.caption("Real-time metrics from APIs")

badge_class = "status-success" if data['source_status'] == "success" else "status-warning"
st.sidebar.markdown(f'<span class="status-badge {badge_class}">{data["source_label"]}</span>', unsafe_allow_html=True)

col_a, col_b = st.sidebar.columns(2)
with col_a:
    st.metric("Wiki Views", f"{live_wiki:,}", help="30-Day Daily Avg")
with col_b:
    st.metric("Trailer Views", f"{live_yt/1000000:.1f}M", help="YouTube View Count")

st.sidebar.link_button(f"▶ Watch Trailer", f"https://www.youtube.com/watch?v={data['yt_id']}")
st.sidebar.markdown("---")

st.sidebar.markdown("### 🎛️ Scenario Inputs")

st.sidebar.caption("Distribution Strategy")
theaters = st.sidebar.number_input("Theater Count", 100, 5000, value=data['theaters'], step=100)
st.sidebar.markdown("---")

st.sidebar.markdown("#### 📊 Audience Tracking")
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
    st.sidebar.success(f"✅ Live Score Found: {live_rt}%")
else:
    rt_label = "Estimated Rotten Tomatoes Score"
    rt_default = 70
    st.sidebar.caption("⚠️ No live score. Defaulting to Neutral (70).")

rt_score = st.sidebar.slider(rt_label, 0, 100, value=rt_default)
buzz = st.sidebar.slider("Social Buzz Multiplier", 0.5, 2.0, value=float(data['buzz']))

comp = st.sidebar.slider("Competition Factor", 0.5, 1.0, value=float(data['comp']))
st.sidebar.caption(f"**Opening Against:** {data['competitors']}")

# --- CALCULATIONS ---
opening, dom_total, global_total = calculate_box_office(interest, total_aware, theaters, rt_score, buzz, comp, live_yt, data['intl_multiplier'])

# --- MAIN DASHBOARD ---
col1, col2, col3 = st.columns(3)

with col1:
    st.metric(label="Predicted Opening (3-Day)", value=f"${opening/1_000_000:.2f}M")
with col2:
    st.metric(label="Projected Domestic Total", value=f"${dom_total/1_000_000:.2f}M")
with col3:
    st.metric(label="Projected Global Total", value=f"${global_total/1_000_000:.2f}M")

st.markdown("---")

# --- CHART ---
col_chart, col_info = st.columns([2, 1])

with col_chart:
    st.markdown(f"#### 📊 Benchmark Comparison: {selected_preset.split('(')[0]}")
    
    chart_data = data['benchmarks'].copy()
    chart_data["PREDICTION"] = opening / 1_000_000
    
    df = pd.DataFrame({
        "Movie": list(chart_data.keys()),
        "Gross": list(chart_data.values())
    })

    base = alt.Chart(df).encode(
        x=alt.X('Gross', title='Opening Weekend ($M)', axis=alt.Axis(grid=False)),
        y=alt.Y('Movie', sort='-x', title=None, axis=alt.Axis(labelLimit=200)),
        tooltip=['Movie', 'Gross']
    )

    bars = base.mark_bar().encode(
        color=alt.condition(
            alt.datum.Movie == 'PREDICTION',
            alt.value('#18181B'),
            alt.value('#E4E4E7')
        )
    )

    text = base.mark_text(
        align='left',
        baseline='middle',
        dx=3
    ).encode(
        text=alt.Text('Gross', format=',.1f')
    )

    chart = (bars + text).properties(height=300).configure_view(strokeWidth=0)
    st.altair_chart(chart, use_container_width=True)

with col_info:
    with st.expander("🔎 View Methodology", expanded=True):
        st.markdown(f"""
        **1. Opening Weekend:**
        * Awareness × Interest.
        * Trailer Boost (if >10M views).
        * Competition Dampener.
        
        **2. Domestic Total:**
        * Opening × Legs Multiplier.
        * Legs are adjusted by RT Score.
        
        **3. Global Total:**
        * Uses Genre-Specific Split.
        * **Current Multiplier:** {data['intl_multiplier']}x Domestic.
        * *(Note: Musicals/Dramas are lower, Animation/Action are higher).*
        """)
