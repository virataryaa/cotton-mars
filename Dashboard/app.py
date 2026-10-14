"""USDA MARS API - US cotton classing, quality, spot and forward contracting (AMS MARS reports)."""
from datetime import timedelta
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

DB = Path(__file__).resolve().parent.parent / "Database"
NAVY, TEAL, AMBER, GREEN, RED, GREY = "#0a2463", "#1f8a9c", "#c98a1f", "#1f9d6f", "#c94a4a", "#8a93a8"
US_OFFICE = ["United States", "United States All Cotton"]
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

st.set_page_config(page_title="USDA MARS API", layout="wide")
st.markdown("""
<style>
[data-testid="stAppViewContainer"], [data-testid="stMain"], .main { background:#fafafa !important; }
[data-testid="stHeader"] { background:#fafafa !important; }
[data-testid="stSidebar"] { background:#f0f2f8 !important; border-right:1px solid #dfe3ee; }
h1, h2, h3, h4, h5, h6 { color:#0a2463 !important; }
body, .main { color:#1a1a2e; }
.stTabs [data-baseweb="tab-list"] { background:#eef0f6; padding:4px; border-radius:999px; gap:4px; display:inline-flex; }
.stTabs [data-baseweb="tab"] { background:transparent !important; color:#5a6688 !important; border-radius:999px !important;
    padding:8px 20px !important; font-weight:600; border:none !important; }
.stTabs [aria-selected="true"] { background:#0a2463 !important; color:#ffffff !important; }
.stTabs [data-baseweb="tab-highlight"], .stTabs [data-baseweb="tab-border"] { display:none !important; }
.stTabs [data-baseweb="tab"] { padding:5px 16px !important; font-size:13px; min-height:0 !important; height:auto !important; }
.stTabs [data-baseweb="tab-list"] { padding:3px; }
/* sub-tabs: slim underline style */
.stTabs .stTabs [data-baseweb="tab-list"] { background:transparent; border-radius:0; padding:0; gap:2px; display:flex;
    border-bottom:1px solid #dfe3ee; width:100%; }
.stTabs .stTabs [data-baseweb="tab"] { border-radius:0 !important; padding:4px 14px !important; font-size:12.5px; font-weight:500;
    color:#7a86a8 !important; border-bottom:2px solid transparent !important; margin-bottom:-1px; }
.stTabs .stTabs [aria-selected="true"] { background:transparent !important; color:#0a2463 !important; font-weight:700;
    border-bottom:2px solid #0a2463 !important; }
div[role="radiogroup"] { background:#eef0f6; padding:4px; border-radius:999px; gap:2px; display:inline-flex; flex-wrap:wrap; }
div[role="radiogroup"] label { background:transparent !important; border-radius:999px !important; padding:4px 12px !important; margin:0 !important; }
div[role="radiogroup"] label[data-baseweb="radio"] > div:first-child { display:none; }
div[role="radiogroup"] label div[data-testid="stMarkdownContainer"] p { font-size:12px !important; color:#5a6688; }
div[role="radiogroup"] label:has(input:checked) { background:#0a2463 !important; }
div[role="radiogroup"] label:has(input:checked) div[data-testid="stMarkdownContainer"] p { color:#ffffff !important; font-weight:600; }
span[data-baseweb="tag"], span[data-baseweb="tag"] div, span[data-baseweb="tag"] span { background-color:#0a2463 !important; color:#ffffff !important; fill:#ffffff !important; }
span[data-baseweb="tag"] svg { fill:#ffffff !important; }
[data-baseweb="popover"] [data-baseweb="menu"] { background:#ffffff !important; }
[data-baseweb="popover"] [data-baseweb="menu"] li, [data-baseweb="popover"] [data-baseweb="menu"] li * { color:#1a1a2e !important; }
[data-baseweb="select"] { background:#ffffff !important; }
[data-baseweb="select"] > div { background:#ffffff !important; color:#1a1a2e !important; }
.sb-title { font-family:'Fraunces', Georgia, serif; font-size:1.5rem; font-weight:600; color:#0a2463; margin-bottom:2px; }
.sb-caption { font-size:11px; color:#7a86a8; margin-bottom:12px; line-height:1.4; }
.filter-stat { font-size:12px; color:#5a6688 !important; line-height:1.7; margin-bottom:14px; }
.filter-stat b { color:#0a2463 !important; font-size:13px; }
.card-desc { color:#5a6688; font-size:0.82rem; margin-top:-6px; margin-bottom:10px; }
table.mt { border-collapse:collapse; font-size:11.5px; width:auto; background:#fff; margin:2px 0 12px 0; }
table.mt th { background:#eef0f6; color:#0a2463; padding:3px 8px; text-align:right; font-weight:600; border-bottom:1px solid #dfe3ee; white-space:nowrap; }
table.mt td { padding:2px 8px; text-align:right; white-space:nowrap; border-bottom:1px solid #f0f2f8; color:#1a1a2e; }
table.mt th:first-child, table.mt td:first-child { text-align:left; font-weight:600; color:#0a2463; }
table.mt tr.sep td { border-top:1.5px solid #0a2463; }
table.mt tr.cur td { font-weight:700; }
table.mt td.dim { color:#9aa3bd; font-style:italic; }
</style>""", unsafe_allow_html=True)


# ── data ─────────────────────────────────────────────────────────────────────
@st.cache_data(ttl=3600)
def rd(name):
    return pd.read_parquet(DB / f"mars_{name}.parquet")


@st.cache_data(ttl=3600)
def get_series(comm, kind, name, period, col):
    """Observed series indexed by endDate. kind: US | State | Office."""
    if kind == "State":
        d = rd("1652")
        d = d[d["classing_State"] == name]
    else:
        d = rd("1625")
        if kind == "US" and comm == "Pima":  # no US total published for Pima - sum the offices
            d = d[(d["commodity"] == comm) & (d["period"] == period) & ~d["classing_Office"].isin(US_OFFICE)]
            return d.sort_values("published_date").drop_duplicates(["classing_Office", "endDate"], keep="last")                 .groupby("endDate")[col].sum(min_count=1).dropna().sort_index()
        d = d[d["classing_Office"].isin(US_OFFICE)] if kind == "US" else d[d["classing_Office"] == name]
    d = d[(d["commodity"] == comm) & (d["period"] == period)]
    d = d.sort_values("published_date").drop_duplicates("endDate", keep="last")
    return d.set_index("endDate")[col].dropna().sort_index()


@st.cache_data(ttl=3600)
def names(kind):
    if kind == "State":
        n = rd("1652")["classing_State"].unique()
        return sorted(x for x in n if x != "United States All Cotton")
    n = rd("1625")["classing_Office"].unique()
    return sorted(x for x in n if not x.startswith("United"))


def pick_start_month():
    """Crop year starts the month after the low-volume trough (Upland, US, daily)."""
    s = get_series("Upland", "US", "", "Daily", "numberofBales")
    share = (s.groupby(s.index.month).sum() / s.sum()).reindex(range(1, 13), fill_value=0)
    m = int(share.idxmin())
    while share[m % 12 + 1] < 0.01:
        m = m % 12 + 1
    return m % 12 + 1


START = pick_start_month()
BASE = pd.Timestamp(2019, START, 1)


def cy_of(t):
    return t.year if t.month >= START else t.year - 1


def cy_label(cy):
    return f"{cy}/{str(cy + 1)[2:]}"


def to_x(idx):
    out = []
    for t in idx:
        y = 2019 if t.month >= START else 2020
        try:
            out.append(t.replace(year=y))
        except ValueError:
            out.append(t.replace(year=y, day=28))
    return pd.DatetimeIndex(out)


def valid_cys(s):
    first, last = s.index.min(), s.index.max()
    return [c for c in range(cy_of(first), cy_of(last) + 1) if first <= pd.Timestamp(c, START, 1) + timedelta(days=45)]


def cy_slice(s, cy):
    a = pd.Timestamp(cy, START, 1)
    return s[(s.index >= a) & (s.index < pd.Timestamp(cy + 1, START, 1))]


def grid(s, cy, mode, win):
    """Daily bales for one crop year as Raw / Rolling mean / Cumulative."""
    x = cy_slice(s, cy)
    if x.empty:
        return x
    if mode == "Raw":
        return x
    a = pd.Timestamp(cy, START, 1)
    end = min(pd.Timestamp(cy + 1, START, 1) - timedelta(days=1), s.index.max())
    g = x.reindex(pd.date_range(a, end)).fillna(0)
    return g.rolling(win, min_periods=1).mean() if mode == "Rolling mean" else g.cumsum()


# ── charts ───────────────────────────────────────────────────────────────────
def band_chart(per_cy, cur, step, title, fmt=",.3s", height=340):
    prior = [c for c in per_cy if c != cur]
    fig = go.Figure()
    if prior:
        parts = []
        for c in prior:
            v = per_cy[c]
            if len(v):
                parts.append(pd.Series(v.values, index=(to_x(v.index) - BASE).days // step).groupby(level=0).last())
        if parts:
            al = pd.concat(parts, axis=1).sort_index()
            al = al[al.count(axis=1) >= min(3, len(parts))]
            bx = BASE + pd.to_timedelta(al.index * step, unit="D")
            fig.add_trace(go.Scatter(x=bx, y=al.max(axis=1), line=dict(width=0), showlegend=False, hoverinfo="skip"))
            fig.add_trace(go.Scatter(x=bx, y=al.min(axis=1), line=dict(width=0), fill="tonexty",
                                     fillcolor="rgba(138,147,168,0.22)", name="Range", hoverinfo="skip"))
            fig.add_trace(go.Scatter(x=bx, y=al.mean(axis=1), name="Avg", line=dict(color="#1a1a2e", width=1.4, dash="dash"),
                                     hovertemplate="%{y:,.2f}<extra>Avg</extra>"))
    for c, col, w in [(cur - 1, RED, 1.4), (cur, NAVY, 3)]:
        v = per_cy.get(c)
        if v is not None and len(v):
            fig.add_trace(go.Scatter(x=to_x(v.index), y=v.values, name=cy_label(c), customdata=v.index.strftime("%d-%b-%Y"),
                                     line=dict(color=col, width=w),
                                     hovertemplate="%{customdata}: %{y:,.2f}<extra>" + cy_label(c) + "</extra>"))
    fig.update_layout(template="plotly_white", height=height, margin=dict(l=8, r=8, t=40, b=8), hovermode="x unified",
                      title=dict(text=title, font=dict(size=14, color=NAVY)),
                      xaxis=dict(tickformat="%b", dtick="M1", range=[BASE, BASE + timedelta(days=364)],
                                 gridcolor="rgba(10,36,99,0.08)"),
                      yaxis=dict(tickformat=fmt, gridcolor="rgba(10,36,99,0.08)"),
                      legend=dict(orientation="h", y=-0.15, font=dict(size=10)))
    return fig


def line_layout(fig, title, height=380, fmt=None, legend_y=-0.15):
    fig.update_layout(template="plotly_white", height=height, margin=dict(l=8, r=8, t=40, b=8), hovermode="x unified",
                      title=dict(text=title, font=dict(size=14, color=NAVY)),
                      xaxis=dict(gridcolor="rgba(10,36,99,0.08)"),
                      yaxis=dict(gridcolor="rgba(10,36,99,0.08)", tickformat=fmt),
                      legend=dict(orientation="h", y=legend_y, font=dict(size=10)))
    return fig


# ── html tables ──────────────────────────────────────────────────────────────
def shade(v, lo, hi, rgb="31,157,111", top=0.5):
    if pd.isna(v) or hi <= lo:
        return ""
    return f"background:rgba({rgb},{(v - lo) / (hi - lo) * top:.2f});"


def pct_cell(v, dec=1):
    if pd.isna(v):
        return ""
    return f"<span style='color:{GREEN if v >= 0 else RED};font-weight:600'>{v:+.{dec}%}</span>"


def table_html(header, rows, row_classes=None):
    """rows: list of lists; a cell is str or (str, style) or (str, style, css_class)."""
    h = "<table class='mt'><tr>" + "".join(f"<th>{c}</th>" for c in header) + "</tr>"
    for i, r in enumerate(rows):
        h += f"<tr class='{(row_classes or {}).get(i, '')}'>"
        for c in r:
            if isinstance(c, tuple):
                txt, sty = c[0], c[1]
                cls = f" class='{c[2]}'" if len(c) > 2 else ""
                h += f"<td style='{sty}'{cls}>{txt}</td>"
            else:
                h += f"<td>{c}</td>"
        h += "</tr>"
    return h + "</table>"


def show(html):
    st.markdown(html, unsafe_allow_html=True)


def desc(t):
    st.markdown(f"<div class='card-desc'>{t}</div>", unsafe_allow_html=True)


def monthly_table(s, cys, cur, agg="sum", scale=1000.0, dec=0):
    """Crop months across, crop years down."""
    order = [(START - 1 + i) % 12 + 1 for i in range(12)]
    last = s.index.max()
    grp = {}
    for c in cys:
        x = cy_slice(s, c)
        g = x.groupby(x.index.month)
        m = g.sum() if agg == "sum" else (g.mean() if agg == "mean" else g.last())
        grp[c] = m.reindex(order) / (scale if agg == "sum" else 1)
    df = pd.DataFrame(grp).T
    done = [c for c in cys if c != cur]
    lo, hi = df.loc[done].min(), df.loc[done].max()
    hdr = ["Crop yr"] + [MONTHS[m - 1] for m in order]
    ytd_off = (last - pd.Timestamp(cur, START, 1)).days
    if agg == "sum":
        hdr += ["Total", "YoY", "YTD", "YTD YoY"]
        tot = {c: cy_slice(s, c).sum() / scale for c in cys}
        ytd = {c: s[(s.index >= pd.Timestamp(c, START, 1)) & (s.index <= pd.Timestamp(c, START, 1) + timedelta(days=ytd_off))].sum() / scale for c in cys}
    rows, cls = [], {}
    for i, c in enumerate(cys):
        r = [cy_label(c)]
        for m in order:
            v = df.loc[c, m]
            partial = c == cur and (m == last.month or pd.isna(v))
            if pd.isna(v):
                r.append("")
            elif c == cur and m == last.month:
                r.append((f"{v:,.{dec}f}", "", "dim"))
            else:
                r.append((f"{v:,.{dec}f}", shade(v, lo[m], hi[m])))
        if agg == "sum":
            p = c - 1
            r.append(f"{tot[c]:,.0f}" if c != cur else "")
            r.append(pct_cell(tot[c] / tot[p] - 1, 1) if c != cur and p in tot and tot[p] else "")
            r.append(f"{ytd[c]:,.0f}")
            r.append(pct_cell(ytd[c] / ytd[p] - 1, 1) if p in ytd and ytd[p] else "")
        if c == cur:
            cls[i] = "cur"
        rows.append(r)
    avg = df.loc[done].mean()
    ra = ["Avg"] + [f"{avg[m]:,.{dec}f}" if pd.notna(avg[m]) else "" for m in order]
    rv = ["Cur vs avg"] + [
        pct_cell(df.loc[cur, m] / avg[m] - 1, 0) if not pd.isna(df.loc[cur, m]) and avg[m] and m != last.month else ""
        for m in order]
    if agg == "sum":
        ta = sum(tot[c] for c in done) / max(len(done), 1)
        ya = sum(ytd[c] for c in done) / max(len(done), 1)
        ra += [f"{ta:,.0f}", "", f"{ya:,.0f}", ""]
        rv += ["", "", pct_cell(ytd[cur] / ya - 1, 1) if ya else "", ""]
    rows += [ra, rv]
    cls[len(cys)] = "sep"
    return table_html(hdr, rows, cls)


def ytd_val(s, cy, off):
    a = pd.Timestamp(cy, START, 1)
    return s[(s.index >= a) & (s.index <= a + timedelta(days=off))].sum()


def compare_table(kind, items, comm):
    """YTD bales vs last year and prior-4 avg per state/office."""
    us = get_series(comm, "US", "", "Daily", "numberofBales")
    if us.empty:
        return pd.DataFrame(columns=["n", "cur", "ly", "avg"]), 0, None
    cur = cy_of(us.index.max())
    off = (us.index.max() - pd.Timestamp(cur, START, 1)).days
    rows = []
    for n in items:
        s = get_series(comm, kind, n, "Daily", "numberofBales")
        if s.empty:
            continue
        c0 = ytd_val(s, cur, off)
        pr = [ytd_val(s, c, off) for c in range(cur - 4, cur) if c in valid_cys(s)]
        ly = ytd_val(s, cur - 1, off) if (cur - 1) in valid_cys(s) else float("nan")
        rows.append(dict(n=n, cur=c0, ly=ly, avg=sum(pr) / len(pr) if pr else float("nan")))
    df = pd.DataFrame(rows)
    df = df[(df[["cur", "ly", "avg"]].fillna(0) > 0).any(axis=1)].sort_values("cur", ascending=False)
    tot = df["cur"].sum()
    return df, tot, cur


def render_compare(df, tot, cur, first_col):
    if df.empty:
        st.info("No data for this selection.")
        return
    hi = df["cur"].max()
    body = []
    for _, r in df.iterrows():
        body.append([r["n"], (f"{r['cur']:,.0f}", shade(r["cur"], 0, hi, "10,36,99", 0.25)),
                     f"{r['ly']:,.0f}" if pd.notna(r["ly"]) else "", pct_cell(r["cur"] / r["ly"] - 1) if r["ly"] else "",
                     f"{r['avg']:,.0f}" if pd.notna(r["avg"]) else "", pct_cell(r["cur"] / r["avg"] - 1) if r["avg"] else "",
                     f"{r['cur'] / tot:.0%}" if tot else ""])
    t = df[["cur", "ly", "avg"]].sum()
    body.append(["Total", f"{t['cur']:,.0f}", f"{t['ly']:,.0f}", pct_cell(t["cur"] / t["ly"] - 1) if t["ly"] else "",
                 f"{t['avg']:,.0f}", pct_cell(t["cur"] / t["avg"] - 1) if t["avg"] else "", "100%"])
    show(table_html([first_col, f"{cy_label(cur)} YTD", "Last yr", "vs LY", "Prior-4 avg", "vs avg", "Share"], body,
                    {len(body) - 1: "sep cur"}))


# ── sidebar ──────────────────────────────────────────────────────────────────
us_all = {c: get_series(c, "US", "", "Daily", "numberofBales") for c in ["Upland", "Pima"]}
with st.sidebar:
    st.markdown("<div class='sb-title'>USDA MARS API</div>", unsafe_allow_html=True)
    st.markdown("<div class='sb-caption'>US cotton classing, quality, spot and forward contracting - AMS MARS.</div>",
                unsafe_allow_html=True)
    st.subheader("Filters")
    comm = st.radio("Commodity", ["Upland", "Pima"], horizontal=True)
    kind_pick = st.radio("Region", ["US", "State", "Office"], horizontal=True)
    name = ""
    if kind_pick != "US":
        opts = names(kind_pick)
        name = st.selectbox(kind_pick, opts, index=opts.index("Texas") if "Texas" in opts else 0,
                            label_visibility="collapsed")
    ser = get_series(comm, kind_pick, name, "Daily", "numberofBales")
    cys_all = valid_cys(ser) if len(ser) else []
    cur_cy = cys_all[-1] if cys_all else cy_of(pd.Timestamp.today())
    default_from = max(cys_all[0], cur_cy - 9) if cys_all else cur_cy
    from_cy = st.selectbox("From crop year", cys_all, index=cys_all.index(default_from) if cys_all else 0,
                           format_func=cy_label) if cys_all else cur_cy
    win = st.selectbox("Rolling window", [3, 7, 14, 30], index=1, format_func=lambda w: f"{w}-day avg")
    st.divider()
    u = us_all[comm]
    if len(u):
        uc = cy_of(u.index.max())
        off = (u.index.max() - pd.Timestamp(uc, START, 1)).days
        a, b = ytd_val(u, uc, off), [ytd_val(u, c, off) for c in range(uc - 4, uc) if c in valid_cys(u)]
        rows = [("Last classing day", u.index.max().strftime("%b %d, %Y"), f"{(pd.Timestamp.today() - u.index.max()).days}d old"),
                (f"{cy_label(uc)} to date", f"{a:,.0f}", "bales")]
        if b and sum(b):
            rows.append(("vs prior-4 avg", f"{a / (sum(b) / len(b)) - 1:+.1%}", ""))
        rows.append(("Crop year starts", MONTHS[START - 1], ""))
        html = "<div class='filter-stat'>" + "".join(
            f"{l}: <b>{v}</b>" + (f" <span style='color:#7a86a8;'>({s})</span>" if s else "") + "<br>" for l, v, s in rows) + "</div>"
        st.markdown(html, unsafe_allow_html=True)

cys = [c for c in cys_all if c >= from_cy]
region_label = {"US": "US", "State": name, "Office": name}[kind_pick]

t_class, t_qual, t_spot, t_fwd = st.tabs(["Classing", "Quality", "Spot & Basis", "Forward Contracting"])

# ── classing ─────────────────────────────────────────────────────────────────
with t_class:
    s_pace, s_state, s_office, s_pulse = st.tabs(["Season Pace", "By State", "By Office", "Daily Pulse"])
    with s_pace:
        if ser.empty or not cys:
            st.info("No classing data for this selection.")
        else:
            desc(f"{comm} bales classed, {region_label}. Crop year starts {MONTHS[START - 1]}. Navy = {cy_label(cur_cy)}, red = last year.")
            c1, c2, c3 = st.columns(3)
            for col, mode, ttl, step in [(c1, "Raw", "Daily bales", 1), (c2, "Rolling mean", f"{win}-day average", 1),
                                         (c3, "Cumulative", "Cumulative", 1)]:
                per = {c: grid(ser, c, mode, win) for c in cys}
                col.plotly_chart(band_chart(per, cys[-1], step, ttl), width="stretch")
            desc("Monthly bales, '000. Shade = rank within month. Italic = month in progress.")
            show(monthly_table(ser, cys, cys[-1]))
    with s_state:
        desc(f"{comm} bales classed {cy_label(cur_cy)} to date vs the same date in prior years.")
        df, tot, cur = compare_table("State", names("State"), comm)
        render_compare(df, tot, cur, "State")
    with s_office:
        desc(f"{comm} bales classed {cy_label(cur_cy)} to date vs the same date in prior years.")
        df, tot, cur = compare_table("Office", names("Office"), comm)
        render_compare(df, tot, cur, "Office")
    with s_pulse:
        if ser.empty:
            st.info("No data.")
        else:
            desc(f"Last 12 classing days, {region_label}.")
            cur = cy_of(ser.index.max())
            g = grid(ser, cur, "Rolling mean", win)
            cum = grid(ser, cur, "Cumulative", win)
            last12 = ser[ser.index >= pd.Timestamp(cur, START, 1)].tail(12)
            body = []
            for d, v in last12.iloc[::-1].items():
                off = (d - pd.Timestamp(cur, START, 1)).days
                ly = ytd_val(ser, cur - 1, off)
                pr = [ytd_val(ser, c, off) for c in range(cur - 4, cur) if c in valid_cys(ser)]
                av = sum(pr) / len(pr) if pr else float("nan")
                body.append([d.strftime("%a %d-%b"), f"{v:,.0f}", f"{g.get(d, float('nan')):,.0f}", f"{cum.get(d, float('nan')):,.0f}",
                             pct_cell(cum.get(d) / ly - 1) if ly else "", pct_cell(cum.get(d) / av - 1) if av else ""])
            show(table_html(["Date", "Bales", f"{win}d avg", "Season to date", "vs LY", "vs prior-4 avg"], body))
            tail = ser[ser.index >= ser.index.max() - timedelta(days=60)]
            fig = go.Figure(go.Bar(x=tail.index, y=tail.values, marker_color=NAVY, name="Bales"))
            gg = g[g.index >= tail.index.min()]
            fig.add_trace(go.Scatter(x=gg.index, y=gg.values, name=f"{win}d avg", line=dict(color=RED, width=2)))
            st.plotly_chart(line_layout(fig, "Last 60 days", 300, ",.3s"), width="stretch")

# ── quality ──────────────────────────────────────────────────────────────────
QMETRICS = {"Micronaire": "avgMike", "Staple": "avgStaple", "Strength": "avgStrength", "Length": "avgLength",
            "Uniformity": "avgUniformity", "Leaf": "avgLeaf", "Trash": "avgTrash", "Loan premium": "avgLoanPD"}
with t_qual:
    q_fiber, q_color, q_tender = st.tabs(["Fiber Quality", "Colour & Leaf", "Tenderable %"])
    with q_fiber:
        qm = st.radio("Metric", list(QMETRICS), horizontal=True, label_visibility="collapsed")
        qs = get_series(comm, kind_pick, name, "Weekly", QMETRICS[qm])
        qc = [c for c in (valid_cys(qs) if len(qs) else []) if c >= from_cy]
        if not qc:
            st.info("No data for this selection.")
        else:
            desc(f"Weekly average {qm.lower()}, {region_label}. Navy = {cy_label(qc[-1])}, red = last year.")
            per = {c: cy_slice(qs, c) for c in qc}
            c1, c2 = st.columns([3, 2])
            c1.plotly_chart(band_chart(per, qc[-1], 7, qm, ",.2f", 360), width="stretch")
            with c2:
                desc("Monthly average. Shade = rank within month.")
                show(monthly_table(qs, qc, qc[-1], agg="mean", dec=2))
    with q_color:
        cl = rd("1654_colorleaf")
        cl = cl[cl["commodity"] == comm]
        states = sorted(cl["gin_State"].unique(), key=lambda x: (not x.lower().startswith("united"), x))
        c1, c2 = st.columns([2, 1])
        stt = c1.selectbox("State", states, index=states.index("Texas") if "Texas" in states else 0, key="cl_state",
                           label_visibility="collapsed")
        which = c2.radio("Basis", ["Season", "Week"], horizontal=True, key="cl_basis", label_visibility="collapsed")
        val = "season_Percent" if which == "Season" else "week_Percent"
        x = cl[(cl["gin_State"] == stt)].dropna(subset=[val])
        leafs = ["1", "2", "3", "4", "5", "6", "7"]
        x = x[x["leaf_Grade"].isin(leafs) & (x["color_Grade"] != "All Colors")]
        if x.empty:
            st.info("No data for this selection.")
        else:
            dts = sorted(x["report_end_date"].unique())
            last = dts[-1]
            ly = min(dts, key=lambda d: abs((pd.Timestamp(d) - (pd.Timestamp(last) - timedelta(days=364))).days))
            desc(f"{stt}, {which.lower()} % by colour and leaf, report of {pd.Timestamp(last):%d-%b-%Y} (shade = share of bales).")
            p = x[x["report_end_date"] == last].pivot_table(index="color_Grade", columns="leaf_Grade", values=val, aggfunc="last")
            p = p.reindex(columns=[c for c in leafs if c in p.columns]).dropna(how="all")
            hi = p.max().max()
            rows = [[g] + [(f"{v:.1f}" if pd.notna(v) else "", shade(v, 0, hi, "10,36,99", 0.55)) for v in p.loc[g]] for g in p.index]
            c1, c2 = st.columns([1, 1])
            with c1:
                show(table_html(["Colour"] + [f"Leaf {c}" for c in p.columns], rows))
            colr = x[x["report_end_date"] == last].groupby("color_Grade")[val].sum()
            colr_ly = x[x["report_end_date"] == ly].groupby("color_Grade")[val].sum()
            both = pd.concat([colr, colr_ly], axis=1, keys=["cur", "ly"]).fillna(0)
            both = both[(both["cur"] > 0.4) | (both["ly"] > 0.4)]
            fig = go.Figure([go.Bar(x=both.index, y=both["ly"], name=f"{pd.Timestamp(ly):%b %Y}", marker_color=RED),
                             go.Bar(x=both.index, y=both["cur"], name=f"{pd.Timestamp(last):%b %Y}", marker_color=NAVY)])
            fig.update_layout(barmode="group")
            c2.plotly_chart(line_layout(fig, "Colour share, %", 330), width="stretch")
    with q_tender:
        sm = rd("1654_summary")
        sm = sm[sm["commodity"] == comm]
        states = sorted(sm["gin_State"].unique(), key=lambda x: (not x.lower().startswith("united"), x))
        c1, c2, c3 = st.columns([2, 1, 1])
        stt = c1.selectbox("State", states, key="tn_state", label_visibility="collapsed")
        per_ = c2.radio("Period", ["Season", "week"], horizontal=True, key="tn_per", format_func=str.title, label_visibility="collapsed")
        mm = c3.radio("Measure", ["Tenderable", "Eligible"], horizontal=True, key="tn_m", label_visibility="collapsed")
        col = "tenderable_Percent" if mm == "Tenderable" else "eligible_Percent"
        x = sm[(sm["gin_State"] == stt) & (sm["report_Period"] == per_)].dropna(subset=[col])
        x = x.sort_values("published_date").drop_duplicates("report_end_date", keep="last").set_index("report_end_date")[col].sort_index()
        xc = [c for c in (valid_cys(x) if len(x) else []) if c >= from_cy]
        if not xc:
            st.info("No data for this selection.")
        else:
            desc(f"{mm} % of bales, {stt}, {per_.lower()} basis. Navy = {cy_label(xc[-1])}, red = last year.")
            c1, c2 = st.columns([3, 2])
            c1.plotly_chart(band_chart({c: cy_slice(x, c) for c in xc}, xc[-1], 7, f"{mm} %", ",.1f", 360), width="stretch")
            with c2:
                desc("Monthly last value. Shade = rank within month.")
                show(monthly_table(x, xc, xc[-1], agg="last", dec=1))

# ── spot & basis ─────────────────────────────────────────────────────────────
with t_spot:
    sp_basis, sp_bales, sp_curve, sp_month = st.tabs(["Basis by Market", "Bales Reported", "CT Futures Curve", "Monthly Average"])
    bs = rd("3804_basis")
    bs = bs[bs["commodity"] == comm]
    with sp_basis:
        mk = sorted(bs["spotMarket"].unique(), key=lambda x: (x != "US Average", x))
        c1, c2, c3 = st.columns([2, 1, 1])
        sel = c1.multiselect("Markets", mk, default=mk[:1], label_visibility="collapsed")
        grade = c2.radio("Grade", ["41-4-34", "31-3-36"], horizontal=True, label_visibility="collapsed")
        kindv = c3.radio("Show", ["Basis", "Base price"], horizontal=True, label_visibility="collapsed")
        rng = st.radio("Range", ["3M", "6M", "12M", "All"], index=2, horizontal=True, label_visibility="collapsed")
        col = {("41-4-34", "Basis"): "basis_41_4_34", ("31-3-36", "Basis"): "basis_31_3_36",
               ("41-4-34", "Base price"): "41_4_34_Base_Price", ("31-3-36", "Base price"): "31_3_36_Base_Price"}[(grade, kindv)]
        if bs.empty or not sel:
            st.info("No data for this selection.")
        else:
            last = bs["report_Begin_Date"].max()
            lo = last - timedelta(days={"3M": 91, "6M": 182, "12M": 365, "All": 9999}[rng])
            fig = go.Figure()
            for i, m in enumerate(sel):
                y = bs[(bs["spotMarket"] == m) & (bs["report_Begin_Date"] >= lo)].dropna(subset=[col])
                fig.add_trace(go.Scatter(x=y["report_Begin_Date"], y=y[col], name=m,
                                         line=dict(color=[NAVY, RED, TEAL, AMBER, GREEN, GREY, "#6b4fa0", "#333"][i % 8], width=2)))
            st.plotly_chart(line_layout(fig, f"{grade} {kindv.lower()} ({'points off ICE' if kindv == 'Basis' else 'cents/lb'})", 360),
                            width="stretch")
            desc(f"Latest by market, {last:%d-%b-%Y}.")
            rows = []
            for m in mk:
                y = bs[bs["spotMarket"] == m].dropna(subset=[col]).set_index("report_Begin_Date")[col]
                if y.empty:
                    continue
                prev = lambda n: y[y.index <= y.index.max() - timedelta(days=n)]
                w, mo = prev(7), prev(30)
                bm = bs[(bs["spotMarket"] == m)].sort_values("report_Begin_Date")["basis_Month"].dropna()
                rows.append([m, f"{y.iloc[-1]:,.2f}" if kindv == "Base price" else f"{y.iloc[-1]:,.0f}",
                             f"{y.iloc[-1] - w.iloc[-1]:+,.2f}" if len(w) else "", f"{y.iloc[-1] - mo.iloc[-1]:+,.2f}" if len(mo) else "",
                             bm.iloc[-1] if len(bm) else ""])
            show(table_html(["Market", "Latest", "1w chg", "1m chg", "vs futures"], rows))
    with sp_bales:
        mk = [m for m in sorted(bs["spotMarket"].unique()) if m != "US Average"]
        tot = bs[bs["spotMarket"] == "US Average"].set_index("report_Begin_Date")["bales_Reported"].sort_index()
        if tot.empty:
            st.info("No data.")
        else:
            desc("Spot bales reported per day, by market. Line = 5-day average of US total.")
            last = tot.index.max()
            y = bs[(bs["spotMarket"] != "US Average") & (bs["report_Begin_Date"] >= last - timedelta(days=120))]
            fig = go.Figure()
            pal = [NAVY, TEAL, AMBER, GREEN, RED, GREY, "#6b4fa0", "#8fa3d1"]
            for i, m in enumerate(mk):
                z = y[y["spotMarket"] == m]
                fig.add_trace(go.Bar(x=z["report_Begin_Date"], y=z["bales_Reported"], name=m, marker_color=pal[i % 8]))
            t5 = tot.rolling(5, min_periods=1).mean()
            t5 = t5[t5.index >= last - timedelta(days=120)]
            fig.add_trace(go.Scatter(x=t5.index, y=t5.values, name="US 5d avg", line=dict(color="#1a1a2e", width=2)))
            fig.update_layout(barmode="stack")
            st.plotly_chart(line_layout(fig, "Last 120 days", 380, ",.3s", legend_y=-0.3), width="stretch")
            desc("Monthly bales by market. Shade = rank within month.")
            z = bs[bs["spotMarket"] != "US Average"].copy()
            z["m"] = z["report_Begin_Date"].dt.to_period("M")
            pv = z.pivot_table(index="spotMarket", columns="m", values="bales_Reported", aggfunc="sum").iloc[:, -9:]
            hdr = ["Market"] + [str(c.strftime("%b-%y")) for c in pv.columns]
            body = [[m] + [(f"{v:,.0f}", shade(v, pv[c].min(), pv[c].max())) if pd.notna(v) else "" for c, v in pv.loc[m].items()]
                    for m in pv.index]
            show(table_html(hdr, body))
    with sp_curve:
        fu = rd("3804_futures")
        fu = fu.copy()
        fu["m"] = pd.to_datetime(fu["contract"], format="%b-%y", errors="coerce")
        dts = sorted(fu["report_Begin_Date"].unique())
        if not dts:
            st.info("No data.")
        else:
            last = dts[-1]
            pick = {f"{pd.Timestamp(last):%d-%b-%Y}": last}
            for lab, n in [("1 week ago", 7), ("1 month ago", 30), ("3 months ago", 91)]:
                d = [x for x in dts if pd.Timestamp(x) <= pd.Timestamp(last) - timedelta(days=n)]
                if d:
                    pick[lab] = d[-1]
            desc("ICE CT settlements by contract month, cents/lb.")
            fig = go.Figure()
            for (lab, d), col in zip(pick.items(), [NAVY, RED, TEAL, GREY]):
                z = fu[fu["report_Begin_Date"] == d].sort_values("m")
                fig.add_trace(go.Scatter(x=z["m"], y=z["settlement_Price"], name=lab, mode="lines+markers",
                                         line=dict(color=col, width=3 if lab == list(pick)[0] else 1.5)))
            fig.update_xaxes(tickformat="%b-%y")
            st.plotly_chart(line_layout(fig, "Futures curve", 340), width="stretch")
            z0 = fu[fu["report_Begin_Date"] == last].sort_values("m").set_index("contract")["settlement_Price"]
            d1 = pick.get("1 week ago")
            z1 = fu[fu["report_Begin_Date"] == d1].set_index("contract")["settlement_Price"] if d1 is not None else pd.Series(dtype=float)
            show(table_html(["Contract", "Settle", "1w chg"],
                            [[c, f"{v:.2f}", f"{v - z1[c]:+.2f}" if c in z1.index else ""] for c, v in z0.items()]))
    with sp_month:
        mo = rd("3895_monthly")
        mo = mo.dropna(subset=["monthly_Average_41_4_34"])
        if mo.empty:
            st.info("No data.")
        else:
            desc("Monthly average spot, 41-4-34, cents/lb. Shade = rank within month.")
            mo["m"] = mo["report_Begin_Date"].dt.to_period("M")
            pv = mo.pivot_table(index="market", columns="m", values="monthly_Average_41_4_34", aggfunc="last")
            pv = pv.reindex(sorted(pv.index, key=lambda x: (not x.startswith("Total"), x)))
            hdr = ["Market"] + [c.strftime("%b-%y") for c in pv.columns]
            body = [[m] + [(f"{v:.2f}", shade(v, pv[c].min(), pv[c].max())) if pd.notna(v) else "" for c, v in pv.loc[m].items()]
                    for m in pv.index]
            show(table_html(hdr, body))
            t = mo[mo["market"].str.startswith("Total US Upland")].sort_values("report_Begin_Date")
            if not t.empty:
                desc("US Upland: monthly average vs CCC loan value, and bales reported.")
                body = [[r["report_Begin_Date"].strftime("%b-%y"), f"{r['monthly_Average_41_4_34']:.2f}",
                         f"{r['cCC_Loan_Average_Value']:.2f}" if pd.notna(r["cCC_Loan_Average_Value"]) else "",
                         f"{r['monthly_High_41_4_34']:.2f}", f"{r['monthly_Low_41_4_34']:.2f}",
                         f"{r['bales_Reported_Current_Month']:,.0f}"] for _, r in t.iloc[::-1].iterrows()]
                show(table_html(["Month", "Avg", "CCC loan", "High", "Low", "Bales"], body))

# ── forward contracting ──────────────────────────────────────────────────────
with t_fwd:
    fc = rd("1613")
    fc = fc[fc["commodity"] == comm]
    if fc.empty:
        st.info("No data for this commodity.")
    else:
        months = sorted(fc["report_begin_date"].unique(), reverse=True)
        c1, c2 = st.columns([1, 2])
        rm = c1.selectbox("Report", months, format_func=lambda d: pd.Timestamp(d).strftime("%b %Y"), label_visibility="collapsed")
        z = fc[fc["report_begin_date"] == rm].copy()
        z["state"] = z["market_location_name"].str.replace(r" /\d", "", regex=True)
        ry = pd.Timestamp(rm).year
        pc = ["pct_acres_planted"] + [f"pct_acres_planted_prior_{n}yr" for n in range(1, 10)]
        desc(f"Share of planted acres forward contracted, as of {pd.Timestamp(rm):%b %Y}. Shade = rank within year.")
        order = sorted(z["state"].unique(), key=lambda x: (x != "United States", -z.loc[z["state"] == x, "nass_acres_planted_total"].max()))
        zz = z.set_index("state")
        body = []
        for stn in order:
            r = zz.loc[stn]
            body.append([stn, f"{r['nass_acres_planted_total'] / 1000:,.0f}"] +
                        [(f"{r[c]:.0f}", shade(r[c], 0, 100, "10,36,99", 0.45)) if pd.notna(r[c]) else "" for c in pc])
        show(table_html(["State", "Acres '000"] + [str(ry - n) for n in range(10)], body, {0: "cur"} if order and order[0] == "United States" else None))
        pick = c2.selectbox("State", order, label_visibility="collapsed")
        r = zz.loc[pick]
        vals = [r[c] for c in pc][::-1]
        yrs = [str(ry - n) for n in range(10)][::-1]
        fig = go.Figure(go.Bar(x=yrs, y=vals, marker_color=[GREY] * 9 + [NAVY], text=[f"{v:.0f}" if pd.notna(v) else "" for v in vals],
                               textposition="outside"))
        st.plotly_chart(line_layout(fig, f"{pick}: % contracted, {pd.Timestamp(rm):%b}", 300), width="stretch")
