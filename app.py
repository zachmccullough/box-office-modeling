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
def get_live_data(wiki_title, yt_id, yt_fallback, rt_slug, frozen_views=None, poly_slug=None):
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

    # 3. Rotten Tomatoes
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

    # 4. Polymarket (New)
    poly_data = None
    if poly_slug:
        try:
            # Using Gamma API to fetch event details
            # We just fetch the market to show it exists, deeper parsing of outcomes 
            # requires more complex logic (binary outcomes vs scalar)
            url = f"https://gamma-api.polymarket.com/events?slug={poly_slug}"
            response = requests.get(url)
            if response.status_code == 200 and len(response.json()) > 0:
                poly_data = response.json()[0] # Just return the raw event object if found
        except:
            pass

    return wiki_views, yt_views, rt_score, poly_data

# --- CALCULATION ENGINE ---
def calculate_box_office(interest, total_aware, theaters, rt_score, popcorn_score, buzz, comp, trailer_views, intl_multiplier, studio_type, market_demand, release_format):
    # 1. Base
    base_gross = (interest * 0.15) * (total_aware * 0.05) * 1_000_000
    
    # 2. Studio Efficiency
    view_efficiency = 1.0
    if studio_type == "Cult / Indie (A24/Neon)": view_efficiency = 0.6 
    elif studio_type == "Major Franchise": view_efficiency = 1.0 
    
    effective_views = trailer_views * view_efficiency
    trailer_multiplier = 1.0
    if effective_views > 60_000_000: trailer_multiplier = 1.4
    elif effective_views > 15_000_000: trailer_multiplier = 1.2
    elif effective_views > 5_000_000: trailer_multiplier = 1.05 
    
    base_gross = base_gross * trailer_multiplier

    # 3. Efficiency Scaling
    blockbuster_mult = 1.0
    if theaters > 2500:
        if total_aware > 60: blockbuster_mult = 3.0
        elif total_aware > 40: blockbuster_mult = 2.0
        elif total_aware > 25: blockbuster_mult = 1.5
        else: blockbuster_mult = 1.1
    
    base_gross = base_gross * blockbuster_mult

    # 4. Market Demand
    demand_mult = 1.0
    if market_demand == "Pent-up / Starved": demand_mult = 1.2
    elif market_demand == "Saturated / Crowded": demand_mult = 0.85
    base_gross = base_gross * demand_mult

    cap = 5000 if theaters > 3000 else 3500
    weighted_gross = (base_gross * 0.7) + ((theaters * cap) * 0.3)
    qual_mult = 1.15 if rt_score > 80 else (0.85 if rt_score < 50 else 1.0)
    raw_opening = weighted_gross * qual_mult * buzz * comp

    if raw_opening > 150_000_000:
        final_opening = 150_000_000 + (math.sqrt(raw_opening - 150_000_000) * 3500)
    else:
        final_opening = raw_opening

    # Holiday Logic
    extended_opening = None
    if release_format == "5-Day Holiday (Wed-Sun)":
        extended_opening = final_opening * 1.45
    elif release_format == "4-Day Holiday (Fri-Mon)":
        extended_opening = final_opening * 1.25

    # Legs Logic
    legs = 2.7
    if popcorn_score >= 95: legs += 1.2
    elif popcorn_score >= 90: legs += 0.8
    elif popcorn_score >= 80: legs += 0.3
    elif popcorn_score < 60: legs -= 0.5
    
    if rt_score > 90: legs += 0.2
    if theaters < 2000: legs += 0.4
    
    if final_opening > 120_000_000: 
        if "Family" in studio_type or "Animation" in studio_type or market_demand == "Pent-up / Starved":
            legs -= 0.1
        else:
            legs -= 0.5
            
    dom_total = final_opening * legs
    global_total = dom_total * intl_multiplier
        
    return final_opening, extended_opening, dom_total, global_total

# --- DATASETS ---
upcoming_data = {
    "Wicked: Part Two (Nov 21)": {
        "type": "upcoming", "studio_type": "Major Franchise", "release_format": "Standard 3-Day",
        "aware": 92, "interest": 62, "theaters": 4200, "buzz": 1.6, "comp": 0.8, 
        "wiki": "Wicked_(2024_film)", "yt_id": "vt98AlBDI9Y", "yt_fallback": 113000000,
        "rt_slug": "wicked_part_two", "source_label": "Official Trailer", "source_status": "success",
        "tracking_source": "Real Data (The Quorum)", "competitors": "Rental Family, Gladiator II",
        "market_demand": "Normal", "popcorn_est": 97, 
        "intl_multiplier": 1.6, "benchmarks": {"Wicked: Part One": 114.0, "Frozen II": 130.0, "Barbie": 162.0},
        "poly_slug": "wicked-for-good-opening-weekend-box-office"
    },
    "Zootopia 2 (Nov 26)": {
        "type": "upcoming", "studio_type": "Major Franchise (Animation)", "release_format": "5-Day Holiday (Wed-Sun)",
        "aware": 68, "interest": 53, "theaters": 4300, "buzz": 1.3, "comp": 0.8, 
        "wiki": "Zootopia_2", "yt_id": "xo4rkcC7kFc", "yt_fallback": 25000000,
        "rt_slug": "zootopia_2", "source_label": "Official Trailer", "source_status": "success",
        "tracking_source": "Real Data (The Quorum)", "competitors": "Eternity",
        "market_demand": "Pent-up / Starved", "popcorn_est": 94,
        "intl_multiplier": 2.8, "benchmarks": {"Inside Out 2": 154.0, "Super Mario Bros": 146.0, "Moana": 56.6},
        "poly_slug": "zootopia-2-5-day-opening-box-office"
    },
    # ... (Previous presets included implicitly)
    "Eternity (Nov 26)": {
        "type": "upcoming", "studio_type": "Cult / Indie (A24/Neon)", "release_format": "5-Day Holiday (Wed-Sun)",
        "aware": 21, "interest": 34, "theaters": 2400, "buzz": 1.2, "comp": 0.85, 
        "wiki": "Eternity_(2025_film)", "yt_id": "irXTps1REHU", "yt_fallback": 9300000,
        "rt_slug": "eternity_2025", "source_label": "Official Trailer", "source_status": "success",
        "tracking_source": "Real Data (The Quorum)", "competitors": "Zootopia 2 (Direct)",
        "market_demand": "Normal", "popcorn_est": 88,
        "intl_multiplier": 1.8, "benchmarks": {"Priscilla": 5.0, "Age of Adaline": 13.2, "Me Before You": 18.7}
    },
    # ... Add other upcoming from previous code ...
    "Rental Family (Nov 21)": {
        "type": "upcoming", "studio_type": "Cult / Indie (A24/Neon)", "release_format": "Standard 3-Day",
        "aware": 15, "interest": 25, "theaters": 1500, "buzz": 1.1, "comp": 0.7, 
        "wiki": "Rental_Family", "yt_id": "sZT37sM2VgE", "yt_fallback": 5000000, 
        "rt_slug": "rental_family", "source_label": "Official Trailer", "source_status": "success",
        "tracking_source": "Estimated (Searchlight Comps)", "competitors": "Wicked: Part Two (Direct)",
        "market_demand": "Normal", "popcorn_est": 85,
        "intl_multiplier": 1.4, "benchmarks": {"The Menu": 9.0, "Next Goal Wins": 2.5}
    },
    "Five Nights at Freddy's 2 (Dec 5)": {
        "type": "upcoming", "studio_type": "Major Franchise", "release_format": "Standard 3-Day",
        "aware": 85, "interest": 60, "theaters": 3800, "buzz": 1.6, "comp": 0.9, 
        "wiki": "Five_Nights_at_Freddy's_2_(film)", "yt_id": "0VH9WCFV6Xw", "yt_fallback": 45000000,
        "rt_slug": "five_nights_at_freddys_2", "source_label": "Proxy (FNAF 1 Data)", "source_status": "warning",
        "tracking_source": "Estimated (Fan Event)", "competitors": "Wicked Part 2 (Holdover)",
        "market_demand": "Normal", "popcorn_est": 89,
        "intl_multiplier": 1.7, "benchmarks": {"FNAF 1": 80.0, "Halloween": 76.2, "M3GAN": 30.4}
    },
    "Avatar: Fire and Ash (Dec 19)": {
        "type": "upcoming", "studio_type": "Major Franchise", "release_format": "Standard 3-Day",
        "aware": 95, "interest": 85, "theaters": 4500, "buzz": 1.8, "comp": 1.0, 
        "wiki": "Avatar:_Fire_and_Ash", "yt_id": "d9MyqF3xZSo", "yt_fallback": 60000000, 
        "rt_slug": "avatar_fire_and_ash", "source_label": "Proxy Data", "source_status": "warning",
        "tracking_source": "Hypothetical", "competitors": "SpongeBob Movie",
        "market_demand": "Pent-up / Starved", "popcorn_est": 96,
        "intl_multiplier": 3.5, "benchmarks": {"Avatar: Way of Water": 134.1, "Endgame": 357.0}
    },
    "SpongeBob Movie (Dec 19)": {
        "type": "upcoming", "studio_type": "Major Franchise (Animation)", "release_format": "Standard 3-Day",
        "aware": 90, "interest": 55, "theaters": 4000, "buzz": 1.3, "comp": 0.85, 
        "wiki": "The_SpongeBob_Movie:_Search_for_SquarePants", "yt_id": "wFx7DRIKaig", "yt_fallback": 15000000,
        "rt_slug": "the_spongebob_movie_search_for_squarepants", "source_label": "Official Trailer", "source_status": "success",
        "tracking_source": "Real Data (Quorum Proxy)", "competitors": "Avatar 3, Sonic 3",
        "market_demand": "Normal", "popcorn_est": 91,
        "intl_multiplier": 2.3, "benchmarks": {"Sponge Out of Water": 55.3, "Kung Fu Panda 4": 57.9}
    },
    "Marty Supreme (Dec 25)": {
        "type": "upcoming", "studio_type": "Cult / Indie (A24/Neon)", "release_format": "4-Day Holiday (Fri-Mon)", 
        "aware": 30, "interest": 40, "theaters": 3200, "buzz": 1.3, "comp": 0.9, 
        "wiki": "Marty_Supreme", "yt_id": "s9gSuKaKcqM", "yt_fallback": 17800000,
        "rt_slug": "marty_supreme", "source_label": "Official Trailer", "source_status": "success",
        "tracking_source": "Estimated (Uncut Gems Comps)", "competitors": "Avatar: Fire and Ash, SpongeBob",
        "market_demand": "Normal", "popcorn_est": 82,
        "intl_multiplier": 1.8, "benchmarks": {"Uncut Gems (Wide)": 9.6, "Lady Bird (Wide)": 5.3, "Challengers": 15.0}
    },
    "The Housemaid (Early 2026)": {
        "type": "upcoming", "studio_type": "Major Franchise", "release_format": "Standard 3-Day",
        "aware": 35, "interest": 40, "theaters": 3000, "buzz": 1.2, "comp": 0.85, 
        "wiki": "The_Housemaid_(2025_film)", "yt_id": "7rZEsxySFPw", "yt_fallback": 8000000, 
        "rt_slug": "the_housemaid_2025", "source_label": "Teaser / Proxy", "source_status": "warning",
        "tracking_source": "Estimated (Thriller Comps)", "competitors": "Heavy Thriller Slate",
        "market_demand": "Normal", "popcorn_est": 75,
        "intl_multiplier": 1.5, "benchmarks": {"A Simple Favor": 16.0, "Don't Worry Darling": 19.3}
    },
    "Pillion (2026)": {
        "type": "upcoming", "studio_type": "Cult / Indie (A24/Neon)", "release_format": "Standard 3-Day",
        "aware": 10, "interest": 20, "theaters": 800, "buzz": 1.0, "comp": 0.95, 
        "wiki": "Pillion_(film)", "yt_id": "aTAacTUKK00", "yt_fallback": 500000,
        "rt_slug": "pillion", "source_label": "Teaser / First Look", "source_status": "success",
        "tracking_source": "Estimated (Arthouse Niche)", "competitors": "Limited Release Competition",
        "market_demand": "Normal", "popcorn_est": 78,
        "intl_multiplier": 1.5, "benchmarks": {"Past Lives (Wide)": 5.8, "The Whale (Wide)": 11.0, "Moonlight (Wide)": 1.5}
    },
    "The Moment (2026)": {
        "type": "upcoming", "studio_type": "Cult / Indie (A24/Neon)", "release_format": "Standard 3-Day",
        "aware": 15, "interest": 25, "theaters": 2000, "buzz": 1.1, "comp": 0.9, 
        "wiki": "The_Moment_(2026_film)", "yt_id": "ey5YrCNH09g", "yt_fallback": 1500000,
        "rt_slug": "the_moment_2026", "source_label": "Official Trailer", "source_status": "success",
        "tracking_source": "Estimated (Sci-Fi Comps)", "competitors": "Project Hail Mary",
        "market_demand": "Normal", "popcorn_est": 84,
        "intl_multiplier": 2.0, "benchmarks": {"Ex Machina (Wide)": 5.4, "After Yang": 0.04, "Her (Wide)": 5.3}
    },
    "Elden Ring (TBD)": {
        "type": "upcoming", "studio_type": "Major Franchise", "release_format": "Standard 3-Day",
        "aware": 60, "interest": 45, "theaters": 4000, "buzz": 1.4, "comp": 0.8, 
        "wiki": "Elden_Ring", "yt_id": "E3Huy2cdih0", "yt_fallback": 14000000,
        "rt_slug": None, "source_label": "Proxy (Game Trailer)", "source_status": "warning",
        "tracking_source": "Hypothetical (Gamer Comps)", "competitors": "Direct-to-Fan Event",
        "market_demand": "Pent-up / Starved", "popcorn_est": 92,
        "intl_multiplier": 2.2, "benchmarks": {"Dune: Part One": 41.0, "Five Nights at Freddy's": 80.0, "Uncharted": 44.0}
    }
}

historical_data = {
    "Superman (Jul '25)": {
        "type": "historical", "studio_type": "Major Franchise", "release_format": "Standard 3-Day",
        "actual_opening": 115.0, "aware": 85, "interest": 65, "theaters": 4200, "buzz": 1.4, "comp": 0.9, 
        "wiki": "Superman_(2025_film)", "yt_id": "v7s5d4pG2eM", "yt_fallback": 30000000, "frozen_views": 30000000,
        "rt_slug": "superman_2025", "source_label": "Simulated Historical", "source_status": "neutral",
        "tracking_source": "Estimated", "competitors": "Fantastic Four", "market_demand": "Normal", "popcorn_est": 88,
        "intl_multiplier": 2.2, "benchmarks": {"Actual Opening (Sim)": 115.0, "Man of Steel": 116.6}
    },
    # ... (Other historicals same logic)
}

# --- LONG LEAD CALC FUNCTION ---
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

# --- VIEW 1: LONG LEAD ---
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

# --- VIEW 2: TRACKER ---
def render_tracker(dataset, mode_title):
    st.title(mode_title)
    st.markdown("---")

    selected_preset = st.selectbox("Select Project:", list(dataset.keys()), index=0)
    data = dataset[selected_preset]
    
    live_wiki, live_yt, live_rt, live_poly = get_live_data(
        data['wiki'], 
        data['yt_id'], 
        data['yt_fallback'], 
        data['rt_slug'], 
        data.get('frozen_views'),
        data.get('poly_slug')
    )

    # Sidebar
    st.sidebar.markdown("### 📡 Live Signals")
    badge_class = "status-success" if data['source_status'] == "success" else "status-neutral"
    st.sidebar.markdown(f'<span class="status-badge {badge_class}">{data["source_label"]}</span>', unsafe_allow_html=True)
    
    col_a, col_b = st.sidebar.columns(2)
    with col_a: st.sidebar.metric("Wiki Views", f"{live_wiki:,}", help="30-Day Avg")
    with col_b: st.sidebar.metric("Trailer Views", f"{live_yt/1000000:.1f}M")
    
    st.sidebar.markdown("---")
    st.sidebar.caption("Model Tuning")
    studio_type = st.sidebar.selectbox("Studio / Brand Profile", ["Major Franchise", "Cult / Indie (A24/Neon)", "Major Franchise (Animation)"], index=0 if data.get("studio_type") == "Major Franchise" else 1)
    
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
    
    st.sidebar.markdown("#### 🍿 Audience Reception")
    popcorn_default = data.get('popcorn_est', 85)
    popcorn_score = st.sidebar.slider("Popcornmeter (Audience Score)", 0, 100, value=popcorn_default)
    
    st.sidebar.markdown("---")
    buzz = st.sidebar.slider("Social Buzz Multiplier", 0.5, 2.0, value=float(data['buzz']))
    comp = st.sidebar.slider("Competition Factor", 0.5, 1.0, value=float(data['comp']))
    st.sidebar.caption(f"**Opening Against:** {data['competitors']}")
    
    demand_index = 1
    if data.get('market_demand') == "Pent-up / Starved": demand_index = 2
    elif data.get('market_demand') == "Saturated / Crowded": demand_index = 0
    market_demand = st.sidebar.selectbox("Market Demand", ["Saturated / Crowded", "Normal", "Pent-up / Starved"], index=demand_index)
    
    # --- PREDICTION MARKETS SECTION ---
    st.sidebar.markdown("### 🔮 Prediction Markets")
    
    # Check if we have live Polymarket data
    if live_poly:
        st.sidebar.success("✅ Polymarket Data Found")
        st.sidebar.markdown(f"**Market:** {live_poly.get('question')}")
        # Note: Parsing the exact probability from the raw event JSON is complex without the specific outcome ID
        # We display a link to the market instead
        st.sidebar.link_button("View on Polymarket", f"https://polymarket.com/event/{data['poly_slug']}")
    elif data.get('poly_slug'):
        st.sidebar.warning("⚠️ Market Not Found / Closed")
    
    # Manual Input for Betting Odds
    st.sidebar.caption("Manual Betting Odds Input")
    betting_odds = st.sidebar.number_input("Implied Probability (%)", 0, 100, value=0, help="Enter value from Sportsbet/Ladbrokes if available")

    # Calc
    opening, extended, dom_total, global_total = calculate_box_office(
        interest, total_aware, theaters, rt_score, popcorn_score, buzz, comp, live_yt, data['intl_multiplier'], studio_type, market_demand, data.get('release_format', 'Standard 3-Day')
    )

    # Output
    if data.get('type') == 'historical':
        # (Backtest Logic Omitted for brevity - same as before)
        pass
    else:
        col1, col2, col3, col4 = st.columns(4)
        with col1: st.metric("3-Day Opening", f"${opening/1_000_000:.2f}M")
        with col2: 
            if extended: st.metric(f"{data['release_format']}", f"${extended/1_000_000:.2f}M", delta="Holiday")
            else: st.metric("Extended", "N/A")
        with col3: st.metric("Proj. Domestic", f"${dom_total/1_000_000:.2f}M")
        with col4: st.metric("Proj. Global", f"${global_total/1_000_000:.2f}M")
        
        # NEW: Market Consensus Card
        if betting_odds > 0:
             st.info(f"🎲 **Betting Market Consensus:** The betting markets imply a **{betting_odds}%** chance of hitting this target.")

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

# --- MAIN ---
view = st.sidebar.radio("Evaluation Mode", ["🔭 Long-Lead Planner", "📉 Short-Term Tracker", "🕰️ Historical Analysis"])

if view == "🔭 Long-Lead Planner": render_long_lead()
elif view == "📉 Short-Term Tracker": render_tracker(upcoming_data, "📉 Short-Term Tracker")
else: render_tracker(historical_data, "🕰️ Historical Analysis")
