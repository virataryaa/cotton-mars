"""USDA MARS API - Daily Cotton Quality Summary by State (report 1652)."""
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

DB = Path(__file__).resolve().parent.parent / "Database" / "mars_1652.parquet"
NAVY, TEAL, AMBER, GREEN, RED, GREY = "#0a2463", "#1f8a9c", "#c98a1f", "#1f9d6f", "#c94a4a", "#8a93a8"
PRIOR_COLORS = [RED, TEAL, AMBER, GREEN, GREY, "#6b4fa0"]
METRICS = {
    "Bales classed": "numberofBales", "Avg micronaire": "avgMike", "Avg staple (32nds)": "avgStaple",
    "Avg length (in)": "avgLength", "Avg strength (g/tex)": "avgStrength",
    "Avg uniformity": "avgUniformity", "Avg leaf": "avgLeaf", "Avg trash": "avgTrash",
    "Avg loan premium/disc": "avgLoanPD", "% bark": "pctBark", "% grass": "pctGrass",
    "% tenderable": "pctTenderable", "Gins reporting": "numberofGins",
    "Predominant colour (code)": "predominateColor", "Predominant colour %": "predominateColorPct",
    "Predominant leaf (code)": "predominateLeaf", "Predominant leaf %": "predominateLeafPct",
}
BASE_START = pd.Timestamp(2019, 7, 1)

st.set_page_config(page_title="USDA MARS API", layout="wide")
st.markdown("""<style>
.stApp, body { background:#fafafa; color:#1a1a2e; }
section[data-testid="stSidebar"] { background:#f0f2f8; }
h1, h2, h3 { color:#0a2463; }
span[data-baseweb="tag"], span[data-baseweb="tag"] * { color:#fff !important; fill:#fff !important; }
span[data-baseweb="tag"] { background:#0a2463 !important; }
.side-note { font-size:12px; color:#5a6688; line-height:1.6; }
.side-note b { color:#0a2463; }
</style>""", unsafe_allow_html=True)


@st.cache_data(ttl=3600)
def load():
    d = pd.read_parquet(DB)
    m = d["endDate"].dt.month
    d["season"] = d["endDate"].dt.year.where(m >= 7, d["endDate"].dt.year - 1)
    d["xbase"] = d["endDate"].apply(lambda t: t.replace(year=2019 if t.month >= 7 else 2020))
    return d


def slabel(s):
    return f"{s}/{str(s + 1)[2:]}"


def transform(s, how, win):
    if how == "Rolling mean":
        return s.rolling(win, min_periods=1).mean()
    if how == "Rolling sum":
        return s.rolling(win, min_periods=1).sum()
    if how == "Cumulative":
        return s.cumsum()
    return s


def season_series(d, season, col, freq, how, win, cur_season, last_date):
    """Series indexed by actual end date for one season."""
    x = d[d["season"] == season].sort_values("endDate").drop_duplicates("endDate", keep="last")
    s = x.set_index("endDate")[col].dropna()
    if s.empty:
        return s
    if freq == "Season":
        stop = last_date if season == cur_season else pd.Timestamp(season + 1, 6, 30)
        s = s.reindex(pd.date_range(s.index.min(), max(stop, s.index.max()))).ffill()
    return transform(s, how, win)


def to_base(idx):
    return pd.DatetimeIndex([t.replace(year=2019 if t.month >= 7 else 2020) for t in idx])


def seasonal_chart(d, title, metric, col, freq, how, win, seasons, show_band):
    cur = int(d["season"].max())
    last_date = d["endDate"].max()
    fig = go.Figure()
    focus = max(seasons)
    prior = [s for s in seasons if s != focus]
    step = 7 if freq == "Weekly" else 1
    ser = {s: season_series(d, s, col, freq, how, win, cur, last_date) for s in seasons}

    if show_band and prior:
        parts = []
        for s in prior:
            v = ser[s]
            if v.empty:
                continue
            k = (to_base(v.index) - BASE_START).days // step
            parts.append(pd.Series(v.values, index=k).groupby(level=0).last())
        if parts:
            al = pd.concat(parts, axis=1).sort_index()
            hi, lo, av = al.max(axis=1), al.min(axis=1), al.mean(axis=1)
            bx = BASE_START + pd.to_timedelta(al.index * step, unit="D")
            fig.add_trace(go.Scatter(x=bx, y=hi, line=dict(width=0), showlegend=False, hoverinfo="skip"))
            fig.add_trace(go.Scatter(x=bx, y=lo, line=dict(width=0), fill="tonexty",
                                     fillcolor="rgba(138,147,168,0.22)", name=f"Range ({len(prior)} prior)",
                                     hoverinfo="skip"))
            fig.add_trace(go.Scatter(x=bx, y=av, name="Prior avg", line=dict(color="#1a1a2e", width=1.5, dash="dash"),
                                     hovertemplate="%{y:,.2f}<extra>Prior avg</extra>"))
    for i, s in enumerate(sorted(prior, reverse=True)):
        v = ser[s]
        if v.empty:
            continue
        fig.add_trace(go.Scatter(
            x=to_base(v.index), y=v.values, name=slabel(s), customdata=v.index.strftime("%d-%b-%Y"),
            line=dict(color=PRIOR_COLORS[i % len(PRIOR_COLORS)], width=1.3),
            hovertemplate="%{customdata}: %{y:,.2f}<extra>" + slabel(s) + "</extra>"))
    v = ser[focus]
    if not v.empty:
        fig.add_trace(go.Scatter(
            x=to_base(v.index), y=v.values, name=slabel(focus), customdata=v.index.strftime("%d-%b-%Y"),
            line=dict(color=NAVY, width=3),
            hovertemplate="%{customdata}: %{y:,.2f}<extra>" + slabel(focus) + "</extra>"))
    fig.update_layout(
        template="plotly_white", height=430, margin=dict(l=10, r=10, t=50, b=10), hovermode="x unified",
        title=dict(text=f"{title} - {metric} ({freq})", font=dict(size=14, color=NAVY)),
        xaxis=dict(tickformat="%b", dtick="M1", range=["2019-07-01", "2020-06-30"]),
        yaxis=dict(tickformat=",.3s" if col == "numberofBales" else None),
        legend=dict(orientation="h", y=-0.12))
    return fig


def timeseries_chart(d, states, metric, col, freq, how, win, lo, hi):
    fig = go.Figure()
    for i, name in enumerate(states):
        x = d[d["classing_State"] == name].sort_values("endDate").drop_duplicates("endDate", keep="last")
        s = transform(x.set_index("endDate")[col].dropna(), how, win)
        s = s[(s.index >= lo) & (s.index <= hi)]
        fig.add_trace(go.Scatter(x=s.index, y=s.values, name=name,
                                 line=dict(color=([NAVY] + PRIOR_COLORS)[i % 7], width=1.8 if i else 2.4)))
    fig.update_layout(
        template="plotly_white", height=470, margin=dict(l=10, r=10, t=50, b=10), hovermode="x unified",
        title=dict(text=f"{metric} ({freq})", font=dict(size=14, color=NAVY)),
        yaxis=dict(tickformat=",.3s" if col == "numberofBales" else None), legend=dict(orientation="h", y=-0.12))
    return fig


df = load()
st.title("USDA MARS API")
st.caption("Daily cotton classing by state - AMS report 1652")

with st.sidebar:
    view = st.radio("View", ["Seasonal", "Time series"], horizontal=True)
    commodity = st.selectbox("Commodity", sorted(df["commodity"].unique()))
    dc = df[df["commodity"] == commodity]
    states_all = sorted(dc["classing_State"].unique(), key=lambda s: (s != "United States All Cotton", s))
    states = st.multiselect("State(s)", states_all, default=["United States All Cotton"])
    metric = st.selectbox("Metric", list(METRICS))
    freq = st.radio("Frequency", ["Daily", "Weekly", "Season"], index=2, horizontal=True)
    how = st.selectbox("Transform", ["Raw", "Rolling mean", "Rolling sum", "Cumulative"])
    win = st.number_input("Rolling window (obs)", 1, 60, 7) if how.startswith("Rolling") else 1
    col = METRICS[metric]
    dd = dc[dc["period"] == freq]

    if view == "Seasonal":
        all_s = sorted(dd["season"].unique(), reverse=True)
        seasons = st.multiselect("Seasons", all_s, default=all_s[:5], format_func=slabel)
        show_band = st.toggle("Prior-season range & avg", value=True)
    else:
        mn, mx = dd["endDate"].min().date(), dd["endDate"].max().date()

        def _from_inputs():
            st.session_state["rng"] = (st.session_state["d_from"], st.session_state["d_to"])

        def _from_slider():
            st.session_state["d_from"], st.session_state["d_to"] = st.session_state["rng"]

        st.session_state.setdefault("d_from", mn)
        st.session_state.setdefault("d_to", mx)
        st.session_state.setdefault("rng", (mn, mx))
        c1, c2 = st.columns(2)
        c1.date_input("From", min_value=mn, max_value=mx, key="d_from", on_change=_from_inputs)
        c2.date_input("To", min_value=mn, max_value=mx, key="d_to", on_change=_from_inputs)
        st.slider("Range", mn, mx, key="rng", on_change=_from_slider, label_visibility="collapsed")

    last = df["endDate"].max()
    cur = int(df["season"].max())
    us = df[(df["commodity"] == "Upland") & (df["classing_State"] == "United States All Cotton")
            & (df["period"] == "Season")]
    now = us[us["season"] == cur].sort_values("endDate").iloc[-1]
    pr = us[us["season"] < cur].copy()
    tgt = (now["xbase"] - BASE_START).days
    pr["doy"] = (pr["xbase"] - BASE_START).dt.days
    pa = pr[pr["doy"] <= tgt].sort_values("endDate").groupby("season").tail(1)["numberofBales"].tail(4).mean()
    st.markdown(
        f"<div class='side-note'>Last data: <b>{last:%d-%b-%Y}</b><br>"
        f"Upland {slabel(cur)} to date: <b>{now['numberofBales']:,.0f}</b> bales<br>"
        f"vs prior-4 avg: <b>{now['numberofBales'] / pa - 1:+.1%}</b></div>", unsafe_allow_html=True)

if not states:
    st.info("Select a state.")
elif view == "Seasonal":
    if not seasons:
        st.info("Select a season.")
    else:
        for name in states:
            sub = dd[dd["classing_State"] == name]
            if sub[col].notna().any():
                st.plotly_chart(seasonal_chart(sub, f"{commodity} - {name}", metric, col, freq, how, win,
                                               seasons, show_band), width="stretch")
            else:
                st.caption(f"{name}: no data for {metric}.")
        st.caption(f"Seasons run Jul-Jun. Latest season in navy. Last data point: {last:%d-%b-%Y}.")
else:
    lo, hi = pd.Timestamp(st.session_state["d_from"]), pd.Timestamp(st.session_state["d_to"])
    st.plotly_chart(timeseries_chart(dd, states, metric, col, freq, how, win, lo, hi), width="stretch")
