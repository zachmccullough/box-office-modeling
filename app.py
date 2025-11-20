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

# --- CORE CALCULATION ENGINE ---
def calculate_box_office(interest, total_aware, theaters, rt_score, buzz, comp, trailer_views, intl_multiplier, studio_type):
    # 1. BASE CALCULATION
    base_gross = (interest * 0.15) * (total_aware * 0.05) * 1_000_000
    
    # 2. STUDIO EFFICIENCY
    view_efficiency = 1.0
    if studio_type == "Cult / Indie (A24/Neon)": view_efficiency = 0.6 
    elif studio_type == "Major Franchise": view_efficiency = 1.0 
    
    effective_views = trailer_views * view_efficiency
    trailer_multiplier = 1.0
    if effective_views > 60_000_000: trailer_multiplier = 1.4
    elif effective_views > 15_000_000: trailer_multiplier = 1.2
    elif effective_views > 5_000_000: trailer_multiplier = 1.05 
    
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

    # Legs Logic
    legs = 2.7
    if rt_score > 80: legs += 0.5
    elif rt_score < 50: legs -= 0.6
    if theaters < 2000: legs += 0.4
    
    # Front-loading Penalty
    if final_opening > 120_000_000: legs -= 0.5
    elif final_opening > 80_000_000: legs -= 0.3
    
    dom_total = final_opening * legs
    global_total = dom_total * intl_multiplier
        
    return final_opening, dom_total, global_total

# --- DATASETS (GLOBAL SCOPE) ---

upcoming_data = {
    "Wicked: Part Two (Nov 21)": {
        "type": "upcoming", "studio_type": "Major Franchise",
        "aware": 92, "interest": 62, "theaters": 4200, "buzz": 1.6, "comp": 0.8, 
        "wiki": "Wicked_(2024_film)", "yt_id": "vt98AlBDI9Y", "yt_fallback": 113000000,
        "rt_slug": "wicked_part_two", "source_label": "Official Trailer", "source_status": "success",
        "tracking_source": "Real Data (The Quorum)", "competitors": "Rental Family, Gladiator II",
        "intl_multiplier": 1.6, "benchmarks": {"Wicked: Part One": 114.0, "Frozen II": 130.0, "Barbie": 162.0}
    },
    "Rental Family (Nov 21)": {
        "type": "upcoming", "studio_type": "Cult / Indie (A24/Neon)",
        "aware": 15, "interest": 25, "theaters": 1500, "buzz": 1.1, "comp": 0.7, 
        "wiki": "Rental_Family", "yt_id": "sZT37sM2VgE", "yt_fallback": 5000000, 
        "rt_slug": "rental_family", "source_label": "Official Trailer", "source_status": "success",
        "tracking_source": "Estimated (Searchlight Comps)", "competitors": "Wicked: Part Two (Direct)",
        "intl_multiplier": 1.4, "benchmarks": {"The Menu": 9.0, "Next Goal Wins": 2.5}
    },
    "Eternity (Nov 26)": {
        "type": "upcoming", "studio_type": "Cult / Indie (A24/Neon)", 
        "aware": 21, "interest": 34, "theaters": 2400, "buzz": 1.2, "comp": 0.85, 
        "wiki": "Eternity_(2025_film)", "yt_id": "irXTps1REHU", "yt_fallback": 9300000,
        "rt_slug": "eternity_2025", "source_label": "Official Trailer", "source_status": "success",
        "tracking_source": "Real Data (The Quorum)", "competitors": "Zootopia 2 (Direct)",
        "intl_multiplier": 1.8, "benchmarks": {"Priscilla": 5.0, "Age of Adaline": 13.2, "Me Before You": 18.7}
    },
    "Zootopia 2 (Nov 26)": {
        "type": "upcoming", "studio_type": "Major Franchise",
        "aware": 68, "interest": 53, "theaters": 4300, "buzz": 1.3, "comp": 0.8, 
        "wiki": "Zootopia_2", "yt_id": "xo4rkcC7kFc", "yt_fallback": 25000000,
        "rt_slug": "zootopia_2", "source_label": "Official Trailer", "source_status": "success",
        "tracking_source": "Real Data (The Quorum)", "competitors": "Eternity",
        "intl_multiplier": 2.8, "benchmarks": {"Inside Out 2": 154.0, "Super Mario Bros": 146.0, "Moana": 56.6}
    },
    "Five Nights at Freddy's 2 (Dec 5)": {
        "type": "upcoming", "studio_type": "Major Franchise",
        "aware": 85, "interest": 60, "theaters": 3800, "buzz": 1.6, "comp": 0.9, 
        "wiki": "Five_Nights_at_Freddy's_2_(film)", "yt_id": "0VH9WCFV6Xw", "yt_fallback": 45000000,
        "rt_slug": "five_nights_at_freddys_2", "source_label": "Proxy (FNAF 1 Data)", "source_status": "warning",
        "tracking_source": "Estimated (Fan Event)", "competitors": "Wicked Part 2 (Holdover)",
        "intl_multiplier": 1.7, "benchmarks": {"FNAF 1": 80.0, "Halloween": 76.2, "M3GAN": 30.4}
    },
    "Avatar: Fire and Ash (Dec 19)": {
        "type": "upcoming", "studio_type": "Major Franchise",
        "aware": 95, "interest": 85, "theaters": 4500, "buzz": 1.8, "comp": 1.0, 
        "wiki": "Avatar:_Fire_and_Ash", "yt_id": "d9MyqF3xZSo", "yt_fallback": 60000000, 
        "rt_slug": "avatar_fire_and_ash", "source_label": "Proxy Data", "source_status": "warning",
        "tracking_source": "Hypothetical", "competitors": "SpongeBob Movie",
        "intl_multiplier": 3.5, "benchmarks": {"Avatar: Way of Water": 134.1, "Endgame": 357.0}
    },
    "SpongeBob Movie (Dec 19)": {
        "type": "upcoming", "studio_type": "Major Franchise",
        "aware": 90, "interest": 55, "theaters": 4000, "buzz": 1.3, "comp": 0.85, 
        "wiki": "The_SpongeBob_Movie:_Search_for_SquarePants", "yt_id": "wFx7DRIKaig", "yt_fallback": 15000000,
        "rt_slug": "the_spongebob_movie_search_for_squarepants", "source_label": "Official Trailer", "source_status": "success",
        "tracking_source": "Real Data (Quorum Proxy)", "competitors": "Avatar 3, Sonic 3",
        "intl_multiplier": 2.3, "benchmarks": {"Sponge Out of Water": 55.3, "Kung Fu Panda 4": 57.9}
    },
    "Marty Supreme (Dec 25)": {
        "type": "upcoming", "studio_type": "Cult / Indie (A24/Neon)",
        "aware": 30, "interest": 40, "theaters": 3200, "buzz": 1.3, "comp": 0.9, 
        "wiki": "Marty_Supreme", "yt_id": "s9gSuKaKcqM", "yt_fallback": 17800000,
        "rt_slug": "marty_supreme", "source_label": "Official Trailer", "source_status": "success",
        "tracking_source": "Estimated (Uncut Gems Comps)", "competitors": "Avatar: Fire and Ash, SpongeBob",
        "intl_multiplier": 1.8, "benchmarks": {"Uncut Gems (Wide)": 9.6, "Lady Bird (Wide)": 5.3, "Challengers": 15.0}
    },
    "The Housemaid (Early 2026)": {
        "type": "upcoming", "studio_type": "Major Franchise",
        "aware": 35, "interest": 40, "theaters": 3000, "buzz": 1.2, "comp": 0.85, 
        "wiki": "The_Housemaid_(2025_film)", "yt_id": "7rZEsxySFPw", "yt_fallback": 8000000, 
        "rt_slug": "the_housemaid_2025", "source_label": "Teaser / Proxy", "source_status": "warning",
        "tracking_source": "Estimated (Thriller Comps)", "competitors": "Heavy Thriller Slate",
        "intl_multiplier": 1.5, "benchmarks": {"A Simple Favor": 16.0, "Don't Worry Darling": 19.3}
    },
    "Pillion (2026)": {
        "type": "upcoming", "studio_type": "Cult / Indie (A24/Neon)",
        "aware": 10, "interest": 20, "theaters": 800, "buzz": 1.0, "comp": 0.95, 
        "wiki": "Pillion_(film)", "yt_id": "aTAacTUKK00", "yt_fallback": 500000,
        "rt_slug": "pillion", "source_label": "Teaser / First Look", "source_status": "success",
        "tracking_source": "Estimated (Arthouse Niche)", "competitors": "Limited Release Competition",
        "intl_multiplier": 1.5, "benchmarks": {"Past Lives (Wide)": 5.8, "The Whale (Wide)": 11.0, "Moonlight (Wide)": 1.5}
    },
    "The Moment (2026)": {
        "type": "upcoming", "studio_type": "Cult / Indie (A24/Neon)",
        "aware": 15, "interest": 25, "theaters": 2000, "buzz": 1.1, "comp": 0.9, 
        "wiki": "The_Moment_(2026_film)", "yt_id": "ey5YrCNH09g", "yt_fallback": 1500000,
        "rt_slug": "the_moment_2026", "source_label": "Official Trailer", "source_status": "success",
        "tracking_source": "Estimated (Sci-Fi Comps)", "competitors": "Project Hail Mary",
        "intl_multiplier": 2.0, "benchmarks": {"Ex Machina (Wide)": 5.4, "After Yang": 0.04, "Her (Wide)": 5.3}
    },
    "Elden Ring (TBD)": {
        "type": "upcoming", "studio_type": "Major Franchise",
        "aware": 60, "interest": 45, "theaters": 4000, "buzz": 1.4, "comp": 0.8, 
        "wiki": "Elden_Ring", "yt_id": "E3Huy2cdih0", "yt_fallback": 14000000,
        "rt_slug": None, "source_label": "Proxy (Game Trailer)", "source_status": "warning",
        "tracking_source": "Hypothetical (Gamer Comps)", "competitors": "Direct-to-Fan Event",
        "intl_multiplier": 2.2, "benchmarks": {"Dune: Part One": 41.0, "Five Nights at Freddy's": 80.0, "Uncharted": 44.0}
    }
}

historical_data = {
    "Superman (Jul '25)": {
        "type": "historical", "studio_type": "Major Franchise", "actual_opening": 115.0,
        "aware": 85, "interest": 65, "theaters": 4200, "buzz": 1.4, "comp": 0.9, 
        "wiki": "Superman_(2025_film)", "yt_id": "v7s5d4pG2eM", "yt_fallback": 30000000, "frozen_views": 30000000,
        "rt_slug": "superman_2025", "source_label": "Simulated Historical", "source_status": "neutral",
        "tracking_source": "Estimated", "competitors": "Fantastic Four",
        "intl_multiplier": 2.2, "benchmarks": {"Actual Opening (Sim)": 115.0, "Man of Steel": 116.6}
    },
    "A Minecraft Movie (Apr '25)": {
        "type": "historical", "studio_type": "Major Franchise", "actual_opening": 145.0,
        "aware": 90, "interest": 55, "theaters": 4300, "buzz": 1.6, "comp": 0.85, 
        "wiki": "A_Minecraft_Movie", "yt_id": "jTq91k43nDQ", "yt_fallback": 45000000, "frozen_views": 45000000,
        "rt_slug": "a_minecraft_movie", "source_label": "Simulated Historical", "source_status": "neutral",
        "tracking_source": "Real Data", "competitors": "Micheal",
        "intl_multiplier": 2.2, "benchmarks": {"Actual Opening (Sim)": 145.0, "Super Mario Bros": 146.3}
    },
    "Civil War (Apr '24)": {
        "type": "historical", "studio_type": "Cult / Indie (A24/Neon)", "actual_opening": 25.7,
        "aware": 48, "interest": 42, "theaters": 3838, "buzz": 1.3, "comp": 0.9, 
        "wiki": "Civil_War_(film)", "yt_id": "aDyQxtgKWbs", "yt_fallback": 22000000, "frozen_views": 16000000,
        "rt_slug": "civil_war_2024", "source_label": "Historical Data", "source_status": "neutral",
        "tracking_source": "Historical NRG", "competitors": "Godzilla x Kong",
        "intl_multiplier": 1.8, "benchmarks": {"Actual Opening": 25.7, "Ex Machina": 6.8}
    },
    "Five Nights at Freddy's (Oct '23)": {
        "type": "historical", "actual_opening": 80.0,
        "aware": 60, "interest": 55, "theaters": 3675, "buzz": 1.6, "comp": 0.9, 
        "wiki": "Five_Nights_at_Freddy's_(film)", "yt_id": "0VH9WCFV6Xw", "yt_fallback": 50000000, "frozen_views": 25000000,
        "rt_slug": "five_nights_at_freddys", "source_label": "Historical Data", "source_status": "neutral",
        "tracking_source": "Historical NRG", "competitors": "Eras Tour",
        "intl_multiplier": 1.8, "benchmarks": {"Actual Opening": 80.0, "Halloween": 76.2}
    },
    "Barbie (Jul '23)": {
        "type": "historical", "studio_type": "Major Franchise", "actual_opening": 162.0,
        "aware": 95, "interest": 75, "theaters": 4243, "buzz": 1.8, "comp": 0.8, 
        "wiki": "Barbie_(film)", "yt_id": "pBk4NYhWNMM", "yt_fallback": 80000000, "frozen_views": 45000000,
        "rt_slug": "barbie", "source_label": "Historical Data", "source_status": "neutral",
        "tracking_source": "Historical NRG", "competitors": "Oppenheimer",
        "intl_multiplier": 2.1, "benchmarks": {"Actual Opening": 162.0, "Mario Bros": 146.3}
    }
}

# --- VIEW 1: LONG LEAD LOGIC ---
def calculate_long_lead(genre, cast_score, budget, rating, ip_status, season, competition_level):
    genre_baselines = {"Action/Adventure": 25.0, "Horror": 18.0, "Sci-Fi": 22.0, "Drama": 8.0, "Comedy": 12.0, "Family/Animation": 28.0, "Thriller": 14.0}
    base = genre_baselines.get(genre, 10.0)
    star_power_add = math.sqrt(cast_score) * 2.5
    production_add = budget * 0.08
    
    ip_mult = 1.0
    if ip_status == "Sequel (Major Franchise)": ip_mult = 2.5
    elif ip_status == "Adaptation (Book/Game)": ip_mult = 1.5
    elif ip_status == "Original": ip_mult = 0.9

    season_mult = 1.0
    if season == "Summer (May-Jul)": season_mult = 1.3
    elif season == "Holiday (Nov-Dec)": season_mult = 1.4
    elif season == "Dump Months (Jan/Sept)": season_mult = 0.8

    rating_mult = 1.0
    if rating == "R": rating_mult = 0.85
    elif rating == "G/PG": rating_mult = 1.1

    comp_mult = 1.0
    if competition_level == "High (2+ Wide Releases)": comp_mult = 0.85
    elif competition_level == "Extreme (vs Blockbuster)": comp_mult = 0.7

    raw_prediction = (base + star_power_add + production_add) * ip_mult * season_mult * rating_mult * comp_mult
    return raw_prediction

def render_long_lead():
    st.title("🔭 Long-Lead Slate Planner")
    st.caption("Fundamental analysis for greenlighting and slate planning (3-12 months out).")
    st.markdown("---")

    st.sidebar.header("Film DNA")
    genre = st.sidebar.selectbox("Genre", ["Action/Adventure", "Horror", "Sci-Fi", "Drama", "Comedy", "Family/Animation", "Thriller"])
    rating = st.sidebar.selectbox("MPA Rating", ["PG-13", "R", "PG", "G"])
    ip_status = st.sidebar.selectbox("IP Status", ["Original", "Adaptation (Book/Game)", "Sequel (Major Franchise)"])
    budget = st.sidebar.number_input("Production Budget ($M)", 5, 300, 50)

    st.sidebar.markdown("---")
    st.sidebar.header("Talent Metrics")
    cast_score = st.sidebar.slider("Cast/Director Avg Opening ($M)", 0, 150, 20, help="Data from Comscore")

    st.sidebar.markdown("---")
    st.sidebar.header("Release Context")
    season = st.sidebar.selectbox("Release Window", ["Average", "Summer (May-Jul)", "Holiday (Nov-Dec)", "Dump Months (Jan/Sept)"])
    competition = st.sidebar.selectbox("Crowdedness", ["Low (Clear Weekend)", "Moderate (1 Opener)", "High (2+ Wide Releases)", "Extreme (vs Blockbuster)"])

    # Calculate
    prediction = calculate_long_lead(genre, cast_score, budget, rating, ip_status, season, competition)
    low_end = prediction * 0.75
    high_end = prediction * 1.25

    col1, col2 = st.columns([1, 1.5])
    with col1:
        st.metric("Forecasted Opening", f"${prediction:.1f}M")
        st.markdown(f"""
        <div style="background-color: #F8FAFC; padding: 15px; border-radius: 8px; border: 1px solid #E2E2E5;">
            <p style="color: #64748B; font-size: 0.85rem; margin-bottom: 5px;">CONFIDENCE INTERVAL (±25%)</p>
            <h3 style="margin: 0; color: #0F172A;">${low_end:.1f}M — ${high_end:.1f}M</h3>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        st.markdown("#### 🧱 Building the Forecast")
        breakdown_data = pd.DataFrame({
            "Factor": ["Genre Baseline", "Star Power Add", "Budget/Spectacle Add", "Final Prediction"],
            "Value": [20, math.sqrt(cast_score) * 2.5, budget * 0.08, prediction],
            "Type": ["Base", "Add-on", "Add-on", "Total"]
        })
        c = alt.Chart(breakdown_data).mark_bar().encode(
            x=alt.X('Value', title='Contribution ($M)'),
            y=alt.Y('Factor', sort=None),
            color=alt.Color('Type', scale=alt.Scale(domain=['Base', 'Add-on', 'Total'], range=['#94A3B8', '#64748B', '#18181B']))
        ).properties(height=300)
        st.altair_chart(c, use_container_width=True)

# --- VIEW 2: PREDICTIVE TRACKER UI ---
def render_tracker(dataset, mode_title):
    st.title(mode_title)
    st.markdown("---")

    selected_preset = st.selectbox("Select Project:", list(dataset.keys()), index=0)
    data = dataset[selected_preset]
    
    live_wiki, live_yt, live_rt = get_live_data(
        data['wiki'], 
        data['yt_id'], 
        data['yt_fallback'], 
        data['rt_slug'], 
        data.get('frozen_views')
    )

    # Sidebar
    st.sidebar.markdown("### 📡 Live Signals")
    badge_class = "status-success" if data['source_status'] == "success" else "status-neutral"
    st.sidebar.markdown(f'<span class="status-badge {badge_class}">{data["source_label"]}</span>', unsafe_allow_html=True)
    
    st.sidebar.metric("Wiki Views", f"{live_wiki:,}", help="30-Day Avg")
    st.sidebar.metric("Trailer Views", f"{live_yt/1000000:.1f}M")
    
    st.sidebar.markdown("---")
    st.sidebar.caption("Model Tuning")
    studio_type = st.sidebar.selectbox("Studio / Brand Profile", ["Major Franchise", "Cult / Indie (A24/Neon)"], index=0 if data.get("studio_type") == "Major Franchise" else 1)
    
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

    # Dashboard
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

# --- MAIN NAVIGATION CONTROLLER ---
view = st.sidebar.radio("Evaluation Mode", ["🔭 Long-Lead Planner", "📉 Short-Term Tracker", "🕰️ Historical Analysis"])

if view == "🔭 Long-Lead Planner":
    render_long_lead()
elif view == "📉 Short-Term Tracker":
    render_tracker(upcoming_data, "📉 Short-Term Tracker")
else:
    render_tracker(historical_data, "🕰️ Historical Analysis")
