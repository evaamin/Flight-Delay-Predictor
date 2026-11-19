"""The live-traffic panel on its own, without the rest of the app around it.

Handy for working on the map alone; the real home of this is the Live Map tab
in app.py. Both call packages/live_panel.render(), so there is one copy of the
panel and this file cannot drift from it.

Run with:  streamlit run live_map_demo.py

One caution: OpenSky budgets anonymous reads per IP address, not per person --
about 100 a day for the box this map asks for, shared by everyone behind that
address. Reads are cached for the refresh window, so an idle tab costs nothing,
but two copies open on the fastest setting will spend the day in half an hour.
Registering an API client (OPENSKY_CLIENT_ID / OPENSKY_CLIENT_SECRET) moves the
budget to the account and raises it tenfold.
"""
import streamlit as st

from packages import live_panel, theme

st.set_page_config(page_title='Live US Air Traffic', layout='wide',
                   page_icon='🛫')

MODE = theme.current_mode()
st.markdown(theme.css(MODE), unsafe_allow_html=True)

st.markdown('# Live US Air Traffic')
live_panel.render(MODE)
