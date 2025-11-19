import streamlit as st
import requests
from datetime import datetime, timedelta

# --- PART 1: THE TOOLS (Functions) ---

def get_wikipedia_views(article_title):
    """
    Fetches the last 30 days of page views for a Wikipedia article.
    """
    # We need a 'User-Agent' so Wikipedia knows who we are (politeness policy)
    headers = {
        'User-Agent': 'BoxOfficePredictor/1.0 (educational_project)'
    }
    
    # Calculate dates for the last 30 days
    end_date = datetime.now()
    start_date = end_date - timedelta(days=30)
    
    # Format dates for the API (YYYYMMDD)
    str_start = start_date.strftime('%Y%m%d')
    str_end = end_date.strftime('%Y%m%d')
    
    # Official Wikimedia API Endpoint
    url = f"https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/en.wikipedia/all-access/user/{article_title}/daily/{str_start}/{str_end}"
    
    try:
        response = requests.get(url, headers=headers)
        data = response.json()
        
        # Calculate the average daily views
        total_views = sum([item['views'] for item in data['items']])
        daily_avg = total_views / len(data['items'])
        return int(daily_avg)
    except Exception as e:
        return None # Return None if movie not found

def calculate_box_office(interest, total_aware, theaters, rt_score, buzz, comp):
    """
    Core logic for the prediction model
    """
    # Base Interest Calculation
    base_gross = (interest * 0.15) * (total_aware * 0.05) * 1_000_000
    
    # Capacity Adjustment
    capacity_gross = theaters * 3500
    weighted_gross = (base_gross * 0.6) + (capacity_gross * 0.4)
    
    # Quality Multiplier
    quality_mult = 1.15 if rt_score > 80 else (0.85 if rt_score < 50 else 1.0)
    
    return weighted_gross * quality_mult * buzz * comp


# --- PART 2: THE APP LAYOUT (Visuals) ---

st.set_page_config(page_title="Eternity Predictor", page_icon="🎬")

st.title("🎬 Eternity: Box Office Predictor")
st.markdown("Adjust the **Tracking Metrics** on the left to estimate the opening weekend.")

# --- SIDEBAR ---
st.sidebar.header("1. Live Tracking Data")
wiki_title = st.sidebar.text_input("Wikipedia Title", value="Eternity_(2025_film)")

if st.sidebar.button("📢 Fetch Live Wiki Views"):
    with st.spinner("Connecting to Wikipedia..."):
        avg_views = get_wikipedia_views(wiki_title)
        if avg_views:
            st.sidebar.success(f"Last 30 Days: {avg_views:,} views/day")
            if avg_views > 15000:
                st.sidebar.caption("🔥 Trending: High Interest")
            elif avg_views < 2000:
                st.sidebar.caption("❄️ Cold: Niche Interest")
        else:
            st.sidebar.error("Movie not found. Check spelling.")

st.sidebar.divider()

st.sidebar.header("2. Model Inputs")
unaided = st.sidebar.slider("Unaided Awareness (%)", 0, 15, 5)
total_aware = st.sidebar.slider("Total Awareness (%)", 0, 100, 25)
interest = st.sidebar.slider("Definite Interest (%)", 0, 100, 35)

st.sidebar.subheader("Market Factors")
theaters = st.sidebar.number_input("Theater Count", 1000, 4000, 2200)
rt_score = st.sidebar.slider("Rotten Tomatoes Score", 0, 100, 85)
buzz = st.sidebar.select_slider("Social Buzz", options=[0.8, 1.0, 1.2, 1.5], value=1.2, 
                               format_func=lambda x: {0.8: "Muted", 1.0: "Normal", 1.2: "High", 1.5: "Viral"}[x])
comp = st.sidebar.select_slider("Competition", options=[0.8, 0.9, 1.0], value=0.9,
                               format_func=lambda x: {0.8: "Heavy (Wicked)", 0.9: "Moderate", 1.0: "Open Sky"}[x])

# --- MAIN DASHBOARD ---

prediction = calculate_box_office(interest, total_aware, theaters, rt_score, buzz, comp)

st.divider()
col1, col2 = st.columns(2)

with col1:
    st.metric(label="Predicted Opening (3-Day)", value=f"${prediction/1_000_000:.2f}M")
    
with col2:
    st.write("### Analysis")
    if prediction > 10_000_000:
        st.success("🚀 BREAKOUT HIT: Exceeds expectations.")
    elif prediction > 6_000_000:
        st.info("✅ SOLID PERFORMER: Meets A24 standards.")
    else:
        st.error("⚠️ UNDERPERFORMER: Needs better marketing.")

# Simple Visual Bar Chart
st.write("### 📊 Benchmark Comparison")
chart_data = {
    "Eternity (Predicted)": prediction / 1_000_000,
    "Priscilla (Actual)": 5.0,
    "The Iron Claw (Actual)": 4.9,
    "Age of Adaline (Goal)": 13.2
}
st.bar_chart(chart_data)

st.caption(f"Current Assumptions: {theaters} Screens | {rt_score}% RT Score")
