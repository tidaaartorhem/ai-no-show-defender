import { tables } from "../rules";

const ORDER: ("CRITICAL" | "ELEVATED" | "LOW")[] = ["CRITICAL", "ELEVATED", "LOW"];

/** Method and data: what the model is, what it measured, what is invented. */
export default function DataView() {
  const meta = tables.meta;
  const calib = meta.calibration_holdout;
  const totalN = ORDER.reduce((acc, s) => acc + calib[s].n, 0);
  const baseRate =
    ORDER.reduce((acc, s) => acc + calib[s].observed_rate * calib[s].n, 0) / totalN;

  return (
    <div>
      <div className="card">
        <h2>The model, in plain language</h2>
        <p className="small">
          NoShowShield is an <b>additive logit</b> model. Each appointment is
          turned into five features: booking lead time crossed with age band,
          subsidized-care flag, whether an automated SMS was already received,
          gender, and day of week. Each feature value carries a weight
          measured as a log-odds ratio from the real appointment corpus. The
          weights are added to the corpus baseline logit ({" "}
          <span className="mono">{meta.baseline_logit}</span>), pushed through
          the sigmoid to get a no-show probability p, then rescaled:
        </p>
        <p className="small">
          <span className="mono">
            score = min(100, floor(100 * p / p99 + 0.5))
          </span>
        </p>
        <p className="small">
          P99 (<span className="mono">{meta.p99}</span>) is the 99th percentile
          of predicted probability across the {meta.train_n.toLocaleString()}{" "}
          training rows. So a score of 100 means the predicted probability
          sits at the top 1% of the corpus, and a score of 50 means half that.
          The score is a disclosed <b>relative-risk index</b>, not a raw
          probability. Zero LLM calls: every number on this page is arithmetic.
        </p>
      </div>

      <div className="card">
        <h2>Segment definitions</h2>
        <table className="table narrow">
          <thead>
            <tr>
              <th>Segment</th>
              <th>Score</th>
              <th>Rescue play</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td><b>CRITICAL</b></td>
              <td className="mono">85-100</td>
              <td>Call today: confirm, take a deposit, or release the slot</td>
            </tr>
            <tr>
              <td><b>ELEVATED</b></td>
              <td className="mono">55-84</td>
              <td>Confirmation SMS campaign</td>
            </tr>
            <tr>
              <td><b>LOW</b></td>
              <td className="mono">0-54</td>
              <td>Routine reminder</td>
            </tr>
          </tbody>
        </table>
      </div>

      <div className="card">
        <h2>Hold-out calibration</h2>
        <p className="small muted">
          Weights were fit on a deterministic 80% split; the observed no-show
          rates below were measured on the remaining 20% hold-out (
          {meta.test_n.toLocaleString()} rows).
        </p>
        <table className="table">
          <thead>
            <tr>
              <th>Segment</th>
              <th>Observed no-show rate</th>
              <th>n</th>
              <th>Share</th>
            </tr>
          </thead>
          <tbody>
            {ORDER.map((s) => (
              <tr key={s}>
                <td><b>{s}</b></td>
                <td className="mono">
                  {(calib[s].observed_rate * 100).toFixed(2)}%
                </td>
                <td className="mono">{calib[s].n.toLocaleString()}</td>
                <td className="mono">{(calib[s].share * 100).toFixed(1)}%</td>
              </tr>
            ))}
            <tr>
              <td><b>Overall base rate</b></td>
              <td className="mono">{(baseRate * 100).toFixed(2)}%</td>
              <td className="mono">{totalN.toLocaleString()}</td>
              <td className="mono">100.0%</td>
            </tr>
          </tbody>
        </table>
        <p className="small muted">{meta.calibration_note}</p>
      </div>

      <div className="card">
        <h2>Key findings from the corpus</h2>
        <ul className="small">
          <li>
            <b>Lead time dominates.</b> Same-day bookings no-show at 6.65%,
            while appointments booked 31+ days out no-show at 33.02%.
          </li>
          <li>
            <b>Age matters.</b> Ages 18-29 are the worst band at 24.65%
            no-show; ages 60-74 are the best at 15.04%.
          </li>
          <li>
            <b>The SMS paradox, reported honestly.</b> Patients flagged as
            having received an automated SMS no-show at 27.57%, versus 16.70%
            for those who did not. That is almost certainly a selection
            effect (clinics chase harder-to-reach patients with SMS), not
            proof that reminders cause no-shows. The model uses it as
            measured and discloses it here.
          </li>
          <li>
            <b>Gender effect is negligible.</b> The measured weights are
            +0.01 for F and -0.02 for M, close to zero.
          </li>
          <li>
            <b>One Age=-1 row excluded</b> from the corpus ({meta.excluded_rows}
            ).
          </li>
          <li>
            <b>Sunday has no corpus rows</b>, so its weekday weight defaults
            to 0 ({meta.sunday_note}).
          </li>
          <li>
            <b>Harbourfront hotspot +0.35 logit is clinic-configured</b>, not
            measured from the corpus: a prior for that catchment, added on
            top of the measured weights.
          </li>
        </ul>
      </div>

      <div className="card">
        <h2>Data source disclosure</h2>
        <p className="small">
          <b>Real.</b> The model weights and calibration come from the{" "}
          {meta.source}, {meta.corpus_n.toLocaleString()} rows of real
          appointment records, used under their published terms.
        </p>
        <p className="small">
          <b>Seeded.</b> The rescue board shows 14 appointments for a
          fictional "Lakeshore Family Clinic, Toronto". Names, schedules, and
          fees are invented for illustration and are never presented as a
          real clinic's records.
        </p>
        <p className="small">
          <b>Gate.</b> Every drafted action carries status{" "}
          <span className="mono">pending_human</span>. This page cannot send
          messages or calls, and nothing is ever sent automatically.
        </p>
      </div>
    </div>
  );
}
