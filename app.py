import io
import re
from datetime import datetime, timezone

import numpy as np
import pandas as pd
import plotly.express as px
import requests
import streamlit as st

# ---------------------------------------------------------------------
# International Cost of Capital | source data + calculations
# ---------------------------------------------------------------------
st.set_page_config(page_title="Global Cost of Capital", page_icon="◈", layout="wide")

BETAS_URL = "https://pages.stern.nyu.edu/~adamodar/pc/datasets/betas.xls"
BETAS_HTML = "https://pages.stern.nyu.edu/~adamodar/New_Home_Page/datafile/Betas.html"
RATINGS_URL = "https://pages.stern.nyu.edu/~adamodar/New_Home_Page/datafile/ratings.html"
OECD_URL = ("https://www.oecd.org/en/publications/corporate-tax-statistics-2024_"
            "9c27d6e8-en/full-report/statutory-corporate-income-tax-rates_440f9286.html")
TE_URL = "https://tradingeconomics.com/country-list/government-bond-10y"

COUNTRY_CURRENCY = {
    "United States": "USD", "Colombia": "COP", "Canada": "CAD",
    "United Kingdom": "GBP", "Euro area": "EUR", "Germany": "EUR",
    "France": "EUR", "Japan": "JPY", "Australia": "AUD", "Brazil": "BRL",
    "Chile": "CLP", "Mexico": "MXN", "India": "INR", "China": "CNY",
    "South Korea": "KRW", "Switzerland": "CHF", "Sweden": "SEK",
    "Norway": "NOK", "New Zealand": "NZD", "South Africa": "ZAR",
    "Singapore": "SGD", "Indonesia": "IDR", "Thailand": "THB",
    "Turkey": "TRY", "Poland": "PLN", "Israel": "ILS",
}
# These are the 2024 OECD combined central/sub-central statutory rates
# used only as an offline fallback for the two assignment starter countries.
# The user can override any rate; live OECD parsing is attempted first.
OECD_2024_FALLBACK = {"United States": 25.77, "Colombia": 35.00}

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; CostOfCapitalStudentApp/1.0)"}

@st.cache_data(ttl=24 * 60 * 60, show_spinner=False)
def get_beta_data():
    try:
        r = requests.get(BETAS_URL, headers=HEADERS, timeout=25)
        r.raise_for_status()
        df = pd.read_excel(io.BytesIO(r.content), sheet_name=0, engine="xlrd")
        df.columns = [str(c).strip() for c in df.columns]
        industry_col = next(c for c in df.columns if "industry" in c.lower())
        ub_col = next(c for c in df.columns if "unlevered beta" in c.lower() and "corrected" not in c.lower())
        result = df[[industry_col, ub_col]].copy()
        result.columns = ["Industry", "Unlevered beta"]
        result["Industry"] = result["Industry"].astype(str).str.strip()
        result["Unlevered beta"] = pd.to_numeric(result["Unlevered beta"], errors="coerce")
        result = result.dropna().query("`Unlevered beta` > 0")
        if len(result) > 10:
            return result.sort_values("Industry"), "Damodaran Excel download"
    except Exception:
        pass
    try:
        tables = pd.read_html(BETAS_HTML)
        for df in tables:
            cols = [str(c).lower() for c in df.columns]
            if any("industry" in c for c in cols) and any("unlevered beta" in c for c in cols):
                industry_col = next(c for c in df.columns if "industry" in str(c).lower())
                ub_col = next(c for c in df.columns if "unlevered beta" in str(c).lower() and "corrected" not in str(c).lower())
                out = df[[industry_col, ub_col]].copy()
                out.columns = ["Industry", "Unlevered beta"]
                out["Unlevered beta"] = pd.to_numeric(out["Unlevered beta"], errors="coerce")
                return out.dropna().sort_values("Industry"), "Damodaran sector webpage"
    except Exception:
        pass
    # Minimal transparent offline fallback; live source refresh remains available.
    return pd.DataFrame([
        ("Software (System & Application)", 0.91),
        ("Computer Services", 0.92),
        ("Healthcare Products", 0.83),
        ("Retail (General)", 0.69),
        ("Auto & Truck", 1.27),
        ("Food Processing", 0.46),
    ], columns=["Industry", "Unlevered beta"]), "Offline starter set — refresh source data"

@st.cache_data(ttl=24 * 60 * 60, show_spinner=False)
def get_us_bbb_spread():
    try:
        tables = pd.read_html(RATINGS_URL)
        for df in tables:
            text = df.astype(str).to_string().lower()
            if "baa2" in text and "bbb" in text:
                for _, row in df.iterrows():
                    row_text = " ".join(str(x) for x in row.values)
                    if re.search(r"Baa2\s*/\s*BBB", row_text, re.I):
                        vals = re.findall(r"(\d+(?:\.\d+)?)\s*%", row_text)
                        if vals:
                            return float(vals[0]), "Damodaran ratings table"
    except Exception:
        pass
    return 1.11, "Damodaran January 2026 published Baa2/BBB spread (fallback)"

@st.cache_data(ttl=24 * 60 * 60, show_spinner=False)
def get_bond_yields():
    try:
        tables = pd.read_html(TE_URL)
        for df in tables:
            cols = [str(c).strip().lower() for c in df.columns]
            if len(df.columns) >= 3:
                # Trading Economics' country table generally has Country, Last, Previous...
                country_col = next((c for c in df.columns if "country" in str(c).lower()), df.columns[0])
                last_col = next((c for c in df.columns if str(c).strip().lower() == "last"), df.columns[1])
                out = df[[country_col, last_col]].copy()
                out.columns = ["Country", "Yield (%)"]
                out["Country"] = out["Country"].astype(str).str.strip()
                out["Yield (%)"] = pd.to_numeric(out["Yield (%)"].astype(str).str.replace(",", ""), errors="coerce")
                out = out.dropna()
                if len(out) > 10 and "United States" in set(out["Country"]):
                    return dict(zip(out["Country"], out["Yield (%)"])), "Trading Economics 10Y government bond table"
    except Exception:
        pass
    return {"United States": 4.00, "Colombia": 12.00}, "Illustrative fallback values — manually verify before use"

@st.cache_data(ttl=24 * 60 * 60, show_spinner=False)
def get_oecd_tax_rates():
    # Try OECD's 2024 statutory-rate report tables. Layout can change; never
    # silently treat an unparsed table as a live observation.
    try:
        tables = pd.read_html(OECD_URL)
        rates = {}
        for df in tables:
            for _, row in df.iterrows():
                vals = [str(v).strip() for v in row.values]
                joined = " ".join(vals)
                country = next((c for c in COUNTRY_CURRENCY if re.search(rf"\b{re.escape(c)}\b", joined, re.I)), None)
                nums = re.findall(r"(?<!\w)(\d{1,2}(?:\.\d+)?)\s*%?", joined)
                if country and nums:
                    candidate = float(nums[-1])
                    if 0 <= candidate <= 60:
                        rates[country] = candidate
        if len(rates) >= 10:
            return rates, "OECD Corporate Tax Statistics 2024"
    except Exception:
        pass
    return OECD_2024_FALLBACK.copy(), "OECD 2024 report fallback for U.S./Colombia only"

from model import calculate_cost_of_capital

# Styling
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&family=Manrope:wght@400;500;600;700;800&display=swap');
html, body, [class*="css"] {font-family:'Manrope',sans-serif;}
.stApp {background:linear-gradient(135deg,#f4f7fb 0%,#edf2f7 100%);}
.block-container {padding-top:1.5rem;max-width:1500px;}
.hero {background:#10243a;color:white;padding:26px 30px;border-radius:18px;margin-bottom:18px;
       border:1px solid #29435d;box-shadow:0 12px 30px rgba(16,36,58,.12);}
.hero-kicker {color:#8dd4c6;font-size:11px;letter-spacing:2px;font-weight:800;text-transform:uppercase;}
.hero h1 {font-size:30px;line-height:1.15;margin:8px 0 6px;color:white;}
.hero p {color:#c4d1df;margin:0;font-size:14px;}
.metric-card {background:white;border:1px solid #dce5ed;border-radius:16px;padding:18px 20px;min-height:130px;}
.metric-label {color:#607286;font-size:11px;font-weight:800;letter-spacing:1.1px;text-transform:uppercase;}
.metric-value {font-size:34px;font-weight:800;color:#10243a;margin:7px 0 2px;font-family:'DM Mono',monospace;}
.metric-sub {font-size:12px;color:#718096;}
.section-label {font-size:12px;font-weight:800;letter-spacing:1.3px;color:#466078;text-transform:uppercase;margin:12px 0 7px;}
.small-note {font-size:12px;color:#66788a;}
div[data-testid="stMetric"] {background:white;border:1px solid #dce5ed;padding:16px;border-radius:14px;}
div[data-testid="stMetricLabel"] p {font-size:11px;text-transform:uppercase;letter-spacing:1px;}
</style>
""", unsafe_allow_html=True)

st.markdown("""
<div class="hero">
  <div class="hero-kicker">Capital allocation · cross-border valuation</div>
  <h1>Global Cost of Capital</h1>
  <p>Translate operating risk and financing assumptions into comparable discount rates across currencies.</p>
</div>
""", unsafe_allow_html=True)

beta_df, beta_source = get_beta_data()
spread_default, spread_source = get_us_bbb_spread()
bond_yields, bond_source = get_bond_yields()
tax_rates, tax_source = get_oecd_tax_rates()

with st.sidebar:
    st.markdown("## Model inputs")
    st.caption("Change assumptions; outputs recalculate instantly.")
    industry_list = beta_df["Industry"].dropna().astype(str).tolist()
    default_industry = next((x for x in industry_list if "Software (System" in x), industry_list[0])
    industry = st.selectbox("Industry benchmark", industry_list,
                            index=industry_list.index(default_industry))
    selected_beta = float(beta_df.loc[beta_df["Industry"] == industry, "Unlevered beta"].iloc[0])
    beta = st.number_input("Unlevered beta override", min_value=0.01, max_value=5.0,
                           value=float(selected_beta), step=0.01, format="%.2f")
    st.divider()
    countries = sorted(set(list(COUNTRY_CURRENCY) + list(bond_yields) + list(tax_rates)))
    countries = [c for c in countries if c != "United States"]
    country = st.selectbox("Project country", countries,
                           index=(countries.index("Colombia") if "Colombia" in countries else 0))
    currency = COUNTRY_CURRENCY.get(country, "Local currency")
    erp_pct = st.number_input("Equity risk premium (%)", 0.0, 30.0, 6.5, 0.1)
    debt_pct = st.slider("Debt / total capital (%)", 0, 90, 30, 1)
    tax_choice = st.radio("Tax rate applied to both currencies", ["U.S. tax rate", "Project-country tax rate"])
    tax_country = "United States" if tax_choice == "U.S. tax rate" else country
    default_tax = float(tax_rates.get(tax_country, OECD_2024_FALLBACK.get(tax_country, 25.77)))
    tax_pct = st.number_input(f"{tax_country} statutory tax rate (%)", 0.0, 60.0,
                              float(default_tax), 0.1)
    st.divider()
    st.markdown("### Manual market overrides")
    us_yield_default = float(bond_yields.get("United States", 4.0))
    foreign_yield_default = float(bond_yields.get(country, 12.0))
    us_yield_pct = st.number_input("U.S. 10Y government yield (%)", 0.0, 40.0, us_yield_default, 0.01)
    foreign_yield_pct = st.number_input(f"{country} 10Y government yield (%)", 0.0, 60.0,
                                        foreign_yield_default, 0.01)
    us_spread_pct = st.number_input("U.S. BBB / Baa2 spread (%)", 0.0, 30.0,
                                    float(spread_default), 0.01)
    use_foreign_override = st.checkbox("Override foreign BBB spread")
    foreign_spread_pct = None
    if use_foreign_override:
        foreign_spread_pct = st.number_input("Foreign BBB spread (%)", 0.0, 40.0, float(us_spread_pct), 0.01)
    st.caption("Rates are entered as percentage points (e.g., 6.5 means 6.5%).")

# Calculation inputs converted to decimal
tax = tax_pct / 100
erp = erp_pct / 100
debt_weight = debt_pct / 100
us_rf = us_yield_pct / 100
foreign_rf = foreign_yield_pct / 100
us_spread = us_spread_pct / 100
foreign_override = None if foreign_spread_pct is None else foreign_spread_pct / 100

try:
    result = calculate_cost_of_capital(beta, debt_weight, tax, erp, us_rf, foreign_rf,
                                       us_spread, foreign_override)
except ValueError as exc:
    st.error(str(exc))
    st.stop()

st.markdown('<div class="section-label">01 / Project return requirements</div>', unsafe_allow_html=True)
c1, c2, c3, c4 = st.columns([1.05, 1.05, 1, 1])
with c1:
    st.markdown(f"""<div class="metric-card"><div class="metric-label">USD WACC</div>
    <div class="metric-value">{result['USD WACC']:.2%}</div>
    <div class="metric-sub">Dollar-denominated discount rate</div></div>""", unsafe_allow_html=True)
with c2:
    st.markdown(f"""<div class="metric-card"><div class="metric-label">{currency} WACC</div>
    <div class="metric-value">{result['Foreign WACC']:.2%}</div>
    <div class="metric-sub">{country} currency discount rate</div></div>""", unsafe_allow_html=True)
with c3:
    st.markdown(f"""<div class="metric-card"><div class="metric-label">Levered beta</div>
    <div class="metric-value">{result['Levered beta']:.2f}</div>
    <div class="metric-sub">Relevered to target capital structure</div></div>""", unsafe_allow_html=True)
with c4:
    st.markdown(f"""<div class="metric-card"><div class="metric-label">FX gross-rate factor</div>
    <div class="metric-value">{result['FX conversion factor']:.3f}x</div>
    <div class="metric-sub">(1 + foreign yield) / (1 + U.S. yield)</div></div>""", unsafe_allow_html=True)

st.markdown('<div class="section-label">02 / Cost of capital build-up</div>', unsafe_allow_html=True)
left, right = st.columns(2)
def pct(v): return f"{v:.2%}"
with left:
    st.markdown("#### USD-denominated project")
    usd_rows = [
        ("Risk-free rate", us_rf), ("Levered beta", result["Levered beta"]),
        ("Equity risk premium", erp), ("Cost of equity", result["USD cost of equity"]),
        ("BBB / Baa2 credit spread", us_spread), ("Pretax cost of debt", result["USD pretax cost of debt"]),
        ("After-tax cost of debt", result["USD after-tax cost of debt"]), ("WACC", result["USD WACC"])
    ]
    st.dataframe(pd.DataFrame(usd_rows, columns=["Component", "Value"]).assign(
        Value=lambda x: x["Value"].map(lambda z: f"{z:.2%}" if isinstance(z, float) and z < 1 else f"{z:.2f}" if isinstance(z, float) else z)
    ), hide_index=True, use_container_width=True)
with right:
    st.markdown(f"#### {currency}-denominated project")
    foreign_rows = [
        ("Risk-free rate", foreign_rf), ("Levered beta", result["Levered beta"]),
        ("Converted equity cost", result["Foreign cost of equity"]),
        ("Foreign BBB spread", result["Foreign BBB spread"]),
        ("Pretax cost of debt", result["Foreign pretax cost of debt"]),
        ("After-tax cost of debt", result["Foreign after-tax cost of debt"]),
        ("WACC", result["Foreign WACC"])
    ]
    st.dataframe(pd.DataFrame(foreign_rows, columns=["Component", "Value"]).assign(
        Value=lambda x: x["Value"].map(lambda z: f"{z:.2%}" if isinstance(z, float) and z < 1 else f"{z:.2f}" if isinstance(z, float) else z)
    ), hide_index=True, use_container_width=True)

st.markdown('<div class="section-label">03 / Capital structure contribution</div>', unsafe_allow_html=True)
contrib = pd.DataFrame({
    "Currency": ["USD", currency],
    "Equity contribution": [(1-debt_weight)*result["USD cost of equity"],
                            (1-debt_weight)*result["Foreign cost of equity"]],
    "After-tax debt contribution": [debt_weight*result["USD after-tax cost of debt"],
                                    debt_weight*result["Foreign after-tax cost of debt"]]
})
fig = px.bar(contrib, x="Currency", y=["Equity contribution", "After-tax debt contribution"],
             barmode="stack", title="WACC contribution by financing source",
             labels={"value": "Contribution to WACC", "variable": "Capital source"},
             color_discrete_sequence=["#0866c2", "#81c6fa"])

# Percentage labels inside each contribution segment.
fig.update_traces(texttemplate="%{y:.2%}", textposition="inside",
                  insidetextanchor="middle", textfont=dict(size=15), cliponaxis=False)
for trace in fig.data:
    trace.textfont.color = "white" if trace.name == "Equity contribution" else "#17334d"

# Total WACC above each stacked bar.
for _, item in contrib.iterrows():
    total = item["Equity contribution"] + item["After-tax debt contribution"]
    fig.add_annotation(x=item["Currency"], y=total,
                       text=f"<b>Total WACC: {total:.2%}</b>",
                       showarrow=False, yshift=16,
                       font=dict(size=14, color="#10243a"))

fig.update_yaxes(tickformat=".0%", title_text="Contribution to WACC (%)", rangemode="tozero")
fig.update_layout(template="plotly_white", legend_title="",
                  margin=dict(l=10, r=10, t=70, b=10),
                  uniformtext_minsize=11, uniformtext_mode="hide")
st.plotly_chart(fig, use_container_width=True)

with st.expander("Model assumptions and formulae"):
    st.markdown(r"""
    **Unlevered beta to project beta**

    \(\beta_E=\beta_U\left[1+(1-\tau)\frac{d}{1-d}\right]\)

    **USD cost of equity and debt**

    \(R_E=R_f+\beta_E ERP\)  
    \(R_D=R_f+s\)

    **Foreign-currency conversion**

    \(1+R_E^*=(1+R_E)\frac{1+R_f^*}{1+R_f}\)  
    \(s^*=s\frac{1+R_f^*}{1+R_f}\), unless a manual foreign spread is entered.

    **WACC**

    \(WACC=(1-d)R_E+dR_D(1-\tau)\)

    The selected statutory tax rate, ERP, target debt share and levered beta are held constant across both currency calculations. Government bond yields are used as risk-free proxies. The conversion method follows the class-slide relative-PPP / equal-real-rate assumption.
    """)

with st.expander("Data sources, freshness and manual override status"):
    st.markdown(f"""
    - **Industry unlevered beta:** {beta_source}. [Damodaran data]({BETAS_URL})
    - **U.S. Baa2 / BBB spread:** {spread_source}. [Damodaran ratings table]({RATINGS_URL})
    - **10-year government yields:** {bond_source}. [Trading Economics]({TE_URL})
    - **Statutory tax rate:** {tax_source}. [OECD Corporate Tax Statistics 2024]({OECD_URL})
    """)
    st.caption("Data is cached for 24 hours. Source layouts can change; inspect the source links and use manual overrides if a live parser fails. Any fallback values are identified above and should be verified before submission.")

# All-industry sensitivity / comparison at same financing and market assumptions
st.markdown('<div class="section-label">04 / Industry comparison</div>', unsafe_allow_html=True)
comparison = beta_df.copy()
comparison["Levered beta"] = comparison["Unlevered beta"] * (1 + (1-tax) * debt_weight/(1-debt_weight))
comparison["USD cost of equity"] = us_rf + comparison["Levered beta"] * erp
comparison["USD WACC"] = ((1-debt_weight)*comparison["USD cost of equity"]
                          + debt_weight*(us_rf+us_spread)*(1-tax))
comparison["Foreign cost of equity"] = (1+comparison["USD cost of equity"])*result["FX conversion factor"]-1
foreign_spread_used = result["Foreign BBB spread"]
comparison["Foreign WACC"] = ((1-debt_weight)*comparison["Foreign cost of equity"]
                              + debt_weight*(foreign_rf+foreign_spread_used)*(1-tax))
comparison["Selected"] = comparison["Industry"].eq(industry)
st.caption("All industries use the same tax rate, ERP, target debt share, yields and credit spread. Only the unlevered industry beta changes.")
chart = px.bar(comparison.sort_values("Foreign WACC", ascending=False), x="Industry",
               y="Foreign WACC", color="Selected", color_discrete_map={True:"#0b8f83",False:"#9aabba"},
               title=f"Foreign-currency WACC by industry · {country}")
chart.update_layout(template="plotly_white", xaxis_tickangle=-55, showlegend=False,
                    yaxis_tickformat=".1%", margin=dict(l=10,r=10,t=55,b=130))
st.plotly_chart(chart, use_container_width=True)
st.dataframe(comparison[["Industry","Unlevered beta","Levered beta","USD WACC","Foreign WACC"]]
             .sort_values("Foreign WACC", ascending=False).style.format({
                 "Unlevered beta":"{:.2f}", "Levered beta":"{:.2f}",
                 "USD WACC":"{:.2%}", "Foreign WACC":"{:.2%}"
             }), use_container_width=True, hide_index=True)

# Downloadable calculation output
assumptions = {
    "Industry": industry, "Project country": country, "Currency": currency,
    "Unlevered beta": beta, "ERP": erp, "Debt share": debt_weight, "Tax rate": tax,
    "Tax rate selection": tax_choice, "U.S. 10Y yield": us_rf,
    "Foreign 10Y yield": foreign_rf, "U.S. BBB spread": us_spread,
    "Foreign BBB spread override": foreign_override,
}
output = pd.DataFrame([{"Metric":k,"Value":v} for k,v in assumptions.items()] +
                      [{"Metric":k,"Value":v} for k,v in result.items()])
csv = output.to_csv(index=False).encode("utf-8")
st.download_button("Download assumptions & results (CSV)", data=csv,
                   file_name="international_cost_of_capital_results.csv", mime="text/csv")

if st.button("Refresh source data", type="secondary"):
    st.cache_data.clear()
    st.rerun()

st.markdown("---")
st.caption(f"Model run: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')} · Educational decision-support tool; not investment advice.")
