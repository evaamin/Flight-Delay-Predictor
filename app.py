"""Flight Delay Predictor — starter.

Run with: streamlit run app.py

The full version is saved in git at commit f94b42d. To get it back:
    git show f94b42d:app.py > app.py
"""

import calendar

import pandas as pd
import streamlit as st

from packages.plot_data import *

DATA = "delays_by_airport_month.parquet"

st.set_page_config(
    page_title="Flight Delay Predictor",
    page_icon="✈️",
    layout="wide"
)


@st.cache_data
def load():
    return pd.read_parquet(DATA)


df = load()


# ---------------------------------------------------------
# Header
# ---------------------------------------------------------

st.title("✈️ Flight Delay Predictor")

st.markdown(
    """
    ### Explore flight delay patterns across U.S. airports

    Use historical U.S. Department of Transportation data from
    2021–2026 to compare airline and airport on-time performance.
    """
)

st.divider()


# ---------------------------------------------------------
# Summary metrics
# ---------------------------------------------------------

col1, col2, col3 = st.columns(3)

with col1:
    st.metric(
        "Flights",
        f"{df['flights'].sum():,.0f}"
    )

with col2:
    st.metric(
        "Airports",
        f"{df['airport'].nunique():,}"
    )

with col3:
    st.metric(
        "Airlines",
        f"{df['carrier'].nunique():,}"
    )


# ---------------------------------------------------------
# Filters
# ---------------------------------------------------------

st.subheader("Explore flight performance")

airport_col, airline_col, month_col = st.columns(3)

with airport_col:
    selected_airport = st.selectbox(
        "Airport",
        sorted(df["airport_name"].dropna().unique())
    )


# Keep only observations for the selected airport
airport_df = df[
    df["airport_name"] == selected_airport
]


with airline_col:
    selected_airline = st.selectbox(
        "Airline",
        sorted(
            airport_df["carrier_label"]
            .dropna()
            .unique()
        )
    )


with month_col:
    selected_month = st.selectbox(
        "Month",
        sorted(
            airport_df["month"]
            .dropna()
            .unique()
        ),
        format_func=lambda x: calendar.month_name[int(x)]
    )


# Keep only observations matching the selected airline and month
filtered_df = airport_df[
    (airport_df["carrier_label"] == selected_airline)
    & (airport_df["month"] == selected_month)
]


# ---------------------------------------------------------
# Display filtered data
# ---------------------------------------------------------

if filtered_df.empty:
    st.warning("No data available for this selection.")
else:
    st.dataframe(
        filtered_df,
        width="stretch"
    )


# ---------------------------------------------------------
# Existing visualizations
# ---------------------------------------------------------

st.caption("General performance across airlines")

fig1 = airline_delays()

st.pyplot(fig1)


st.caption("Delay rate across airlines")

fig2 = delay_rate()

st.pyplot(fig2)