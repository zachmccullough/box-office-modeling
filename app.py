import streamlit as st

# 1. Title and Description
st.title("🎬 Eternity: Box Office Predictor")
st.write("Adjust the tracking metrics below to estimate the opening weekend.")

# 2. Sidebar Inputs
st.sidebar.header("Tracking Metrics")
unaided = st.sidebar.slider("Unaided Awareness (%)", 0, 15, 5)
total_aware = st.sidebar.slider("Total Awareness (%)", 0, 100, 25)
interest = st.sidebar.slider("Definite Interest (%)", 0, 100, 35)

st.sidebar.header("Market Factors")
theaters = st.sidebar.number_input("Theater Count", 1000, 4000, 2200)
rt_score = st.sidebar.slider("Rotten Tomatoes Score", 0, 100, 85)
buzz = st.sidebar.select_slider("Social Buzz", options=[0.8, 1.0, 1.2, 1.5], value=1.2, 
                               format_func=lambda x: {0.8: "Muted", 1.0: "Normal", 1.2: "High", 1.5: "Viral"}[x])
comp = st.sidebar.select_slider("Competition", options=[0.8, 0.9, 1.0], value=0.9,
                               format_func=lambda x: {0.8: "Heavy (Wicked)", 0.9: "Moderate", 1.0: "Open Sky"}[x])

# 3. The Logic (Backend)
def calculate_box_office():
    # Base Interest Calculation
    base_gross = (interest * 0.15) * (total_aware * 0.05) * 1_000_000
    
    # Capacity Adjustment
    capacity_gross = theaters * 3500
    weighted_gross = (base_gross * 0.6) + (capacity_gross * 0.4)
    
    # Quality Multiplier
    quality_mult = 1.15 if rt_score > 80 else (0.85 if rt_score < 50 else 1.0)
    
    return weighted_gross * quality_mult * buzz * comp

prediction = calculate_box_office()

# 4. The Output (Dashboard)
st.divider()
col1, col2 = st.columns(2)
with col1:
    st.metric(label="Predicted Opening (3-Day)", value=f"${prediction/1_000_000:.2f}M")
with col2:
    st.write("### Scenario Analysis")
    if prediction > 10_000_000:
        st.success("🚀 BREAKOUT HIT: Exceeds expectations.")
    elif prediction > 6_000_000:
        st.info("✅ SOLID PERFORMER: Meets A24 standards.")
    else:
        st.error("⚠️ UNDERPERFORMER: Needs better marketing.")

st.write(f"**Current Assumptions:** {theaters} Screens | {rt_score}% RT Score | Buzz: {buzz}x")
