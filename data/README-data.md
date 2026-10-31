# Data provenance — ai-no-show-defender

## Real data (risk math)

**Kaggle "Medical Appointment No Shows"** — collected by Joni Hoppen,
published by Aquarela Analytics (2016).
Source: https://raw.githubusercontent.com/ShivankYadav/No-show/master/noshowappointments-kagglev2-may-2016.csv
(also mirrored at `data/raw/noshowappointments-kagglev2-may-2016.csv`, 10.74 MB).

- 110,527 rows × 14 columns: PatientId, AppointmentID, Gender, ScheduledDay,
  AppointmentDay, Age, Neighbourhood, Scholarship, Hipertension, Diabetes,
  Alcoholism, Handcap, SMS_received, No-show (`Yes` = patient did NOT show up).
- Overall no-show rate: 20.19% (20.27% on the 80% train split).
- One row with Age = −1 excluded as corrupt; all other rows used.
- Deterministic 80/20 split by MD5(AppointmentID): weights fit on 80%
  (n=88,490), calibration measured on 20% (n=22,036).
- Neighbourhoods in the corpus are Vitória, Brazil. Because they do not
  transfer to a Toronto clinic, neighbourhood is NOT a measured feature. The
  model instead accepts a clinic-configured hotspot prior (+0.35 logit),
  which is clearly labeled as configured rather than measured wherever used.

## Seeded / fictional data (illustration only)

- `data/outputs/book.json`: 14 fictional appointments for a fictional
  "Lakeshore Family Clinic, Toronto", week of Mon 2026-11-02. Patient names,
  schedules, visit types, fees, and hotspot flags are invented.
- Visit fees (Specialist consult $220, Procedure $310, Follow-up $95,
  New patient intake $140, Screening $120, Minor procedure $420) are plausible
  fictional price points, not measured.
- `data/test-vectors.json`: 12 synthetic appointments used only as a
  Python↔TypeScript scoring contract. They carry no real patient data.

## Derived artifacts

- `data/risk_tables.json`: fitted log-odds weights per (lead_time × age_band)
  cell, scholarship, SMS_received, gender, weekday + baseline logit, P99
  scaling factor, segment thresholds, and hold-out calibration. Fully
  reproducible via `python scripts/build_noshowshield.py`.
- `data/outputs/rescue.json`, `summary.json`: engine output over the seeded
  book — prioritized rescue list and headline stats.
