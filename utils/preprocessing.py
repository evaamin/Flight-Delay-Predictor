import pandas as pd
import streamlit as st


@st.cache_data
def filter_coffee(roast, loc_country, df_coffee):
    
    # filter data
    mask = (df_coffee['roast'] == roast) \
        & (df_coffee['loc_country'] == loc_country)
    
    df_ = df_coffee[mask].copy()

    return df_