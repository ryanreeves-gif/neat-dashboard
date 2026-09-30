# Neat workplace intelligence

A Streamlit redesign of the existing Neat dashboard: executive overview, space utilisation, room fit, environmental evidence and practical next steps. Uses the existing published Google Sheet feed. This repository does not contain a direct Pulse API collector.

## Review and deploy

1. Extract the supplied project. The complete `neat-dashboard/` folder contains the updated app; uploading `app.py` alone is insufficient.
2. In your GitHub repository, create a review branch named `feature/neat-workplace-dashboard` from `main`.
3. Add the package's `app.py`, `pages/`, `workplace/`, `assets/`, `requirements.txt`, `.streamlit/config.toml`, `.gitignore`, `tests/` and this README to that branch. Retain any existing deployment settings or secrets outside these files. Remove the obsolete `requirements.txt.txt`, `pages/AI_Search.py.txt` and `pages/Administration.py.txt` copies; they are not used by Streamlit.
4. Create a separate Streamlit Community Cloud app from this branch, with entry point `app.py` and Python 3.12. This gives you a review URL while the existing app continues to use `main`.
5. Check the review app on your webinar laptop: date/location filters, one room's evidence, every info popover, navigation, downloads and the narrower window layout. Compare representative totals with the collector.
6. Once you approve the review, merge the branch into `main`; the app connected to that branch can deploy the new version. Revert the merge to restore the previous app if necessary.

No changes have been pushed to GitHub or published to the existing Streamlit app as part of this package. The supplied code was validated locally. A browser visual review remains required because the available cloud browser could not access the local server.

## Run locally

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
streamlit run app.py
```

On Windows, activate with `.venv\Scripts\activate`. Open the local URL printed by Streamlit. Python 3.12 is recommended for the deployment environment.

The current CSV URL is retained in `workplace/data.py`. To use a different source, set `NEAT_TELEMETRY_CSV` in the environment or Streamlit secrets. This accepts an HTTPS URL or a local CSV path. Do not put credentials in committed source files. `NEAT_DATE_ORDER` defaults to `legacy_mixed`; supported alternatives are `dayfirst`, `monthfirst` and `iso`.

Required columns: `Timestamp`, `Room Name`, `Location`. Other fields: `Occupancy`, `Capacity`, `Device Status`, `Temperature`, `Humidity`, `Light Level`, `VOC`, `Platform`, `Software Version`. Missing sensor fields stay unknown. A source without device status is explicitly marked unreported; the app then cannot exclude offline readings.

The feed is cached for ten minutes. Sidebar → Data source → Refresh observations reloads it. A failed connection displays an error. Demonstration data is used only after an explicit opt-in, is clearly labelled, and is never substituted silently.

## Experience

- **Overview:** four outcome measures, a weekday demand heatmap, one room-fit example and three rooms to investigate.
- **Spaces:** attendance versus capacity, individual histories and downloadable observations.
- **Environment:** temperature, humidity, light and VOC trends, plus environmental evidence.
- **Insights:** all qualifying findings with owners, evidence and next steps.
- **Operations:** latest selected room status and a downloadable draft facilities handoff.
- **Ask the data:** a guided set of questions using the same calculations; no simulated AI reasoning.

Each headline metric and section has a native Streamlit info popover. Hover provides a hint; click opens meaning, business value, calculation and limitations. Click outside dismisses the panel. The native button also supports keyboard use. Shared selections persist as you move between pages.

## Calculation rules

| Measure | Definition |
| --- | --- |
| Rooms monitored | Distinct location + room name with a record in the selected period. Known positive capacity is required by default; More filters can include unclassified and zero-capacity assets. |
| Space utilisation | Occupied observed room-hours ÷ valid observed room-hours. |
| Typical attendance | Person-hours ÷ occupied room-hours. Empty time is excluded. |
| Observation coverage | Valid occupancy room-hours ÷ scheduled room-hours across rooms in scope. |
| Room fit | Time-weighted attendance and P90 compared with recorded capacity. A candidate requires ≥2 occupied hours, ≥4 seats and P90 ≤ half capacity. |
| Warm / bright empty | Valid zero occupancy at the same time as temperature >22°C or illuminance >50 lux, for ≥1 observed hour. These are adjustable investigation thresholds. |
| Rooms to review | Unique rooms with one or more qualifying findings. Overview shows one finding per room, ordered by evidence hours. |

Each sample represents time until the next sample, capped at the median observed sampling cadence for its room (1–30 minutes; 10-minute fallback). This handles the source's historical 15-minute and recent 10-minute collection, but remains an estimate between readings. Gaps, missing occupancy, offline states and unknown states do not become empty-room time. Hours are clipped to the selected dates and, by default, weekdays 08:00–19:00. Heatmap intervals split at hour boundaries so they reconcile with totals.

Dates end at the latest available source timestamp, rather than implying data exists through the present. Office hours use the recorded source clock: no per-location timezone mapping is supplied. Offset-bearing ISO timestamps are normalised to UTC; provide consistent clock semantics when changing the collector. Coverage treats each included room as in scope for the whole period because commissioning dates are absent. A comparison uses the preceding calendar window, preserving the partial final day's clock time, and is shown only when both windows have ≥70% occupancy coverage.

The existing sheet changed from unpadded US dates (e.g. `9/10/2026 11:55:32`, September 10) to padded UK dates (`10/09/2026 12:41:06`, also September 10). The default parser explicitly supports that source-specific convention; it is not a generic format detector. Prefer ISO timestamps in future collection. Duplicate location/room/timestamp rows keep the last entry.

Capacity uses available metadata within the same location and room name, filling missing entries forwards then backwards. Unknown capacity is never assumed to be four seats. Metadata corrections, renamed rooms and parallel platform aliases require reconciliation in the collector before making estate-wide decisions.

## Claims and integrations

Temperature does not prove heating is on; lux does not prove electric lighting is on. No-shows require bookings. Energy and verified savings require controls, meters and an agreed baseline. VOC remains in source units until the collector's field is confirmed; it is not CO₂ or a carbon-emissions measure.

Removed the previous simulated incident confirmations, fake control actions and hard-coded financial savings. Operations exports a JSON **draft**, without sending a ticket, webhook, reboot or BMS command. Source observations exported from a room include all readings within the selected dates, including times outside the office-hours calculation, for auditability.

## Brand assets

The original Neat SVG logo and Maison Neue Book/Bold webfonts are bundled, so rendering does not depend on a third-party font request. Sources used for this Neat-led project:

- Logo: `https://cdn.neat.no/v3/assets/img/neat-logo-dark.svg`
- Fonts: Neat's public web storefront, `fonts/maison-neue-mg/MaisonNeue-Book.woff2` and `MaisonNeue-Bold.woff2`.
- UI charcoal `#333333`, website blue `#6A87D0`, background `#F6F7F8`, white panels and light neutral borders. Logo proportions and the original wordmark are preserved.

Current website styling takes precedence over the uploaded 2025 partner document, as requested. Brand assets retain their respective ownership; this package does not relicense them for unrelated products.

## Verification

```bash
python -m pip install pytest
python -m pytest tests -q
```

Pure calculation tests cover the timestamp migration, duplicate records, unknown sensors, offline exclusion, time weighting, sampling gaps, office boundaries, heatmap reconciliation and room-fit evidence. Streamlit AppTest also loads all six pages and tests cross-page filters and explicit sample mode. Actual live deployment, browser layout and mouse/keyboard dismissal need checking in the separate review app.

Deployment reference: https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/deploy
