import { useState } from "react";
import BoardView from "./views/BoardView";
import PasteView from "./views/PasteView";
import DataView from "./views/DataView";
import "./styles.css";

const REPO_URL = "https://github.com/tidaaartorhem/ai-no-show-defender";

type Tab = "board" | "paste" | "data";

const TABS: { id: Tab; label: string }[] = [
  { id: "board", label: "Rescue board" },
  { id: "paste", label: "Paste an appointment" },
  { id: "data", label: "Method & data" },
];

export default function App() {
  const [tab, setTab] = useState<Tab>("board");

  return (
    <div className="app">
      <header className="header">
        <div>
          <h1><span className="mark">Ns</span>NoShowShield</h1>
          <p className="sub">
            An appointment no-show rescue desk for clinics. Every upcoming
            appointment is scored 0-100 for no-show risk with a disclosed
            additive-logit model, then ranked so front-desk staff call the
            riskiest patients first. Every action sits behind a hard human
            gate: nothing is ever sent automatically.
          </p>
          <div className="badges">
            <span className="badge neutral"><a href={REPO_URL} target="_blank" rel="noreferrer">GitHub repo</a></span>
            <span className="badge neutral">Zero LLM calls</span>
          </div>
        </div>
      </header>

      <div className="disclosure">
        <b>What is real, what is seeded.</b> The risk weights are measured
        from 110,527 real appointment rows in the Kaggle Medical Appointment
        No Shows corpus. The 14 appointments for "Lakeshore Family Clinic,
        Toronto" are invented for illustration and are never presented as a
        real clinic's records.
      </div>

      <div className="tabs">
        {TABS.map((t) => (
          <button key={t.id} className={tab === t.id ? "active" : ""} onClick={() => setTab(t.id)}>
            {t.label}
          </button>
        ))}
      </div>

      {tab === "board" && <BoardView />}
      {tab === "paste" && <PasteView />}
      {tab === "data" && <DataView />}

      <footer className="footer muted small">
        NoShowShield · Deterministic rules mirrored in Python and TypeScript,
        bit-for-bit · Zero LLM calls, no automatic sends.
      </footer>
    </div>
  );
}
