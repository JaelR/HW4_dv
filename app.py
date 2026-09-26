"""
Kepler Light Curve Explorer — Trend, Variability & Uncertainty
DS-III Assignment: Time series visualization with temporal framing.

Dataset: KIC 11395018, Kepler long-cadence stitched light curve
         (FITS: hlsp_kepler.fits, extension LIGHTCURVE_STITCHED)
         https://mast.stsci.edu/portal/Mashup/Clients/Mast/Portal.html
"""
from pathlib import Path
import numpy as np
import pandas as pd
import streamlit as st
import altair as alt
from statsmodels.tsa.seasonal import STL

st.set_page_config(page_title="Kepler Light Curve Explorer", layout="wide")
st.title("⭐ Kepler Light Curve — KIC 11395018")
st.caption(
    "Kepler long-cadence photometry | stitched multi-quarter baseline | "
    "29.4-minute integration per point"
)


# ---------------- Data Path (works locally AND on Streamlit Cloud) ----------------
HERE = Path(__file__).resolve().parent
DATA_FILE = HERE / "kic11395018_lightcurve.csv"

st.write(f"Looking for: `{DATA_FILE}`")
st.write(f"Exists: `{DATA_FILE.exists()}`")

if not DATA_FILE.exists():
    st.error(
        f"Data file not found at `{DATA_FILE}`. "
        f"Make sure `kic11395018_lightcurve.csv` is committed to the repo "
        f"at the same level as `app.py`."
    )
    st.stop()


# ---------------- Data Loading ----------------
@st.cache_data
def load_data(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)

    # Convert BJD (days since 2454833, Kepler launch epoch) to datetime
    epoch = pd.Timestamp("2009-05-02")
    df["datetime"] = epoch + pd.to_timedelta(df["time"], unit="D")

    # Relative flux centered near 1.0
    median_flux = df["flux"].median()
    df["rel_flux"] = df["flux"] / median_flux
    if "flux_err" in df.columns:
        df["rel_flux_err"] = df["flux_err"] / median_flux
    else:
        df["rel_flux_err"] = 0.0

    # Quality flag
    if "sap_quality" in df.columns:
        df["sap_quality"] = df["sap_quality"].fillna(0).astype(int)
    else:
        df["sap_quality"] = 0

    return df.sort_values("datetime").reset_index(drop=True)

try:
    df = load_data(DATA_FILE)
except FileNotFoundError:
    st.error(
        f"Could not find **{DATA_FILE}**. "
        "Place it in the same folder as `app.py` and reload."
    )
    st.stop()

total_rows = len(df)
good_rows = int((df["sap_quality"] == 0).sum())
flagged_rows = total_rows - good_rows

st.sidebar.metric("Total cadences", f"{total_rows:,}")
st.sidebar.caption(f"Flagged: {flagged_rows:,} / {total_rows:,}")


# ---------------- Sidebar Controls ----------------
st.sidebar.header("⚙️ Controls")

resolution = st.sidebar.radio(
    "Display resolution",
    options=["Native cadence (29.4 min)", "6-hour bins", "Daily bins"],
    index=2,
    help="Kepler long-cadence integrates 29.4 minutes per point. "
         "Binning suppresses short-period variability.",
)

quality_filter = st.sidebar.checkbox(
    "Keep only good-quality cadences (sap_quality == 0)",
    value=False,   # default off — show the honest full picture first
    help=f"{flagged_rows:,} cadences carry non-zero quality flags.",
)

quarters = sorted(df["quarter"].dropna().unique().tolist()) \
    if "quarter" in df.columns else []

if quarters:
    quarter_filter = st.sidebar.multiselect(
        "Quarters to display",
        options=quarters,
        default=quarters,
    )
else:
    quarter_filter = None


# ---------------- Apply Filters ----------------
filtered = df.copy()
if quarter_filter is not None:
    filtered = filtered[filtered["quarter"].isin(quarter_filter)]
if quality_filter:
    filtered = filtered[filtered["sap_quality"] == 0]

if filtered.empty:
    st.warning("No data after filtering. Relax the sidebar filters.")
    st.stop()


# ---------------- Resampling ----------------
bin_map = {
    "Native cadence (29.4 min)": None,
    "6-hour bins": "6h",
    "Daily bins": "1D",
}
rule = bin_map[resolution]

if rule is None:
    plot_df = (
        filtered[["datetime", "rel_flux", "rel_flux_err"]]
        .rename(columns={"datetime": "date"})
        .reset_index(drop=True)
    )
else:
    plot_df = (
        filtered.set_index("datetime")       # datetime index → resample OK
        .resample(rule)
        .agg({"rel_flux": "mean", "rel_flux_err": "mean"})
        .dropna()
        .reset_index()
        .rename(columns={"datetime": "date"})
    )


# ---------------- STL Decomposition ----------------
@st.cache_data
def decompose_daily(times: np.ndarray, values: np.ndarray):
    s = pd.Series(values, index=pd.to_datetime(times)).sort_index()
    s = s.resample("1D").mean().dropna()
    if len(s) < 14:
        return None
    res = STL(s, period=7, robust=True).fit()
    return {
        "dates": s.index,
        "trend": res.trend.values,
        "seasonal": res.seasonal.values,
        "resid": res.resid.values,
    }


stl_result = decompose_daily(
    filtered["datetime"].values, filtered["rel_flux"].values
)


# ---------------- Layout ----------------
col1, col2 = st.columns([3, 2])

with col1:
    st.subheader("📈 Light Curve with Uncertainty")

    window = {"Native cadence (29.4 min)": 200,
              "6-hour bins": 14,
              "Daily bins": 7}[resolution]

    roll_mean = plot_df["rel_flux"].rolling(window, center=True, min_periods=1).mean()
    roll_std = plot_df["rel_flux"].rolling(window, center=True, min_periods=1).std()

    total_sigma = np.sqrt(roll_std.fillna(0) ** 2 +
                          plot_df["rel_flux_err"].fillna(0) ** 2)

    band_df = pd.DataFrame({
        "date": plot_df["date"],
        "mean": roll_mean,
        "lower": roll_mean - 1.96 * total_sigma,
        "upper": roll_mean + 1.96 * total_sigma,
    })

    band = alt.Chart(band_df).mark_area(opacity=0.25, color="#4c78a8").encode(
        x=alt.X("date:T", title="Date"),
        y=alt.Y("lower:Q", title="Relative flux",
                scale=alt.Scale(zero=False)),
        y2="upper:Q",
    )
    line = alt.Chart(band_df).mark_line(color="#1f4e79", strokeWidth=1.5).encode(
        x="date:T", y="mean:Q"
    )
    points = (
        alt.Chart(plot_df)
        .mark_circle(size=6, opacity=0.25, color="#555")
        .encode(
            x="date:T",
            y="rel_flux:Q",
            tooltip=[
                alt.Tooltip("date:T", title="Date"),
                alt.Tooltip("rel_flux:Q", format=".5f", title="Relative flux"),
            ],
        )
    )
    st.altair_chart(
        (band + line + points).properties(height=420),
        use_container_width=True,
    )

    st.caption(
        f"**Figure 1.** KIC 11395018 at **{resolution}**. "
        "Shaded band = rolling ±1.96σ combining pipeline `flux_err` and "
        "rolling-window systematics. Gaps between clusters are the ~1-day "
        "downlinks between Kepler quarters."
    )

with col2:
    st.subheader("🔍 STL Decomposition")
    st.markdown(
        "**STL** separates the light curve into trend, seasonal, and residual "
        "components. Trend = slow drift; seasonal = short-period structure "
        "(7-day period here); residual = unexplained noise and systematics."
    )

    if stl_result is None:
        st.info("Not enough data for STL after filtering.")
    else:
        for key, color, label in [
            ("trend", "#d62728", "Trend"),
            ("seasonal", "#2ca02c", "Seasonal (7-day)"),
            ("resid", "#7f7f7f", "Residual"),
        ]:
            chart = (
                alt.Chart(pd.DataFrame({
                    "date": stl_result["dates"],
                    "value": stl_result[key],
                }))
                .mark_line(color=color)
                .encode(
                    x=alt.X("date:T",
                            title=None if key != "resid" else "Date"),
                    y=alt.Y("value:Q", title=label),
                )
                .properties(height=105, title=label)
            )
            st.altair_chart(chart, use_container_width=True)


# ---------------- Temporal Honesty Note ----------------
st.divider()
st.subheader("📝 Temporal-Honesty Choice")

st.markdown(
    f"""
    **Cadence disclosure.** Kepler long-cadence integrates **29.4 minutes per
    measurement**. The sidebar label is *"Display resolution"*, not *"zoom"*,
    because binning is not zooming: aggregating to 6-hour or daily bins
    averages away real short-period variability. At **{resolution}**, each
    point represents {'one 29.4-minute integration' if rule is None else ('a 6-hour average' if rule == '6h' else 'a daily average')}.

    **Quarter gaps.** The x-axis is drawn in real time (`date:T`), so the
    ~1-day downlinks between Kepler quarters appear as horizontal breaks —
    a truthful representation of the observing schedule. Connecting points
    across gaps would imply continuous coverage that does not exist.

    **Quality flags.** {flagged_rows:,} of {total_rows:,} cadences carry
    non-zero `sap_quality` flags. The sidebar toggle lets you include or
    exclude them; the default keeps them in so the reader sees the raw
    picture first.

    **Axis honesty.** The y-axis uses `scale(zero=False)` because relative
    flux spans a narrow range (~0.99–1.01). Forcing zero would compress the
    signal into a flat line. Uncertainty combines pipeline `flux_err`
    (photon noise) with a rolling standard deviation (systematics); a fixed
    global band would misrepresent heteroskedasticity across quarters.
    """
)


# ---------------- Data Preview ----------------
with st.expander("Show data preview"):
    st.dataframe(plot_df.head(20), use_container_width=True)
    st.caption(f"Rows shown: {len(plot_df):,} | Columns: {plot_df.shape[1]}")

with st.expander("Column glossary"):
    st.markdown(
        """
        | Column | Meaning |
        |---|---|
        | `time` | BJD − 2454833 (days since Kepler launch epoch) |
        | `cadenceno` | Sequential cadence index |
        | `quarter` | Kepler quarter number |
        | `flux` | PDCSAP flux (e⁻/s) |
        | `flux_err` | 1σ uncertainty on `flux` |
        | `sap_flux` | Simple aperture photometry flux |
        | `sap_quality` | Quality bitmask (0 = good) |
        """
    )
