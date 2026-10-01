# Neat workplace intelligence

A Streamlit redesign of the existing Neat dashboard: executive overview, space utilisation, room fit, environmental evidence and practical next steps. Uses the existing published Google Sheet feed. This repository does not contain a direct Pulse API collector.

## Review and deploy

1. Extract the supplied project. The complete `neat-dashboard/` folder contains the updated app; uploading `app.py` alone is insufficient.
2. In your GitHub repository, create a review branch named `feature/neat-workplace-dashboard` from `main`.
3. Add the package's `app.py`, `pages/`, `workplace/`, `assets/`, `requirements.txt`, `.streamlit/config.toml`, `.gitignore`, `tests/` and this README to that branch. Retain any existing deployment settings or secrets outside these files. Remove the obsolete `requirements.txt.txt`, `pages/AI_Search.py.txt` and `pages/Administration.py.txt` copies; they are not used by Streamlit.
4. Create a separate Streamlit Community Cloud app from this branch, with entry point `app.py` and Python 3.12. This gives you a review URL while the existing app continues to use `main`.
5. Check the review app on your webinar laptop: date/location filters, one room's evidence, every info popover, navigation, downloads and the narrower window layout. Compare representative totals with the collector.
6. Once you approve the review, merge the branch into `main`; the app connected to that branch can deploy the new version. Revert the merge to restore the previous app if necessary.

Development is published to `feature/neat-workplace-dashboard` and the separate Streamlit preview. The original `main` app is kept unchanged. Streamlit may require a reboot to load a new build; verify the preview before merging.

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

The app opens in **Presentation view**, a compact four-chapter executive briefing. Switch it off in the sidebar for the complete dashboard. Scope, data-quality detail, calculation notes and savings assumptions remain available in sidebar expanders or popovers, rather than taking space from the main visual story. The layout targets a laptop/monitor canvas; narrower screens stack cards without clipping information.

| Webinar timing | Chapter | Decision and demonstration |
| --- | --- | --- |
| 0:00–2:00 | The conclusion | Earn the commute: which room-fit, experience and cost improvements deserve a pilot? |
| 2:00–4:30 | The right space | One room, its automatically matched capacity peer, and a replay against a proposed smaller room. |
| 4:30–7:00 | The experience | Separate employee and guest sentiment, then try the portrait survey in a dialog. |
| 7:00–10:00 | The next move | Replay an explicitly simulated Pulse → ServiceNow → BMS workflow. Close on an owner, budget and review date. |

The sidebar's Presenter guide contains these cues. Each chapter has a next link. Use one room through the story, and retain deeper pages for questions. A live pilot should compare real room demand, comfort, actual cost/energy and genuine feedback before and after the change. No dashboard metric alone establishes whether a commute is worthwhile.

The compact workflow reuses the coverage-screened findings. It is disabled where no qualifying finding supports the selected room and condition. Simulation results are tied to room, dates, hours, thresholds and evidence; changing that configuration removes the displayed result. No command is sent, no ServiceNow ticket is created and no saving is measured. The financial example is opt-in and independent of this control simulation.

The full dashboard remains available:

- **Overview:** the executive conclusion: a recommended direction, savings case, room-type demand, equipment in the leading room, employee/guest sample sentiment and priority actions. Supporting utilisation evidence is expandable.
- **Spaces:** automatic comparison with a similarly sized room, attendance versus capacity, individual histories and downloadable observations.
- **Scenarios:** current capacity alongside two editable room layouts, optional project costs and a downloadable comparison. Open from the sidebar or Spaces → Compare alternative layouts.
- **Feedback:** clearly labelled synthetic employee and customer/guest results across the room feed's history, audience/date/room filters, exports and an interactive portrait survey.
- **Frame:** a standalone portrait survey demonstration, opened from Feedback. The `room` query parameter identifies its room; submissions remain in the browser's Streamlit session.
- **Environment:** recurring conditions, sensor trends, facilities investigation candidates and the simulated action workflow.
- **Opportunities (Insights route):** room-mix, temperature and lighting themes, with evidence, owners and next steps.
- **Value & ROI:** room-specific entered annual costs, cash-flow projection, ROI, payback and savings sensitivity. No automatic financial claims are derived from Pulse or sample sentiment.
- **Operations:** visual room-status cards, records to check, platform mix and a downloadable draft facilities handoff.
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
| Rooms to review | Unique rooms with one or more qualifying findings. Overview checks data readiness, then covers distinct room-fit, temperature and lighting decisions with one finding per room. The longest evidence within each theme is considered first. |

Each sample represents time until the next sample, capped at the median observed sampling cadence for its room (1–30 minutes; 10-minute fallback). This handles the source's historical 15-minute and recent 10-minute collection, but remains an estimate between readings. Gaps, missing occupancy, offline states and unknown states do not become empty-room time. Hours are clipped to the selected dates and, by default, weekdays 08:00–19:00. Heatmap intervals split at hour boundaries so they reconcile with totals.

Dates end at the latest available source timestamp, rather than implying data exists through the present. Office hours use the recorded source clock: no per-location timezone mapping is supplied. Offset-bearing ISO timestamps are normalised to UTC; provide consistent clock semantics when changing the collector. Coverage treats each included room as in scope for the whole period because commissioning dates are absent. A comparison uses the preceding calendar window, preserving the partial final day's clock time, and is shown only when both windows have ≥70% occupancy coverage.

The existing sheet changed from unpadded US dates (e.g. `9/10/2026 11:55:32`, September 10) to padded UK dates (`10/09/2026 12:41:06`, also September 10). The default parser explicitly supports that source-specific convention; it is not a generic format detector. Prefer ISO timestamps in future collection. Duplicate location/room/timestamp rows keep the last entry.

Capacity uses available metadata within the same location and room name, filling missing entries forwards then backwards. Unknown capacity is never assumed to be four seats. Metadata corrections, renamed rooms and parallel platform aliases require reconciliation in the collector before making estate-wide decisions.

## Claims and integrations

### Overview conclusions

The conclusion adapts to the selected scope and observation coverage. Improvement counts include only rooms with at least 70% occupancy coverage and use the existing room-fit, warm-empty and bright-empty findings. Counts across themes can overlap; the headline counts distinct rooms.

Room types are inferred size bands: Focus (1–2 seats), Small (3–6), Medium (7–12) and Large (13+). Rankings require positive capacity, at least 70% occupancy coverage and at least two observed hours per included room. The score pools occupied and observed hours, rather than averaging room percentages. Ties at one decimal place are retained; a single eligible category is not called a comparison winner, and zero-use categories do not produce a leader. Highest use is a demand signal, not a quality or ROI score.

The device highlight identifies the current video equipment in the busiest qualifying room, using the inventory snapshot at the selected period end. It does not claim a device-level use, quality or historical installation comparison. Multiple video products remain a mixed setup, controllers are listed separately and unmapped codes are retained without guessed names. Equipment metadata is optional; an unknown model does not cause the app to select a different room. Product-code mappings are sourced from [Neat's model guide](https://support.neat.no/article/neat-device-attributes-for-microsoft-intune-conditional-access-device-exclusions/) and [Microsoft's device list](https://learn.microsoft.com/en-us/microsoftteams/devices/certified-hardware-android).

The savings summary reads complete Value & ROI cases for rooms in the selected scope, within the current browser session. A selector chooses one case; projects and currencies are never added together. Annual net benefit excludes the initial investment, which is shown separately with payback and horizon net benefit. If no case is complete, the result stays unassessed. An optional, clearly labelled illustration shows £18,000 initial investment, £9,000 annual savings and £1,500 extra annual cost: £7,500 annual net benefit, 28.8-month simple payback and £4,500 three-year net benefit. This illustration does not populate or overwrite a customer's cost inputs.

Overview sentiment covers both audiences within the shared room/date/hour filters. It uses the same synthetic records as Feedback, with average space and equipment ratings, 4–5 positive share, response counts and an employee/guest distribution. Synthetic opinions never affect the room-use rankings or financial case.

### Room-size scenarios

Spaces and Scenarios automatically select a capacity peer from London EC or Oslo EC, independent of the selected room/location filters. The closest recorded capacity wins (maximum difference 25% or two seats), followed by the same location, higher coverage, observed hours and room key. Candidates need a source record in the date range. Both rooms use identical date/hour filters; limited coverage is shown. A capacity match does not imply identical equipment, room purpose or working patterns.

The scenario page replays one room's observed occupied time against proposed capacities. Each people count is treated as one group that must fit in one room. Two four-seat rooms therefore cannot accommodate an observed count of six in this model. Empty time, gaps and offline data are excluded from the fit denominator. The largest proposed room sets the capacity threshold; additional room use, concurrent demand and future utilisation are not predicted.

Options and costs are remembered per room during the browser session. Costs are optional user-entered totals, with separate values for GBP, EUR and NOK; changing currency does not convert a cost. No savings or payback is inferred. An entered Option A/B project cost can be carried to Value & ROI, where savings and additional running costs require separate assumptions. The export includes the room, selected dates/hours, data coverage, costs and assumptions. Validate dimensions, bookings, peak demand, accessibility, acoustics and AV requirements before adopting a layout.

### Value & ROI

The annual room-cost profile requires explicit property, technology/licensing and facilities/support inputs. Blank means unknown; zero is accepted as an explicit amount. Avoid overlapping categories and use an annualised equipment cost consistently. An optional, explicitly acknowledged allocation maps that annual total to occupied, observed-empty and unknown shares of the selected scheduled period. It assumes a representative annual pattern, retains missing time and never calls allocated empty-room cost a recoverable saving.

The project model is separate from that cost profile:
- Annual net cash benefit = expected annual cash savings minus additional annual running costs.
- Horizon net benefit = annual net benefit × assessment years minus initial project cost.
- ROI = horizon net benefit ÷ initial project cost × 100. A zero initial cost gives undefined ROI, not infinity.
- Simple payback = initial cost ÷ positive annual net benefit × 12 months; no payback is shown when net benefit is zero or negative.
- Sensitivity lines apply 50%, 100% and 125% to savings only, retaining the same project and additional running costs.

The model is undiscounted and omits tax, inflation, residual value and staged savings. Its results are projections from entered assumptions, not verified financial returns. Inputs remain per room and currency during the session. The illustrative preset is opt-in, labelled and editable, and does not represent Neat prices. The export retains assumptions, calculation horizon, telemetry scope, evidence coverage and source labels. Sample sentiment never enters a financial calculation.

### Customer story and visual system

The full navigation follows Understand → Improve → Operate; Presentation view reduces this to the four-chapter story above. Every page has a stated customer purpose, a leading answer or decision, graphical evidence and a practical next step. Technical details and long tables use expandable sections. Keep Pulse observations, invented sentiment and entered financial assumptions distinct at the point of use. The Feedback relationship chart combines actual room-use values with explicitly synthetic ratings solely to demonstrate a future live workflow.

Use Neat's September 2025 partner palette: restrained purple `#5F259F`, neutral backgrounds, Rain `#93ABB3`, Forest `#638C7D`, Sunrise `#DBC684`, Oak `#D5B68F`, Sunset `#D69B8C` and Walnut `#9F8884`. Retain the supplied wordmark and established Maison Neue font from the existing Neat-led experience. Purpose and legibility take priority over decoration. The one-page brief remains an evidence/investigation brief; business-case assumptions have a separate export.

### Feedback demonstration and path to a live pilot

Feedback is synthetic even when the telemetry toggle is set to the real feed. All generated rows and interactive tryouts carry `is_demo=true`, a versioned schema and a source label. Every displayed historical result, quote and export is labelled as sample data. These figures must not be used as real customer endorsements or measured employee satisfaction.

The deterministic generator uses one actual source timestamp in each three-hour office-time bucket per room/weekday (maximum four records/day). It covers each positive-capacity room's entire available history, including historical rooms when selected. It does not fill absent source dates or infer opinions from environmental/occupancy signals. Appending future source days preserves existing sample IDs and ratings. Choose **Full history** to show the full range; all other shared filters apply normally. The current feed begins on 9 April 2026 under the existing source date parser. Source time semantics remain unchanged.

Guest samples deliberately favour ratings of 4–5 (98% probability for spaces, 99% for equipment); employees are positive with more mixed experiences (88% and 92%). These are generation settings, not achieved survey statistics. Charts and exports calculate the actual resulting sample values. Optional issues and low-score comments provide examples for future service workflows.

The portrait form has no preselected audience or ratings. It validates both ratings, offers temperature/air-quality/lighting/technology issues and optional comments, and clears selections for the next visitor. IT help only shows a demonstration explanation. Interactive submissions use their actual UTC submission time and a separate `Interactive demonstration` source; they never alter or backdate the historical sample dataset. They are visible/exportable within the same browser session, not shared across devices, and disappear when that session ends.

For a future pilot, replace the sample source at the result-loading boundary and keep `sample_feedback` separately selectable. Persist validated responses through an authenticated HTTPS service/database, with a stable room ID, UTC timestamp, explicit audience choice, two 1–5 ratings and optional issue/comment. Maintain `schema_version`, unique response IDs and idempotent submission. Configure each Frame with its room, reset after completion/inactivity, restrict dashboard access, and agree retention and appropriate privacy text. Connect IT help to an agreed support destination; a support request should not be inferred from a survey rating. Neither persistent collection nor a service-desk integration is present in this demo.

Neat's official guidance describes portrait Frame touchscreens and custom web apps managed through Pulse. Device entitlement, mode, networking, kiosk behaviour and touch layout need verification on the actual Frame before a pilot:
- https://support.neat.no/article/how-to-set-up-a-neat-frame/
- https://support.neat.no/article/get-started-neat-pulse-app-hub/
- https://neat.no/app-hub/

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

Pure calculation tests cover the timestamp migration, duplicate records, unknown sensors, offline exclusion, time weighting, sampling gaps, office boundaries, heatmap reconciliation and room-fit evidence. Streamlit AppTest loads the full dashboard and compact briefing, and checks shared filters, the presentation switch, financial scope, synthetic feedback, the portrait dialog and simulation results. Actual live deployment, browser layout and mouse/keyboard dismissal need checking in the separate review app.

Deployment reference: https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/deploy
