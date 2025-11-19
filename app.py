import streamlit as st
import requests
from datetime import datetime, timedelta

# --- PART 1: THE TOOLS (Functions) ---

def get_wikipedia_views(article_title):
    """Fetches last 30 days of Wiki page views."""
    headers = {'User-Agent': 'BoxOfficePredictor/1.0'}
    end_date = datetime.now()
    start_date = end_date - timedelta(days=30)
    str_start = start_date.strftime('%Y%m%d')
    str_end = end_date.strftime('%Y%m%d')
    url = f"https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/en.wikipedia/all-access/user/{article_title}/daily/{str_start}/{str_end}"
    
    try:
        data = requests.get(url, headers=headers).json()
        total_views = sum([item['views'] for item in data['items']])
        return int(total_views / len(data['items']))
    except:
        return 0

def calculate_box_office(interest, total_aware, theaters, rt_score, buzz, comp):
    # Base Calculation
    base_gross = (interest * 0.15) * (total_aware * 0.05) * 1_000_000
    capacity_gross = theaters * 3500
    weighted_gross = (base_gross * 0.6) + (capacity_gross * 0.4)
    
    # Multipliers
    quality_mult = 1.15 if rt_score > 80 else (0.85 if rt_score < 50 else 1.0)
    return weighted_gross * quality_mult * buzz * comp

# --- PART 2: REAL DATA PRESETS (The Quorum Data) ---
presets = {
    "Custom / Manual": {"aware": 5, "interest": 35, "theaters": 2200, "buzz": 1.0, "comp": 0.9, "wiki": "Eternity_(2025_film)"},
    "Eternity (Actual Tracking)": {"aware": 21, "interest": 34, "theaters": 2400, "buzz": 1.2, "comp": 0.85, "wiki": "Eternity_(2025_film
