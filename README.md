# Kepler Light Curve — Trend, Variability & Uncertainty

**DS-III Data Visualization — Time Series Assignment**

Visualization of the Kepler long-cadence light curve for **KIC 11395018**,
a solar-like oscillator observed across multiple quarters. The analysis
separates long-term trend from short-term variability via STL decomposition
and communicates uncertainty with a rolling 95% band that combines pipeline
photon noise with systematic scatter.

---

## Dataset

| Field | Value |
|---|---|
| Target | KIC 11395018 |
| Mission | Kepler (long cadence, 29.4 min integration) |
| Coverage | Multi-quarter stitched baseline |
| Source file | `hlsp_kepler.fits` (extension `LIGHTCURVE_STITCHED`) |
| Derived CSV | `kic11395018_lightcurve.csv` |

**Columns in the CSV** (produced from the FITS file with `astropy.io.fits`):

| Column | Meaning |
|---|---|
| `time` | BJD − 2454833 (days since Kepler launch epoch) |
| `cadenceno` | Sequential cadence index |
| `quarter` | Kepler quarter number |
| `flux` | PDCSAP flux (e⁻/s) |
| `flux_err` | 1σ uncertainty on `flux` |
| `sap_flux` | Simple aperture photometry flux |
| `sap_flux_err` | 1σ uncertainty on `sap_flux` |
| `psf_flat_flux` | PSF-fit photometry flux |
| `psf_flat_flux_err` | 1σ uncertainty on `psf_flat_flux` |
| `sap_quality` | Quality bitmask (0 = good) |
| `flatten_mask` | Flattening mask flag |

The CSV is included in the repository, so no download step is required to
reproduce the analysis.

---

## What the analysis does

1. **Loads** the stitched light curve and converts BJD to real datetimes.
2. **Normalizes** flux to relative units centered near 1.0.
3. **Decomposes** the daily-binned series with STL into trend, seasonal
   (7-day period), and residual components.
4. **Plots** the light curve with a rolling ±1.96σ uncertainty band that
   combines pipeline `flux_err` (photon noise) with a rolling standard
   deviation (systematics).
5. **Documents** temporal-honesty choices: cadence disclosure, quarter-gap
   representation, quality-flag handling, and axis scaling.

An **optional bootstrap confidence interval** is also computed in the
notebook, showing an empirical alternative to the ±2σ assumption.

---

## Deliverables

### 1. Jupyter notebook (primary)

- `kepler_lightcurve.ipynb` — executed notebook with outputs saved.
- `kepler_lightcurve.html` — self-contained HTML export of the executed notebook.

**To view:** open the `.html` file in any browser — no installation needed.

**To run:**

```bash
python -m venv .venv
.venv\Scripts\activate            # Windows
# source .venv/bin/activate       # macOS / Linux
pip install -r requirements.txt
jupyter notebook kepler_lightcurve.ipynb
```

Then **Run All** in the notebook.

### 2. Streamlit app (secondary)

`app.py` provides the same analysis interactively, with a sidebar resolution
widget, quarter filter, and quality-flag toggle.

**To run:**

```bash
streamlit run app.py
```

Opens at `http://localhost:8501`.

---

## Files

```
.
├── README.md
├── requirements.txt
├── kic11395018_lightcurve.csv        # the dataset
├── kepler_lightcurve.ipynb           # executed notebook (source + outputs)
├── kepler_lightcurve.html            # exported HTML (self-contained)
└── app.py                            # Streamlit version
```

---

## Temporal-honesty choices

These are documented in the notebook (Section 7) and in the Streamlit app
("Temporal-Honesty Choice" panel):

- **Cadence disclosure.** Kepler long-cadence integrates 29.4 minutes per
  point. Binning to 6-hour or daily averages suppresses real short-period
  variability. The active resolution is always stated in the figure title
  and caption.

- **Quarter gaps.** The x-axis uses real datetimes, so the ~1-day downlinks
  between Kepler quarters appear as horizontal gaps. This is truthful — the
  telescope was not observing during those intervals.

- **Quality flags.** Non-zero `sap_quality` cadences are shown by default.
  The Streamlit sidebar exposes a toggle to exclude them; the choice is
  explicit, never silent.

- **Axis honesty.** The y-axis uses `scale(zero=False)` because relative
  flux spans a narrow range (~0.99–1.01). Forcing zero would compress the
  signal into a flat line.

- **Uncertainty.** The rolling band combines pipeline photon noise with
  rolling systematics. A fixed global band would misrepresent
  heteroskedasticity across quarters.

---

## Requirements

```
pandas>=2.0
numpy>=1.24
matplotlib>=3.7
altair>=5.0
statsmodels>=0.14
streamlit>=1.39
jupyter>=1.0
nbconvert>=7.0
```

Install everything at once:

```bash
pip install -r requirements.txt
```

---

## Rubric mapping

| Requirement | Where it is satisfied |
|---|---|
| Time series ≥ a few years | Multi-quarter Kepler baseline (KIC 11395018) |
| Trend shown | STL trend panel + rolling mean line |
| Seasonality/variability shown | STL seasonal panel (7-day period) |
| Uncertainty shown | Rolling ±1.96σ band + optional bootstrap CI |
| Temporal-honesty note | Section 7 of the notebook; "Temporal-Honesty Choice" panel in the app |
| Resolution widget (Streamlit path) | Sidebar radio: Native / 6-hour / Daily |
| Runnable with no errors | `streamlit run app.py`, or open the `.html` / `.ipynb` |
| Correct date handling & resampling | BJD → datetime conversion; pandas `resample` on a `DatetimeIndex` |

---

## Reproducing the CSV from the FITS file

If you want to regenerate the dataset from scratch:

```python
from astropy.io import fits
import pandas as pd
import numpy as np

filename = "hlsp_kepler.fits"

with fits.open(filename) as hdul:
    data = hdul["LIGHTCURVE_STITCHED"].data
    columns = {
        name.lower(): np.asarray(data[name]).byteswap().view(
            np.asarray(data[name]).dtype.newbyteorder("=")
        )
        for name in data.names
    }

df = pd.DataFrame(columns).dropna(subset=["time", "flux"])
df.to_csv("kic11395018_lightcurve.csv", index=False)
print(f"Saved {len(df):,} rows.")
```

---

## Author

**Jael Rojas** — MS Data Science, DS-III Data Visualization
