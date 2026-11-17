"""Live US air traffic, from the OpenSky Network.

The only live feed in the project -- every other view draws the historical BTS
table. A position is whatever OpenSky's volunteer receiver network saw in the
last few seconds, so coverage is dense over land and thin over water.

Kept free of Streamlit on purpose, the way weather.py is: the page that shows
this decides what to cache. That matters here, because OpenSky's anonymous tier
is metered per IP address -- 400 credits a day, and the box this module reads
costs 4 a call, so 100 reads before the budget is gone, shared by everyone
behind that IP. Always read this through a TTL cache. Registering an API
client (OPENSKY_CLIENT_ID / OPENSKY_CLIENT_SECRET) moves the budget to the
account and raises it to 4,000 credits, which is what a deployed copy needs.

The map is deck.gl, via pydeck: aircraft-shaped icons turned to their heading,
over a basemap that pans and zooms. Plotly draws every other chart in this app
but cannot draw this one -- it has no aircraft glyph, and cannot rotate a text
one on a geo axis, so the best it manages is a flat arrow.
"""
import base64
import functools
import io
import math
import os
import time

import pandas as pd
import pydeck as pdk
import requests
from PIL import Image, ImageDraw

from carriers import CARRIERS
from packages import theme

API = 'https://opensky-network.org/api/states/all'
TOKEN_URL = ('https://auth.opensky-network.org/auth/realms/opensky-network'
             '/protocol/openid-connect/token')

# Anonymous reads are budgeted per IP address; a registered client gets ten
# times the credits and is budgeted per account instead, which is what a group
# sharing one network wants. OpenSky dropped username/password auth in March
# 2026, so this is the OAuth2 client-credentials flow: make an API client on
# the account, then export OPENSKY_CLIENT_ID / OPENSKY_CLIENT_SECRET.
_token = {'value': None, 'expires': 0.0}

# OpenSky sends a bare array per aircraft; these are its columns, in order.
STATE_COLS = ['icao24', 'callsign', 'origin_country', 'time_position',
              'last_contact', 'longitude', 'latitude', 'baro_altitude',
              'on_ground', 'velocity', 'true_track', 'vertical_rate',
              'sensors', 'geo_altitude', 'squawk', 'spi', 'position_source']

# The fifty states do not fit one comfortable frame -- at a zoom holding
# Alaska, Hawaii and Florida at once, the lower 48 is a smear across the
# corner -- so each is its own region: a box that says which aircraft belong
# to it, and a camera that frames it. The panel picks one.
REGIONS = {
    'Lower 48': dict(bbox=dict(lamin=24.0, lomin=-125.0, lamax=50.0, lomax=-66.0),
                     view=dict(latitude=39.3, longitude=-96.0, zoom=3.4)),
    'Alaska':   dict(bbox=dict(lamin=51.0, lomin=-180.0, lamax=72.0, lomax=-129.0),
                     view=dict(latitude=63.5, longitude=-152.0, zoom=3.5)),
    'Hawaii':   dict(bbox=dict(lamin=18.0, lomin=-161.0, lamax=23.0, lomax=-154.0),
                     view=dict(latitude=20.6, longitude=-157.4, zoom=6.2)),
}

# All fifty at once: mostly Pacific, but it is the only view that shows the
# Alaska and Hawaii traffic in the same frame as everything else.
ALL_REGIONS = 'All 50 states'
ALL_VIEW = dict(latitude=40.0, longitude=-133.0, zoom=2.1)

# One request covers every region. Three separate calls would cost eight
# OpenSky credits against the daily 400; this box costs four, at the price of
# also returning Canada, Mexico and a lot of ocean -- which _region_of drops.
US_BBOX = dict(lamin=18.0, lomin=-180.0, lamax=72.0, lomax=-66.0)

# ICAO telephony prefix -> the IATA code carriers.py knows the airline by, so
# the live map and the delay ranking name the same airline the same way. Only
# carriers the ranking covers are here; everything else falls to 'Other
# traffic', which is most of the sky (cargo, business, GA, military).
ICAO_TO_IATA = {
    'AAL': 'AA', 'DAL': 'DL', 'UAL': 'UA', 'SWA': 'WN', 'ASA': 'AS',
    'JBU': 'B6', 'FFT': 'F9', 'AAY': 'G4',
    'EDV': '9E', 'ENY': 'MQ', 'JIA': 'OH', 'PDT': 'PT', 'QXE': 'QX',
    'SKW': 'OO', 'RPA': 'YX', 'ASH': 'YV', 'GJS': 'G7', 'CMT': 'C5',
    'AWI': 'ZW',
}

OTHER = 'Other traffic'

M_TO_FT = 3.28084
MS_TO_MPH = 2.23694
MI_PER_DEG_LAT = 69.0        # close enough across the lower 48
MI_PER_DEG_LON = 69.172      # at the equator; scaled by cos(latitude) below


# --- the feed --------------------------------------------------------------

def fetch_live_flights(bbox=None, timeout=30):
    """Current aircraft states over the US, one row per aircraft.

    Returns a DataFrame with the raw OpenSky columns plus the derived ones the
    map and the tiles read: altitude_ft, speed_mph, carrier_label, vertical
    (Climbing/Descending/Level) and flight (the tidied callsign). Raises
    requests.HTTPError on a refusal -- 429 is the one to expect, and it means
    the credit budget is spent, not that something is broken.
    """
    params = dict(bbox or US_BBOX)
    res = requests.get(API, params=params, headers=_auth_header(),
                       timeout=timeout)
    res.raise_for_status()
    payload = res.json()

    df = pd.DataFrame(payload.get('states') or [], columns=STATE_COLS)
    if df.empty:
        return df.assign(altitude_ft=[], speed_mph=[], carrier_label=[],
                         vertical=[], flight=[], heading=[])

    # A position is the one thing a row cannot do without.
    df = df.dropna(subset=['latitude', 'longitude']).copy()

    df['flight'] = df['callsign'].fillna('').str.strip().replace('', 'unknown')
    df['carrier_label'] = df['flight'].map(_airline)

    # Metres and metres/second are the API's units, not the reader's.
    df['altitude_ft'] = (df['baro_altitude'].fillna(df['geo_altitude'])
                         * M_TO_FT)
    df['speed_mph'] = df['velocity'] * MS_TO_MPH
    df['heading'] = df['true_track'].fillna(0)

    # +/- 1.5 m/s is inside the noise of a barometric climb rate, so calling
    # that band level keeps the split from flickering between refreshes.
    rate = df['vertical_rate'].fillna(0)
    df['vertical'] = pd.cut(rate, [-1e9, -1.5, 1.5, 1e9],
                            labels=['Descending', 'Level', 'Climbing'])

    # The one fetch box is wider than the states it covers, so label each row
    # with its region and drop what falls between them -- otherwise the tiles
    # would count Canadian and Mexican traffic as US flights.
    df['region'] = _region_of(df)
    return df[df['region'].notna()].reset_index(drop=True)


def _region_of(df):
    """Which region each row sits in, or NA for the ocean and the neighbours."""
    out = pd.Series(pd.NA, index=df.index, dtype='object')
    for name, spec in REGIONS.items():
        b = spec['bbox']
        inside = (df['latitude'].between(b['lamin'], b['lamax'])
                  & df['longitude'].between(b['lomin'], b['lomax']))
        out = out.mask(inside & out.isna(), name)
    return out


def _auth_header(timeout=15):
    """Bearer header for the configured API client, or {} to read anonymously.

    Tokens last about half an hour, so one is kept in module state and renewed
    a minute early. Falling back to anonymous on a failed token exchange is
    deliberate: bad credentials should cost the smaller budget, not the map.
    """
    client = os.getenv('OPENSKY_CLIENT_ID')
    secret = os.getenv('OPENSKY_CLIENT_SECRET')
    if not (client and secret):
        return {}

    if _token['value'] and time.time() < _token['expires']:
        return {'Authorization': f"Bearer {_token['value']}"}

    try:
        res = requests.post(TOKEN_URL, timeout=timeout, data={
            'grant_type': 'client_credentials',
            'client_id': client, 'client_secret': secret})
        res.raise_for_status()
        body = res.json()
        _token['value'] = body['access_token']
        _token['expires'] = time.time() + body.get('expires_in', 1800) - 60
        return {'Authorization': f"Bearer {_token['value']}"}
    except (requests.RequestException, KeyError, ValueError):
        return {}


def credit_cost(bbox=None):
    """What one read of this box costs against the daily allowance.

    OpenSky prices a request by the area it covers, so this is the number that
    decides how many refreshes a day the panel can afford.
    """
    b = bbox or US_BBOX
    area = (b['lamax'] - b['lamin']) * (b['lomax'] - b['lomin'])
    for ceiling, cost in ((25, 1), (100, 2), (400, 3)):
        if area <= ceiling:
            return cost
    return 4


def daily_budget(bbox=None):
    """(reads per day anonymously, reads per day with an API client)."""
    cost = credit_cost(bbox)
    return 400 // cost, 4000 // cost


def _airline(callsign):
    """Airline for a callsign, by its first three letters (UAL371 -> United)."""
    code = ICAO_TO_IATA.get(callsign[:3].upper())
    return CARRIERS[code][0] if code in CARRIERS else OTHER


def summarize_traffic(df):
    """The handful of numbers worth a tile above the map."""
    air = df[~df['on_ground'].fillna(False)]
    known = air[air['carrier_label'] != OTHER]
    return {
        'airborne': len(air),
        'on_ground': len(df) - len(air),
        'tracked_carriers': known['carrier_label'].nunique(),
        'carrier_flights': len(known),
        'median_altitude': air['altitude_ft'].median(),
        'median_speed': air['speed_mph'].median(),
        'climbing': int((air['vertical'] == 'Climbing').sum()),
        'descending': int((air['vertical'] == 'Descending').sum()),
    }


# Airline order for colour, fixed by carriers.py rather than by how many of
# each happen to be up: a live count is a moving number, and ranking by it
# would hand an airline a different colour every refresh. There are more
# airlines here than palette slots, so beyond eight on screen at once the
# hues repeat -- which is why the panel shows a chosen few by default.
CARRIER_ORDER = [name for name, _kind, _brands in CARRIERS.values()]
CARRIER_SLOTS = {name: i % theme.MAX_SERIES
                 for i, name in enumerate(CARRIER_ORDER)}


def carrier_colors(df, mode='light'):
    """{airline: '#rrggbb'} -- its palette slot for a ranked carrier, the
    neutral grey for everything else. Stable across refreshes."""
    pal = theme.palette(mode)
    present = set(df['carrier_label'].unique())
    ranked = [n for n in CARRIER_ORDER if n in present]
    out = theme.assign_colors(ranked, CARRIER_SLOTS, mode)
    out[OTHER] = pal['other']
    return out


# --- the deck.gl renderer --------------------------------------------------

@functools.lru_cache(maxsize=1)
def airplane_icon(size=128):
    """A white top-down aircraft silhouette as a PNG data URI, pointing north.

    Drawn here rather than fetched so the map has no external asset to wait on,
    and white rather than coloured because the icon is used as a mask: deck.gl
    tints the alpha channel per aircraft, which is what lets one 3 KB image
    carry every airline's colour.

    Supersampled 4x and reduced, because PIL does not antialias a polygon.
    """
    scale = 4
    big = size * scale
    alpha = Image.new('L', (big, big), 0)
    pen = ImageDraw.Draw(alpha)

    def at(points):
        return [(x / 100 * big, y / 100 * big) for x, y in points]

    pen.ellipse(at([(45, 5), (55, 90)]), fill=255)
    pen.polygon(at([(50, 34), (97, 63), (97, 71),
                    (50, 57), (3, 71), (3, 63)]), fill=255)
    pen.polygon(at([(50, 74), (73, 88), (73, 94),
                    (50, 85), (27, 94), (27, 88)]), fill=255)

    alpha = alpha.resize((size, size), Image.LANCZOS)
    white = Image.new('L', (size, size), 255)
    icon = Image.merge('RGBA', [white, white, white, alpha])

    buf = io.BytesIO()
    icon.save(buf, format='PNG', optimize=True)
    return 'data:image/png;base64,' + base64.b64encode(buf.getvalue()).decode()


def _rgb(hex_color):
    h = hex_color.lstrip('#')
    return [int(h[i:i + 2], 16) for i in (0, 2, 4)]


def trail_points(df, minutes=8):
    """Where each aircraft was `minutes` ago, if it held this course and speed.

    A projection backwards, not a filed route and not an observed track: the
    feed gives one position per aircraft, so the only honest claim here is
    'came from roughly that direction'. Straight-line is a fair approximation
    in cruise and wrong in a turn, which is the trade for drawing a trail at
    all. Whatever shows this must say so.
    """
    out = pd.DataFrame(index=df.index)
    miles = df['speed_mph'].fillna(0) * (minutes / 60.0)
    bearing = df['heading'].fillna(0).map(math.radians)
    lat = df['latitude']
    out['lat0'] = lat - miles * bearing.map(math.cos) / MI_PER_DEG_LAT
    out['lon0'] = df['longitude'] - (
        miles * bearing.map(math.sin)
        / (MI_PER_DEG_LON * lat.map(lambda v: max(math.cos(math.radians(v)),
                                                  0.01)))
    )
    return out


def auto_icon_size(count):
    """Icon pixels for a given number of aircraft on screen.

    A size that reads well for one airline over one state turns the whole
    country into a solid mat of wings, so the glyph shrinks as the crowd
    grows instead of making the reader find the slider.
    """
    for ceiling, size in ((200, 26), (600, 20), (1500, 15), (4000, 11)):
        if count < ceiling:
            return size
    return 8


def flight_deck(df, mode='light', trail_minutes=8, icon_size=None,
                show_trails=True, region='Lower 48'):
    """Live positions as aircraft icons on their heading, each with a trail.

    Returns a pydeck Deck for st.pydeck_chart. Colour is the airline's own
    palette slot, applied by tinting the icon mask, so this map and the delay
    charts agree about which blue is United.
    """
    pal = theme.palette(mode)
    colors = carrier_colors(df, mode) if not df.empty else {}
    if icon_size is None:
        icon_size = auto_icon_size(len(df))
    view = dict(REGIONS[region]['view'] if region in REGIONS else ALL_VIEW)

    frame = pd.DataFrame({
        # Four decimals is about 11 m -- past the point a 20 px icon can show,
        # and it keeps the payload for several thousand aircraft reasonable.
        'lat': df['latitude'].round(4),
        'lon': df['longitude'].round(4),
        # deck.gl turns an icon counter-clockwise; a heading runs clockwise
        # from north, so the one has to be the negative of the other.
        'angle': ((-df['heading'].fillna(0)) % 360).round(1),
        'icon': 'plane',
        'color': df['carrier_label'].map(
            lambda c: _rgb(colors.get(c, pal['other']))),
        'flight': df['flight'],
        'carrier': df['carrier_label'],
        'altitude': df['altitude_ft'].map(
            lambda v: f'{v:,.0f} ft' if pd.notna(v) else 'altitude unknown'),
        'speed': df['speed_mph'].map(
            lambda v: f'{v:,.0f} mph' if pd.notna(v) else 'speed unknown'),
        'vertical': df['vertical'].astype(str),
    }) if not df.empty else pd.DataFrame(
        columns=['lat', 'lon', 'angle', 'icon', 'color', 'flight', 'carrier',
                 'altitude', 'speed', 'vertical'])

    layers = []

    if show_trails and not df.empty:
        trails = trail_points(df, trail_minutes).round(4)
        trails = trails.assign(lat=frame['lat'], lon=frame['lon'],
                               color=frame['color'])
        layers.append(pdk.Layer(
            'LineLayer', data=trails,
            get_source_position=['lon0', 'lat0'],
            get_target_position=['lon', 'lat'],
            get_color='color', get_width=1,
            width_min_pixels=1, width_max_pixels=1,
            # Faint on purpose. The aircraft is the mark; the trail is
            # context, and at full strength it competes with the glyph it is
            # attached to instead of sitting behind it.
            opacity=0.18 if mode == 'light' else 0.26,
            pickable=False,
        ))

    layers.append(pdk.Layer(
        'IconLayer', data=frame,
        get_icon='icon', get_position=['lon', 'lat'],
        get_angle='angle', get_color='color',
        get_size=icon_size,
        # String() again, and it matters more here: as a bare string this
        # serialises "@@=pixels", deck.gl cannot read it, and the size falls
        # back to world units -- which draws every aircraft a hundred miles
        # wide. The pixel caps below are a belt on top of that brace.
        size_units=pdk.types.String('pixels'),
        size_scale=1, size_min_pixels=6, size_max_pixels=40,
        # One atlas for the whole layer; the rows carry a key, not a copy of
        # the image. mask lets get_color tint the silhouette.
        # String() keeps pydeck from reading the URI as a data accessor: a bare
        # string here is serialised "@@=data:image/png..." and evaluated in the
        # browser, which silently leaves every aircraft unpainted.
        icon_atlas=pdk.types.String(airplane_icon()),
        icon_mapping={'plane': {'x': 0, 'y': 0, 'width': 128, 'height': 128,
                                'anchorX': 64, 'anchorY': 64, 'mask': True}},
        pickable=True,
    ))

    style = (pdk.map_styles.CARTO_DARK_NO_LABELS if mode == 'dark'
             else pdk.map_styles.CARTO_LIGHT_NO_LABELS)

    return pdk.Deck(
        layers=layers,
        map_style=style,
        # The camera frames the chosen region. min_zoom is set just under
        # that region's own zoom so the view cannot pull back into empty
        # world, while still allowing the wide all-fifty frame when that is
        # what was asked for; max_zoom reaches a single airport. deck.gl has
        # no declarative pan bounds, so drifting sideways offshore stays
        # possible -- there is simply nothing drawn out there.
        initial_view_state=pdk.ViewState(
            **view, min_zoom=max(view['zoom'] - 0.4, 1.8), max_zoom=10,
            bearing=0, pitch=0),
        tooltip={
            'html': '<b>{flight}</b><br/>{carrier}'
                    '<br/>{altitude} &middot; {speed}<br/>{vertical}',
            'style': {'backgroundColor': pal['surface'], 'color': pal['ink'],
                      'fontSize': '12px', 'borderRadius': '8px',
                      'fontFamily': theme.FONT},
        },
    )

