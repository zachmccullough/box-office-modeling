import streamlit as st
import requests
import re
import math
import pandas as pd
import altair as alt
from datetime import datetime, timedelta

# --- PART 0: SHADCN/UI THEME (ZINC) ---
st.set_page_config(page_title="Box Office Suite", page_icon="🎬", layout="wide")

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
        min-width: 350px !important;
        max-width: 350px !important;
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
    
    .stRadio > div {
        background-color: #FFFFFF;
        border: 1px solid #E4E4E7;
        border-radius: 8px;
        padding: 10px;
        box-shadow: 0 1px 2px 0 rgba(0,0,0,0.05);
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
        color: #334155;
    }

</style>
""", unsafe_allow_html=True)

# --- SHARED HELPER FUNCTIONS ---
@st.cache_data(ttl=3600)
def get_live_data(wiki_title, yt_id, yt_fallback, rt_slug, frozen_views=None):
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

    if frozen_views:
        yt_views = frozen_views
    else:
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

def calculate_box_office(interest, total_aware, theaters, rt_score, buzz, comp, trailer_views, intl_multiplier, studio_type):
    # 1. BASE CALCULATION
    base_gross = (interest * 0.15) * (total_aware * 0.05) * 1_000_000
    
    # 2. STUDIO EFFICIENCY ADJUSTMENT (NEW LOGIC)
    # "Cult" brands (A24) get lots of views but fewer ticket conversions.
    # "Major" studios convert views to tickets more efficiently.
    view_efficiency = 1.0
    if studio_type == "Cult / Indie (A24/Neon)":
        view_efficiency = 0.6 # 40% discount on trailer views
    elif studio_type == "Major Franchise":
        view_efficiency = 1.0 # Standard conversion
        
    # Apply efficiency to the views before calculating the boost
    effective_views = trailer_views * view_efficiency
    
    trailer_multiplier = 1.0
    if effective_views > 60_000_000: trailer_multiplier = 1.4
    elif effective_views > 15_000_000: trailer_multiplier = 1.2
    elif effective_views > 5_000_000: trailer_multiplier = 1.05 # Small boost for Indies
    
    base_gross = base_gross * trailer_multiplier

    # 3. EFFICIENCY SCALING
    blockbuster_mult = 1.0
    if theaters > 2500:
        if total_aware > 60: blockbuster_mult = 3.0
        elif total_aware > 40: blockbuster_mult = 2.0
        elif total_aware > 25: blockbuster_mult = 1.5
        else: blockbuster_mult = 1.1
    
    base_gross = base_gross * blockbuster_mult

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
    dom_total = final_opening * legs
    global_total = dom_total * intl_multiplier
        
    return final_opening, dom_total, global_total

# --- PART 2: PRESETS (With Studio Type) ---
presets = {
    "Eternity (A24)": {
        "type": "upcoming", "studio_type": "Cult / Indie (A24/Neon)", 
        "aware": 21, "interest": 34, "theaters": 2400, "buzz": 1.2, "comp": 0.85, 
        "wiki": "Eternity_(2025_film)", "yt_id": "irXTps1REHU", "yt_fallback": 9300000,
        "rt_slug": "eternity_2025", "source_label": "Official Trailer", "source_status": "success",
        "tracking_source": "Real Data (The Quorum)", "competitors": "Wicked: Part Two, Zootopia 2",
        "intl_multiplier": 1.8, "benchmarks": {"Priscilla": 5.0, "Age of Adaline": 13.2, "Me Before You": 18.7}
    },
    "Marty Supreme (A24)": {
        "type": "upcoming", "studio_type": "Cult / Indie (A24/Neon)",
        "aware": 30, "interest": 40, "theaters": 3200, "buzz": 1.3, "comp": 0.9, 
        "wiki": "Marty_Supreme", "yt_id": "s9gSuKaKcqM", "yt_fallback": 17800000,
        "rt_slug": "marty_supreme", "source_label": "Official Trailer", "source_status": "success",
        "tracking_source": "Estimated (Uncut Gems Comps)", "competitors": "Avatar: Fire and Ash, SpongeBob",
        "intl_multiplier": 1.8, "benchmarks": {"Uncut Gems (Wide)": 9.6, "Lady Bird (Wide)": 5.3, "Challengers": 15.0}
    },
    "Wicked: Part Two": {
        "type": "upcoming", "studio_type": "Major Franchise",
        "aware": 92, "interest": 62, "theaters": 4200, "buzz": 1.6, "comp": 0.8, 
        "wiki": "Wicked_(2024_film)", "yt_id": "vt98AlBDI9Y", "yt_fallback": 113000000,
        "rt_slug": "wicked_part_two", "source_label": "Official Trailer", "source_status": "success",
        "tracking_source": "Real Data (The Quorum)", "competitors": "Zootopia 2, Eternity",
        "intl_multiplier": 1.6, "benchmarks": {"Frozen II": 130.0, "Barbie": 162.0, "Wonka": 39.0}
    },
    "Avatar: Fire and Ash": {
        "type": "upcoming", "studio_type": "Major Franchise",
        "aware": 95, "interest": 85, "theaters": 4500, "buzz": 1.8, "comp": 1.0, 
        "wiki": "Avatar:_Fire_and_Ash", "yt_id": "d9MyqF3xZSo", "yt_fallback": 60000000, 
        "rt_slug": "avatar_fire_and_ash", "source_label": "Proxy Data", "source_status": "warning",
        "tracking_source": "Hypothetical", "competitors": "None",
        "intl_multiplier": 3.5, "benchmarks": {"Avatar: Way of Water": 134.1, "Endgame": 357.0}
    },
    "A Minecraft Movie (Historical)": {
        "type": "historical", "studio_type": "Major Franchise", "actual_opening": 145.0,
        "aware": 90, "interest": 55, "theaters": 4300, "buzz": 1.6, "comp": 0.85, 
        "wiki": "A_Minecraft_Movie", "yt_id": "jTq91k43nDQ", "yt_fallback": 45000000, 
        "frozen_views": 45000000, "rt_slug": "a_minecraft_movie", "source_label": "Simulated Historical", "source_status": "neutral",
        "tracking_source": "Real Data", "competitors": "Micheal",
        "intl_multiplier": 2.2, "benchmarks": {"Actual Opening (Sim)": 145.0, "Super Mario Bros": 146.3}
    },
    "Civil War (Historical)": {
        "type": "historical", "studio_type": "Cult / Indie (A24/Neon)", "actual_opening": 25.7,
        "aware": 48, "interest": 42, "theaters": 3838, "buzz": 1.3, "comp": 0.9, 
        "wiki": "Civil_War_(film)", "yt_id": "aDyQxtgKWbs", "yt_fallback": 22000000, 
        "frozen_views": 16000000, "rt_slug": "civil_war_2024", "source_label": "Historical Data", "source_status": "neutral",
        "tracking_source": "Historical NRG", "competitors": "Godzilla x Kong",
        "intl_multiplier": 1.8, "benchmarks": {"Actual Opening": 25.7, "Ex Machina": 6.8}
    },
    "Barbie (Historical)": {
        "type": "historical", "studio_type": "Major Franchise", "actual_opening": 162.0,
        "aware": 95, "interest": 75, "theaters": 4243, "buzz": 1.8, "comp": 0.8, 
        "wiki": "Barbie_(film)", "yt_id": "pBk4NYhWNMM", "yt_fallback": 80000000, 
        "frozen_views": 45000000, "rt_slug": "barbie", "source_label": "Historical Data", "source_status": "neutral",
        "tracking_source": "Historical NRG", "competitors": "Oppenheimer",
        "intl_multiplier": 2.1, "benchmarks": {"Actual Opening": 162.0, "Mario Bros": 146.3}
    }
}

# --- VIEW 2: SHORT TERM TRACKER LOGIC ---
def render_short_term():
    st.title("📉 Short-Term Tracker")
    st.caption("High-precision model using Awareness, Interest, and Social Buzz (2-6 weeks out).")
    st.markdown("---")

    selected_preset = st.selectbox("Select Project:", list(presets.keys()), index=0)
    data = presets[selected_preset]
    
    live_wiki, live_yt, live_rt = get_live_data(
        data['wiki'], 
        data['yt_id'], 
        data['yt_fallback'], 
        data['rt_slug'], 
        data.get('frozen_views')
    )

    # Sidebar Inputs
    st.sidebar.markdown("### 📡 Live Signals")
    badge_class = "status-success" if data['source_status'] == "success" else "status-neutral"
    st.sidebar.markdown(f'<span class="status-badge {badge_class}">{data["source_label"]}</span>', unsafe_allow_html=True)
    
    st.sidebar.metric("Wiki Views", f"{live_wiki:,}", help="30-Day Avg")
    st.sidebar.metric("Trailer Views", f"{live_yt/1000000:.1f}M")
    
    # NEW: Studio Type Selector (Shows the weighting logic)
    st.sidebar.markdown("---")
    st.sidebar.caption("Model Tuning")
    studio_type = st.sidebar.selectbox("Studio / Brand Profile", ["Major Franchise", "Cult / Indie (A24/Neon)"], index=0 if data.get("studio_type") == "Major Franchise" else 1)
    
    if studio_type == "Cult / Indie (A24/Neon)":
        st.sidebar.info("ℹ️ **Cult Brand:** Trailer views are dampened (0.6x) to account for high fan engagement vs. general audience conversion.")

    st.sidebar.markdown("### 🎛️ Model Inputs")
    
    theaters = st.sidebar.number_input("Theater Count", 100, 5000, value=data['theaters'], step=100)
    
    if "Real" in data['tracking_source']: st.sidebar.caption(f"✅ {data['tracking_source']}")
    else: st.sidebar.caption(f"⚠️ {data['tracking_source']}")
    
    total_aware = st.sidebar.slider("Total Awareness (%)", 0, 100, value=data['aware'])
    interest = st.sidebar.slider("Definite Interest (%)", 0, 100, value=data['interest'])
    
    st.sidebar.markdown("---")
    
    if live_rt:
        rt_label = f"Rotten Tomatoes (Live)"
        rt_default = live_rt
        st.sidebar.success(f"✅ Live Score: {live_rt}%")
    else:
        rt_label = "Estimated RT Score"
        rt_default = 70
        
    rt_score = st.sidebar.slider(rt_label, 0, 100, value=rt_default)
    buzz = st.sidebar.slider("Social Buzz Multiplier", 0.5, 2.0, value=float(data['buzz']))
    comp = st.sidebar.slider("Competition Factor", 0.5, 1.0, value=float(data['comp']))
    st.sidebar.caption(f"**Opening Against:** {data['competitors']}")

    # Calculations
    opening, dom_total, global_total = calculate_box_office(
        interest, total_aware, theaters, rt_score, buzz, comp, live_yt, data['intl_multiplier'], studio_type
    )

    # Display Dashboard
    if data.get('type') == 'historical':
        actual = data['actual_opening'] * 1_000_000
        delta = opening - actual
        percent_error = (delta / actual) * 100
        
        st.info(f"🕰️ **BACKTEST MODE:** Comparing prediction against actual results.")
        col1, col2, col3 = st.columns(3)
        with col1: st.metric("Model Prediction", f"${opening/1_000_000:.2f}M")
        with col2: st.metric("Actual Opening", f"${data['actual_opening']}M", delta=f"{percent_error:.1f}% Error", delta_color="inverse")
        with col3: 
            if abs(percent_error) < 15: st.success("✅ Accurate")
            else: st.warning("⚠️ Drift Detected")
            
        advice = ""
        if percent_error < -20: advice = "📉 **Diagnosis:** Too conservative. Increase Interest weight."
        elif percent_error > 20: advice = "📈 **Diagnosis:** Too optimistic. Check Buzz/Trailer weights."
        else: advice = "✨ **Diagnosis:** Model logic holds up well."
        st.markdown(f"""<div class="tuning-box">{advice}</div>""", unsafe_allow_html=True)
    else:
        col1, col2, col3 = st.columns(3)
        with col1: st.metric("Predicted Opening", f"${opening/1_000_000:.2f}M")
        with col2: st.metric("Proj. Domestic", f"${dom_total/1_000_000:.2f}M")
        with col3: st.metric("Proj. Global", f"${global_total/1_000_000:.2f}M")

    st.markdown("---")
    
    # Chart
    col_chart, col_info = st.columns([2, 1])
    with col_chart:
        st.markdown(f"#### 📊 Benchmark Comparison")
        chart_data = data['benchmarks'].copy()
        chart_data["PREDICTION"] = opening / 1_000_000
        if data.get('type') == 'historical': chart_data["ACTUAL"] = data['actual_opening']
        
        df = pd.DataFrame({"Movie": list(chart_data.keys()), "Gross": list(chart_data.values())})
        
        def get_color(movie):
            if movie == 'PREDICTION': return '#18181B'
            if movie == 'ACTUAL': return '#10B981'
            return '#E4E4E7'
        
        df['Color'] = df['Movie'].apply(get_color)
        
        base = alt.Chart(df).encode(x=alt.X('Gross', title='Opening ($M)', axis=alt.Axis(grid=False)), y=alt.Y('Movie', sort='-x', title=None))
        bars = base.mark_bar().encode(color=alt.Color('Color', scale=None))
        text = base.mark_text(align='left', dx=3).encode(text=alt.Text('Gross', format=',.1f'))
        st.altair_chart((bars + text).properties(height=300).configure_view(strokeWidth=0), use_container_width=True)

# --- MAIN NAVIGATION ---
def render_long_lead():
    st.title("🔭 Long-Lead Slate Planner")
    st.caption("Fundamental analysis for greenlighting and slate planning (3-12 months out).")
    st.markdown("---")
    st.info("Select 'Short-Term Tracker' in the sidebar to access the detailed A24/Blockbuster models.")

view = st.sidebar.radio("Evaluation Mode", ["🔭 Long-Lead Planner", "📉 Short-Term Tracker"])

if view == "🔭 Long-Lead Planner":
    render_long_lead()
else:
    render_short_term()
