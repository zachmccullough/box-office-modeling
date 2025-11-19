import streamlit as st
import pandas as pd
import altair as alt
import math

# --- PART 0: SHADCN/UI THEME (LIGHT) ---
st.set_page_config(page_title="Long-Lead Slate Model", page_icon="📅", layout="wide")

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
    
    .stTextInput input, .stNumberInput input, .stSelectbox div[data-baseweb="select"] {
        background-color: transparent;
        border-radius: var(--radius);
        border: 1px solid var(--input);
        color: var(--foreground);
        font-size: 0.875rem;
        height: 2.5rem;
    }
    
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

# --- PART 1: LOGIC ENGINE (FUNDAMENTAL ANALYSIS) ---
def calculate_long_lead(genre, cast_score, budget, rating, ip_status, season, competition_level):
    
    # 1. GENRE BASELINES (The "Floor")
    # Based on historical average opening weekends for wide releases
    genre_baselines = {
        "Action/Adventure": 25.0,
        "Horror": 18.0,
        "Sci-Fi": 22.0,
        "Drama": 8.0,
        "Comedy": 12.0,
        "Family/Animation": 28.0,
        "Thriller": 14.0
    }
    base = genre_baselines.get(genre, 10.0)

    # 2. CAST/DIRECTOR POWER (The "Draw")
    # We assume the 'cast_score' is an Avg Opening $ of the lead's last 3 films
    # We apply diminishing returns (a star can only open a movie so much)
    star_power_add = math.sqrt(cast_score) * 2.5
    
    # 3. PRODUCTION VALUE (Budget)
    # Big budget implies big spectacle (and big marketing commit)
    # We add ~10% of the budget to the opening (rough heuristic)
    production_add = budget * 0.08

    # 4. IP MULTIPLIER (The "Brand")
    ip_mult = 1.0
    if ip_status == "Sequel (Major Franchise)": ip_mult = 2.5
    elif ip_status == "Adaptation (Book/Game)": ip_mult = 1.5
    elif ip_status == "Original": ip_mult = 0.9 # Originals are harder to market

    # 5. SEASONALITY
    season_mult = 1.0
    if season == "Summer (May-Jul)": season_mult = 1.3
    elif season == "Holiday (Nov-Dec)": season_mult = 1.4
    elif season == "Dump Months (Jan/Sept)": season_mult = 0.8

    # 6. RATING LIMITER
    rating_mult = 1.0
    if rating == "R": rating_mult = 0.85 # Excludes families/teens
    elif rating == "G/PG": rating_mult = 1.1 # Expands audience

    # 7. COMPETITION DAMPENER
    comp_mult = 1.0
    if competition_level == "High (2+ Wide Releases)": comp_mult = 0.85
    elif competition_level == "Extreme (vs Blockbuster)": comp_mult = 0.7

    # --- FINAL CALCULATION ---
    raw_prediction = (base + star_power_add + production_add) * ip_mult * season_mult * rating_mult * comp_mult
    
    return raw_prediction

# --- PART 2: APP UI ---
st.title("📅 Long-Lead Slate Forecast")
st.caption("Fundamental analysis model for 3-12 month forecasting.")
st.markdown("---")

# --- SIDEBAR INPUTS ---
st.sidebar.header("1. Film DNA")
genre = st.sidebar.selectbox("Genre", ["Action/Adventure", "Horror", "Sci-Fi", "Drama", "Comedy", "Family/Animation", "Thriller"])
rating = st.sidebar.selectbox("MPA Rating", ["PG-13", "R", "PG", "G"])
ip_status = st.sidebar.selectbox("IP Status", ["Original", "Adaptation (Book/Game)", "Sequel (Major Franchise)"])
budget = st.sidebar.number_input("Production Budget ($M)", 5, 300, 50)

st.sidebar.markdown("---")
st.sidebar.header("2. Talent Metrics (Comscore/NRG)")
st.sidebar.caption("Enter the 'Bankability Score' or Avg Opening of the Lead Actor/Director.")
cast_score = st.sidebar.slider("Cast/Director Avg Opening ($M)", 0, 150, 20)

st.sidebar.markdown("---")
st.sidebar.header("3. Release Context")
season = st.sidebar.selectbox("Release Window", ["Average", "Summer (May-Jul)", "Holiday (Nov-Dec)", "Dump Months (Jan/Sept)"])
competition = st.sidebar.selectbox("Crowdedness (Comscore)", ["Low (Clear Weekend)", "Moderate (1 Opener)", "High (2+ Wide Releases)", "Extreme (vs Blockbuster)"])

# --- CALCULATE ---
prediction = calculate_long_lead(genre, cast_score, budget, rating, ip_status, season, competition)

# Create Range (Long lead is volatile, so we show a range)
low_end = prediction * 0.75
high_end = prediction * 1.25

# --- DASHBOARD ---
col1, col2 = st.columns([1, 1.5])

with col1:
    st.metric("Forecasted Opening", f"${prediction:.1f}M")
    
    # Confidence Interval Card
    st.markdown(f"""
    <div style="background-color: #F8FAFC; padding: 15px; border-radius: 8px; border: 1px solid #E2E2E5;">
        <p style="color: #64748B; font-size: 0.85rem; margin-bottom: 5px;">CONFIDENCE INTERVAL (±25%)</p>
        <h3 style="margin: 0; color: #0F172A;">${low_end:.1f}M — ${high_end:.1f}M</h3>
    </div>
    """, unsafe_allow_html=True)

    # Analysis Box
    st.markdown(f"""<div class="tuning-box">
    <b>🧠 Analysis:</b><br>
    This model bases the estimate heavily on <b>{ip_status}</b> status and <b>{genre}</b> baselines.<br><br>
    The <b>${budget}M</b> budget adds a production value premium, while the <b>{rating}</b> rating adjusts the addressable audience cap.
    </div>""", unsafe_allow_html=True)

with col2:
    st.markdown("#### 🧱 Building the Forecast")
    
    # Breakdown Chart (Waterfall-style logic)
    breakdown_data = pd.DataFrame({
        "Factor": ["Genre Baseline", "Star Power Add", "Budget/Spectacle Add", "Final Prediction"],
        "Value": [
            20,  # Placeholder for visualization scale
            math.sqrt(cast_score) * 2.5,
            budget * 0.08,
            prediction
        ],
        "Type": ["Base", "Add-on", "Add-on", "Total"]
    })
    
    c = alt.Chart(breakdown_data).mark_bar().encode(
        x=alt.X('Value', title='Contribution to Opening ($M)'),
        y=alt.Y('Factor', sort=None),
        color=alt.Color('Type', scale=alt.Scale(domain=['Base', 'Add-on', 'Total'], range=['#94A3B8', '#64748B', '#18181B']))
    ).properties(height=300)
    
    st.altair_chart(c, use_container_width=True)

# --- COMPS TABLE ---
st.markdown("---")
st.markdown("#### 🎞️ Automatic Comparables")
st.caption("Historical films with similar DNA (Genre + Budget + Rating)")

# Simple logic to pick comps
comps_db = [
    {"Title": "M3GAN", "Genre": "Horror", "Budget": 12, "Opening": 30.4},
    {"Title": "Smile", "Genre": "Horror", "Budget": 17, "Opening": 22.6},
    {"Title": "The Creator", "Genre": "Sci-Fi", "Budget": 80, "Opening": 14.1},
    {"Title": "Dune: Part One", "Genre": "Sci-Fi", "Budget": 165, "Opening": 41.0},
    {"Title": "Air", "Genre": "Drama", "Budget": 90, "Opening": 14.4},
    {"Title": "Challengers", "Genre": "Drama", "Budget": 55, "Opening": 15.0},
    {"Title": "Bullet Train", "Genre": "Action/Adventure", "Budget": 90, "Opening": 30.0},
    {"Title": "John Wick 4", "Genre": "Action/Adventure", "Budget": 100, "Opening": 73.8},
    {"Title": "No Hard Feelings", "Genre": "Comedy", "Budget": 45, "Opening": 15.0},
    {"Title": "Anyone But You", "Genre": "Comedy", "Budget": 25, "Opening": 6.0},
]

# Filter logic
filtered_comps = [m for m in comps_db if m['Genre'] == genre and abs(m['Budget'] - budget) < 60]

if filtered_comps:
    df_comps = pd.DataFrame(filtered_comps)
    st.dataframe(
        df_comps, 
        use_container_width=True,
        column_config={
            "Opening": st.column_config.NumberColumn("Opening ($M)", format="$%.1fM"),
            "Budget": st.column_config.NumberColumn("Budget ($M)", format="$%.1fM")
        }
    )
else:
    st.info("No direct comps found in database for this specific Genre/Budget combo.")
