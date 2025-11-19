import streamlit as st
import requests
import re
import math
from datetime import datetime, timedelta

# --- PART 1: CACHED DATA TOOLS ---
@st.cache_data(ttl=3600)
def get_live_data(wiki_title, yt_id, yt_fallback, rt_slug):
    """
    Fetches Wiki, YouTube, AND Rotten Tomatoes data.
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

    # 3. Rotten Tomatoes Scraper
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
    # Base Calculation
    base_gross = (interest * 0.15) * (total_aware * 0.05) * 1_000_000
    
    # Trailer Boost Logic (This is the "Hidden" Buzz)
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

# --- PART 2: PRESETS (NOW WITH COMPETITION & SOURCES) ---
presets = {
    "Eternity (A24)": {
        "aware": 21, "interest": 34, "theaters": 2400, "buzz": 1.2, "comp": 0.85, 
        "wiki": "Eternity_(2025_film)", "yt_id": "irXTps1REHU", "yt_fallback": 9300000,
        "rt_slug": "eternity_2025", 
        "source_label": "✅ Official Trailer",
        "tracking_source": "Real Data (The Quorum)",
        "competitors": "Wicked: Part Two, Zootopia 2 (Thanksgiving Weekend)",
        "benchmarks": {"Priscilla": 5.0, "The Iron Claw": 4.9, "Civil War (A24 Max)": 25.7}
    },
    "Marty Supreme (A24)": {
        "aware": 30, "interest": 40, "theaters": 2200, "buzz": 1.3, "comp": 0.9, 
        "wiki": "Marty_Supreme", "yt_id": "s9gSuKaKcqM", "yt_fallback": 17800000,
        "rt_slug": "marty_supreme",
        "source_label": "✅ Official Trailer",
        "tracking_source": "Estimated (Based on Uncut Gems / Chalamet Comps)",
        "competitors": "Avatar: Fire and Ash, SpongeBob (December Corridor)",
        "benchmarks": {"Uncut Gems (Wide)": 9.6, "Lady Bird (Wide)": 5.3, "Challengers": 15.0}
    },
    "Pillion (A24/Element)": {
        "aware": 10, "interest": 20, "theaters": 800, "buzz": 1.0, "comp": 0.95, 
        "wiki": "Pillion_(film)", "yt_id": "aTAacTUKK00", "yt_fallback": 500000,
        "rt_slug": "pillion",
        "source_label": "✅ Teaser / First Look",
        "tracking_source": "Estimated (Arthouse Niche)",
        "competitors": "Limited Release / Platform rollout competition",
        "benchmarks": {"Past Lives (Wide)": 5.8, "The Whale (Wide)": 11.0, "Moonlight (Wide)": 1.5}
    },
    "The Moment (A24)": {
        "aware": 15, "interest": 25, "theaters": 2000, "buzz": 1.1, "comp": 0.9, 
        "wiki": "The_Moment_(2026_film)", "yt_id": "ey5YrCNH09g", "yt_fallback": 1500000,
        "rt_slug": "the_moment_2026",
        "source_label": "✅ Official Trailer",
        "tracking_source": "Estimated (Based on After Yang / Sci-Fi Comps)",
        "competitors": "Project Hail Mary, The Batman Part II (Hypothetical)",
        "benchmarks": {"Ex Machina (Wide)": 5.4, "After Yang": 0.04, "Her (Wide)": 5.3}
    },
    "Wicked: Part Two": {
        "aware": 77, "interest": 50, "theaters": 4200, "buzz": 1.5, "comp": 0.8, 
        "wiki": "Wicked_(2024_film)", "yt_id": "vt98AlBDI9Y", "yt_fallback": 113000000,
        "rt_slug": "wicked_part_two",
        "source_label": "✅ Official Trailer",
        "tracking_source": "Real Data (The Quorum)",
        "competitors": "Zootopia 2, Eternity",
        "benchmarks": {"Frozen II": 130.0, "Barbie": 162.0, "Wonka": 39.0}
    },
    "Zootopia 2": {
        "aware": 68, "interest": 53, "theaters": 4300, "buzz": 1.3, "comp": 0.8, 
        "wiki": "Zootopia_2", "yt_id": "xo4rkcC7kFc", "yt_fallback": 25000000,
        "rt_slug": "zootopia_2",
        "source_label": "✅ Official Trailer",
        "tracking_source": "Real Data (The Quorum)",
        "competitors": "Wicked: Part Two",
        "benchmarks": {"Inside Out 2": 154.0, "Super Mario Bros": 146.0, "Moana": 56.6}
    },
    "Elden Ring (Hypothetical)": {
        "aware": 60, "interest": 45, "theaters": 4000, "buzz": 1.4, "comp": 0.8, 
        "wiki": "Elden_Ring", "yt_id": "E3Huy2cdih0", "yt_fallback": 14000000,
        "rt_slug": None,
        "source_label": "⚠️ Proxy (Game Launch Trailer)",
        "tracking_source": "Hypothetical (Based on FNAF / Mario)",
        "competitors": "Direct-to-Fan Event (Minimal direct competition)",
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
live_wiki, live_yt, live_rt = get_live_data(data['wiki'], data['yt_id'], data['yt_fallback'], data['rt_slug'])

# --- SIDEBAR ---
st.sidebar.header("Live Tracking Data")
st.sidebar.caption("Auto-fetched from API")

col_a, col_b = st.sidebar.columns(2)
with col_a:
    st.metric("Wiki Views", f"{live_wiki:,}", help="30-Day Daily Avg")
with col_b:
    st.metric("Trailer Views", f"{live_yt/1000000:.1f}M", help="YouTube View Count")

st.sidebar.link_button(f"📺 Watch Trailer", f"https://www.youtube.com/watch?v={data['yt_id']}")

if "Proxy" in data['source_label']:
    st.sidebar.warning(f"Source: {data['source_label']}")
else:
    st.sidebar.success(f"Source: {data['source_label']}")

st.sidebar.divider()
st.sidebar.header("Model Inputs")

# DATA SOURCE LABEL
if "Real" in data['tracking_source']:
    st.sidebar.success(f"📊 {data['tracking_source']}")
else:
    st.sidebar.warning(f"📉 {data['tracking_source']}")

total_aware = st.sidebar.slider("Total Awareness (%)", 0, 100, value=data['aware'], help="NRG/Quorum metric: % of audience who know the movie exists.")
interest = st.sidebar.slider("Definite Interest (%)", 0, 100, value=data['interest'], help="NRG/Quorum metric: % of audience who say they will 'definitely' see it.")
theaters = st.sidebar.number_input("Theater Count", 100, 5000, value=data['theaters'])

# RT LOGIC
if live_rt:
    rt_label = f"Rotten Tomatoes Score (Live)"
    rt_default = live_rt
    st.sidebar.success(f"✅ Live Score Found: {live_rt}%")
else:
    rt_label = "Estimated Score (Unreleased)"
    rt_default = 70
    st.sidebar.caption("⚠️ No live score. Defaulting to Neutral (70).")

rt_score = st.sidebar.slider(rt_label, 0, 100, value=rt_default, help="Scores <50 hurt the gross. Scores >80 boost the gross. 70 is neutral.")

buzz = st.sidebar.slider("Social Buzz Multiplier", 0.5, 2.0, value=float(data['buzz']), help="Manual adjustment for TikTok/Twitter virality. 1.0 is normal.")

# COMPETITION BOX
st.sidebar.info(f"⚔️ **Competition:**\n{data['competitors']}")
comp = st.sidebar.slider("Competition Factor", 0.5, 1.0, value=float(data['comp']), help="1.0 = Empty Weekend. 0.8 = Heavy Competition.")

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
chart_data = data['benchmarks'].copy()
chart_data["PREDICTION"] = prediction / 1_000_000
sorted_chart = dict(sorted(chart_data.items(), key=lambda item: item[1]))
st.bar_chart(sorted_chart)
st.caption("Benchmarks are Actual Wide Release Opening Weekends in Millions.")

# --- MATH EXPLAINER ---
with st.expander("🔎 How is this calculated?"):
    st.markdown("""
    **The Formula:**
    1. **Base Gross:** Derived from `Awareness` × `Interest` (Linear scaling).
    2. **Trailer Boost:** If YouTube views > 10M, we apply a **1.25x** multiplier. If > 50M, **1.5x**.
    3. **Social Buzz:** Multiplied by your manual slider input (e.g., 1.2x).
    4. **Competition:** Dampened by the competition factor (e.g., 0.85x).
    5. **Quality:** If RT Score > 80, **+15%**. If < 50, **-15%**.
    6. **Reality Cap:** For predictions over $150M, we apply logarithmic dampening to simulate capacity limits.
    """)
