# NoShowShield — the appointment no-show rescue desk

A clinic's most expensive problem is the empty chair. About one in five booked
slots never shows up: the specialist hour that could have gone to the waitlist,
the procedure room sitting idle, the front desk spending the morning on
reactive rebooking. Most small practices fight this with blunt tools — the same
reminder blast to everyone, or nothing at all — because they can't see *which*
appointments are actually at risk before the day starts.

NoShowShield is a morning rescue desk for clinics, salons, and SME service
businesses. Feed it the week's appointment book and it scores every appointment
0–100 for no-show risk, then hands the front desk a prioritized rescue list:
who to phone today, who goes into the confirmation-SMS batch, and which
high-value slots deserve a deposit nudge or an overbooking buffer. Every action
is a human-gated draft — nothing is ever sent automatically.

## How the risk score works (measured, not guessed)

The engine is a deterministic additive-logit model — zero LLM calls. Each
appointment is featurized (booking lead time × age band, subsidized-care flag,
whether an automated SMS was already sent, gender, day of week, plus an
optional clinic-configured catchment-hotspot prior) and each feature value
carries a log-odds weight **measured from 110,527 real appointments** in the
Kaggle *Medical Appointment No Shows* corpus (Joni Hoppen / Aquarela Analytics,
2016). Weights are summed onto the corpus baseline logit, squashed to a
no-show probability p, and scaled to a 0–100 risk index:

```
score = min(100, floor(100 * p / P99 + 0.5))
```

P99 is the 99th percentile of predicted p on the training split, so a score of
100 means "top-1% predicted risk in the corpus". The scaling is disclosed, not
hidden: the score is a relative-risk index, and per-segment calibration on a
held-out 20% of the corpus is published below and in the app's Method tab.

Key measured findings (all from the corpus, 80% train split):

- **Lead time dominates.** Same-day bookings no-show at 6.65%; bookings made
  31+ days out no-show at 33.02%.
- **Age matters.** 18–29 is the worst band (24.65%); 60–74 the best (15.04%).
- **The SMS paradox, reported honestly.** Appointments flagged `SMS_received=1`
  no-show at 27.57% vs 16.70% for `SMS_received=0`. That is almost certainly a
  selection effect (clinics text the patients they already worry about), so the
  model keeps the measured positive weight instead of hand-tuning it away.
- Subsidized-care flag: 23.74% vs 19.81%. Gender: negligible (F 20.31%, M 19.97%).
- Day of week: mild spread (Thu 19.35% … Fri 21.23%); Saturdays are rare (n=39).
- One corrupt row (Age = −1) excluded; Sundays have no corpus rows, so the
  Sunday weight defaults to 0.

**Hold-out calibration** (20% of corpus, deterministic split by AppointmentID
hash; weights fit on the other 80%; base no-show rate 19.87%):

| Segment | Threshold | Observed no-show | n | Share |
|---|---|---|---|---|
| CRITICAL | ≥ 85 | 33.61% | 1,931 | 8.8% |
| ELEVATED | 55–84 | 29.35% | 6,156 | 27.9% |
| LOW | < 55 | 13.79% | 13,949 | 63.3% |

CRITICAL + ELEVATED capture 77% of the hold-out no-shows while covering 37% of
the book. The model is strongest at ruling *out* low-risk appointments.

The TypeScript scoring mirror in `web/src/rules.ts` implements the identical
algorithm; `data/test-vectors.json` keeps the Python engine and the browser
mirror in exact agreement (12 vectors covering all three segments and edge
cases like same-day bookings, age 0, Sundays, and unknown neighbourhoods).

## The seeded example book

The web app ships with a scored example book: 14 fictional appointments for a
fictional "Lakeshore Family Clinic, Toronto" for the week of Mon 2026-11-02.
Names, schedules, fees, and the Harbourfront catchment-hotspot flag are
invented for illustration. The risk math applied to them is the real measured
model. Headline numbers: 14 appointments, 50.0% high-risk, $1,460 of at-risk
revenue out of $2,815 scheduled, $966.50 expected no-show loss.

## Repo layout

```
src/noshowshield/      Python service layer: rules.py (deterministic engine),
                       nodes.py + graph.py (LangGraph StateGraph:
                       intake -> featurize -> score -> segment -> action -> gate)
web/                   TypeScript/React UI (Vite): rescue board, paste-an-appointment
                       tab (scores in the browser via the TS mirror), method & data tab
data/
  raw/                 the Kaggle corpus CSV (downloaded at build time)
  risk_tables.json     fitted log-odds weights + calibration metadata
  test-vectors.json    Python<->TS scoring contract
  outputs/             book.json, rescue.json, summary.json for the example book
  README-data.md       data provenance notes
scripts/build_noshowshield.py   end-to-end build: fetch -> fit -> seed -> score -> vectors
tests/                 pytest suite (15 tests)
```

## Run it

```bash
pip install -r requirements.txt        # langgraph, pytest
python scripts/build_noshowshield.py  # rebuild tables, book, outputs, vectors
python -m pytest tests/ -q

cd web && npm install && npm test && npm run build
```

Deploy the UI anywhere static: `firebase.json` points hosting at `web/dist`.

## What it is not

- Not a medical device, not a diagnosis tool. It ranks appointment slots by
  no-show likelihood so staff can prioritize outreach.
- Not automated messaging. All drafts are `pending_human`; the engine sends
  nothing, ever.
- The example book is fictional. The risk weights and calibration are measured
  on the real 2016 corpus and disclosed above.
