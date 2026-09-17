import pickle

import streamlit as st
from streamlit_gsheets import GSheetsConnection

from utils.preprocessing import *
from utils.modeling import *


# ------------------------------------------------------
#                      APP CONSTANTS
# ------------------------------------------------------
MODELPATH = './model.pickle'

# ------------------------------------------------------
#                  CACHE DATA AND MODEL
# these two functions could also be in a separate module
# ------------------------------------------------------
@st.cache_resource
def get_model():
    with open(MODELPATH, 'rb') as f:
        analyzer = pickle.load(f)
    
    return analyzer

@st.cache_data
def get_benchmarks(df_coffee):
    # average sentiment scores for the whole dataset
    benchmarks = df_coffee[['neg', 'neu', 'pos', 'compound']] \
                    .agg(['mean', 'median'])
    
    return benchmarks

# Create a connection object.
conn = st.connection("gsheets", type=GSheetsConnection)

# Caches data ... setting ttl=0 will disable caching
df_coffee = conn.read(ttl="5m")

# define the sheet name if there are multiple tabs
# df = conn.read(worksheet="Sheet1", ttl="5m")

benchmarks = get_benchmarks(df_coffee)
analyzer = get_model()

# ------------------------------------------------------
#                         APP
# ------------------------------------------------------
# ------------------------------
# PART 0 : Overview
# ------------------------------
st.write(
'''
# Review Sentiment Analysis
We pull data from Google Sheets, analyze it, and render analyses in Streamlit.
''')

# ------------------------------
# PART 1 : Filter Data
# ------------------------------
roast = st.selectbox("Select a roast:",
                     df_coffee['roast'].unique())

loc_country = st.selectbox("Select a roaster location:",
                     df_coffee['loc_country'].unique())

# note that this function caches data returned based on repeated input
df_filtered = filter_coffee(roast, loc_country, df_coffee)

st.write(
'''
**Your filtered data:**
''')

st.dataframe(df_filtered)

# ------------------------------
# PART 2 : Plot
# ------------------------------

st.write(
'''
## Visualize
Compare this subset of reviews with the rest of the data.
'''
)

fig = plot_sentiment(df_filtered, benchmarks)
st.plotly_chart(fig)

# ------------------------------
# PART 3 : Analyze Input Sentiment
# ------------------------------

st.write(
'''
## Custom Sentiment Check

Compare these results with the sentiment scores of your own input.
'''
)

text = st.text_input("Write a paragraph, if you like.", 
                     "Your text here.")

df_sentiment = get_sentence_sentiment(text, analyzer)

st.dataframe(df_sentiment)