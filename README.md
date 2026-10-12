# CMMS Utility Analytics

Upload an interval meter export (CSV or XLSX) and get back headline metrics and a 3-page PDF report: cost and carbon estimates, data-quality checks, daily trend, weekday/weekend profile, a day-by-hour heatmap and flagged anomalies.

Live: https://engie-cmms.vercel.app/

## How it works

| Part | Where | What it does |
| --- | --- | --- |
| Web page | `app/`, `components/` | Next.js upload form. Posts the file and rates to `/api/analyze`, shows the metrics, offers the PDF as a download. |
| API | `api/analyze.py` | FastAPI function (deployed by Vercel as a Python serverless function). Validates the request and returns JSON with the metrics and the PDF, base64-encoded. |
| Analysis | `analytics/core.py` | Reads the file, cleans it and computes the metrics. No web or plotting code. |
| Report | `analytics/report.py` | Renders the PDF with matplotlib. |

Files are processed in memory and nothing is stored. There are no environment variables or external services to configure.

## Input file

- **Format:** `.csv` or `.xlsx`, up to 4 MB (Vercel rejects larger request bodies).
- **Columns:** one date/time column and one consumption column in kWh per reading. They are found by name:
  - date/time: a name containing `datetime`, `timestamp`, `date` or `time`
  - consumption: a name containing `consumption`, `kwh`, `usage` or `energy`
- **Header row:** may be anywhere in the first 20 rows, so title rows above it are fine.
- **Dates:** `YYYY-MM-DD HH:MM` is safest. `DD/MM/YYYY` and `MM/DD/YYYY` are both detected from the data; if a file is genuinely ambiguous, `DD/MM` is assumed and the report says so.

Rows with an unreadable date, a non-numeric or negative value, or a duplicate timestamp are excluded and counted in the report's data-quality section.

`sample-data/sample_meter_15min.csv` is a four-week example with a spike, an out-of-hours load and a gap. Regenerate it with `python scripts/make_sample_data.py`.

## Running locally

You need Node 20+ and Python 3.12+. Two processes run side by side; in development Next.js forwards `/api/*` to the Python server (see `next.config.mjs`).

```bash
# Terminal 1 — API
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
uvicorn api.analyze:app --port 8000 --reload

# Terminal 2 — web
npm install
npm run dev
```

Open http://localhost:3000 and upload the sample file.

## Checks

```bash
pytest               # analysis and API tests
npm run lint         # ESLint
npx tsc --noEmit     # type-check
npm run build        # production build
```

## Notes on the metrics

- **Cost and carbon** are consumption multiplied by the tariff and emission factor entered on the form. The defaults (0.15 per kWh, 0.4 kg CO2e per kWh) are placeholders, set in `api/analyze.py` and `components/analytics-upload.tsx`.
- **Base load** is the 5th percentile of non-zero readings.
- **Anomalies** are readings far from the median for the same hour of the week (robust z-score above 3.5). With too little data per hour of week, the comparison falls back to weekday/weekend hour, then to the whole period; the report states which was used.
- **Missing intervals** are inferred from the median gap between readings. Totals are not adjusted for them.

## Deployment

Pushing to `main` deploys to Vercel. Python dependencies come from `requirements.txt`, which is pinned; update the pins deliberately and re-run `pytest`.
