"""The live-traffic panel: controls, tiles and the map, as one Streamlit block.

Split from live_flights.py so that module stays importable without Streamlit,
and split from app.py so the panel is three lines there instead of eighty.
render() is the whole public surface; app.py and live_map_demo.py both call it.
"""
import time

import requests
import streamlit as st

from packages import live_flights, theme

REFRESH = {'30 seconds': 30, '1 minute': 60, '5 minutes': 300, 'Off': None}

# Most of the sky is not an airline this app ranks, and at national zoom those
# 4,000-odd cargo, business and GA aircraft are most of what makes the map
# unreadable. Off by default; the checkbox puts them back.
SHOW_OTHER_DEFAULT = False

# The palette holds eight distinct hues and the app knows twenty airlines, so
# showing them all would repeat colours and crowd the map. These six are the
# default because they are the largest mainlines and the set never shifts
# under you; the picker reaches the rest.
DEFAULT_AIRLINES = ['American Airlines', 'Delta Air Lines', 'United Airlines',
                    'Southwest Airlines', 'Alaska Airlines', 'JetBlue Airways']


@st.cache_data(ttl=25, show_spinner=False)
def _load(bucket):
    """Live states, re-read at most once per refresh window.

    `bucket` is a coarsened clock the body never looks at: it changes only when
    the window has rolled over, and that is what expires the entry. The TTL
    underneath is a floor, so two viewers cannot double the credit spend.
    """
    return live_flights.fetch_live_flights()


def _tile(label, value, sub=''):
    st.markdown(
        f'<div class="kpi"><div class="kpi-label">{label}</div>'
        f'<div class="kpi-value">{value}</div>'
        f'<div class="kpi-sub">{sub}</div></div>',
        unsafe_allow_html=True)


def render(mode=None, key='live'):
    """Draw the panel. `key` keeps widget ids distinct if it is ever shown twice."""
    mode = mode or theme.current_mode()

    st.markdown(
        '<div class="legend-note">Every aircraft ADS-B receivers can see over '
        'the lower 48 right now, each turned to its heading. The delay figures '
        'elsewhere in this app are five years of history; this is live.</div>',
        unsafe_allow_html=True)
    st.write('')

    airlines = st.multiselect(
        'Airlines', options=live_flights.CARRIER_ORDER, default=DEFAULT_AIRLINES,
        key=f'{key}_airlines',
        help='The same twenty airlines the delay ranking covers. Past eight '
             'at once the palette starts reusing hues.')

    c0, c1, c2, c3 = st.columns([1.4, 1.4, 1.4, 2.6])
    with c0:
        region = st.selectbox(
            'Region', list(live_flights.REGIONS) + [live_flights.ALL_REGIONS],
            key=f'{key}_region',
            help='All fifty states are in the feed. They get their own frames '
                 'because one view holding Alaska, Hawaii and Florida leaves '
                 'the lower 48 too small to read.')
    with c1:
        every = st.selectbox('Auto-refresh', list(REFRESH), index=1,
                             key=f'{key}_every')
    with c2:
        # Off by default: at a few minutes the line is short enough to read as
        # a spike off the tail rather than a path. It earns its place only
        # when it is long enough to show a flow, so the useful settings are
        # the big ones.
        trail = st.select_slider('Trail', options=[0, 8, 15, 30, 60], value=0,
                                 format_func=lambda m: 'none' if not m else f'{m} min',
                                 key=f'{key}_trail')
    with c3:
        st.write('')
        show_other = st.checkbox(
            'Include cargo, private and GA traffic', value=SHOW_OTHER_DEFAULT,
            key=f'{key}_other',
            help='Roughly two thirds of what is flying. Revealing, but it '
                 'crowds the airlines this app ranks.')

    interval = REFRESH[every]

    @st.fragment(run_every=interval)
    def panel():
        # A fragment reruns only itself, so the controls above do not flicker
        # every interval and the rest of the app is not recomputed.
        window = interval or 300
        try:
            df = _load(int(time.time()) // window)
        except requests.HTTPError as err:
            code = err.response.status_code if err.response is not None else None
            if code == 429:
                anon, keyed = live_flights.daily_budget()
                st.error(
                    f'OpenSky is rate-limiting this address (429). Anonymous '
                    f'reads are budgeted per IP -- about {anon} a day for '
                    f'this map, shared by everyone on the same network -- '
                    f'and they are spent; the allowance refills on a rolling '
                    f'window. An API client raises it to about {keyed:,} a '
                    f'day and counts against the account instead: set '
                    f'OPENSKY_CLIENT_ID / OPENSKY_CLIENT_SECRET.')
            else:
                st.error(f'OpenSky returned HTTP {code}.')
            return
        except requests.RequestException as err:
            st.error(f'Could not reach OpenSky ({type(err).__name__}). '
                     'This panel is the one part of the app that needs '
                     'a live connection.')
            return

        if df.empty:
            st.warning('OpenSky answered but reported no aircraft in the box.')
            return

        if region != live_flights.ALL_REGIONS:
            df = df[df['region'] == region]
            if df.empty:
                st.info(f'Nothing is in the air over {region} right now.')
                return

        keep = set(airlines) | ({live_flights.OTHER} if show_other else set())
        view = df[~df['on_ground'].fillna(False)]
        view = view[view['carrier_label'].isin(keep)]

        # Map first, then its footnote, then the tiles. The tiles summarise the
        # whole region rather than the filtered selection, so they stand on
        # their own below -- and an empty selection still gets them, which is
        # why this branches rather than returning early.
        st.write('')
        if view.empty:
            st.info('Nothing selected is in the air. Pick an airline, or '
                    'switch on the other traffic.')
        else:
            st.pydeck_chart(
                live_flights.flight_deck(view, mode, trail_minutes=trail,
                                         show_trails=bool(trail), region=region),
                height=620,
            )
            trail_note = (
                f'Trails project {trail} minutes back from each heading and '
                'speed — direction of travel, not a filed route. '
                if trail else '')
            st.markdown(
                f'<div class="legend-note">{len(view):,} aircraft drawn · read '
                f'at {time.strftime("%I:%M:%S %p", time.localtime())} · '
                f'{"refreshing every " + every.lower() if interval else "auto-refresh off"}'
                f' · {trail_note}Positions from the '
                '<a href="https://opensky-network.org/">OpenSky Network</a>.</div>',
                unsafe_allow_html=True)

        st.write('')
        stats = live_flights.summarize_traffic(df)
        cols = st.columns(4)
        with cols[0]:
            _tile('In the air now', f"{stats['airborne']:,}",
                  f"{stats['on_ground']:,} more on the ground")
        with cols[1]:
            _tile('Ranked airlines flying', f"{stats['carrier_flights']:,}",
                  f"across {stats['tracked_carriers']} of the 20 this app tracks")
        with cols[2]:
            _tile('Median altitude', f"{stats['median_altitude']:,.0f} ft",
                  f"median speed {stats['median_speed']:,.0f} mph")
        with cols[3]:
            _tile('Climbing / descending',
                  f"{stats['climbing']:,} / {stats['descending']:,}",
                  'a rough read on how many are near an airport')

    panel()
