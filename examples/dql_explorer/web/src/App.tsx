import { useState } from "react";
import { Ask } from "./Ask";
import { Dashboard } from "./Dashboard";
import { Explorer } from "./Explorer";

type Tab = "dashboard" | "explorer" | "ask";

const TABS: { id: Tab; label: string }[] = [
  { id: "dashboard", label: "M&A / IPO Dashboard" },
  { id: "explorer", label: "DQL Builder" },
  { id: "ask", label: "Ask Diffbot" },
];

export function App() {
  const [tab, setTab] = useState<Tab>("dashboard");
  // The dashboard is the landing tab and queries on mount, so it starts mounted;
  // we keep it mounted across tab switches to preserve its filters and results.
  const [dashboardSeen, setDashboardSeen] = useState(true);

  function select(t: Tab) {
    if (t === "dashboard") setDashboardSeen(true);
    setTab(t);
  }

  return (
    <div className="mx-auto max-w-5xl px-5 pb-16 pt-8">
      <nav className="mb-6 flex gap-1 border-b border-slate-200 dark:border-slate-700">
        {TABS.map((t) => (
          <button
            key={t.id}
            type="button"
            onClick={() => select(t.id)}
            className={`-mb-px border-b-2 px-4 py-2 text-sm font-medium transition-colors ${
              tab === t.id
                ? "border-blue-600 text-blue-600 dark:border-blue-400 dark:text-blue-400"
                : "border-transparent text-slate-500 hover:text-slate-800 dark:text-slate-400 dark:hover:text-slate-200"
            }`}
          >
            {t.label}
          </button>
        ))}
      </nav>

      {/* Keep each mounted so switching tabs preserves its state. */}
      <div className={tab === "explorer" ? "" : "hidden"}>
        <Explorer />
      </div>
      <div className={tab === "ask" ? "" : "hidden"}>
        <Ask />
      </div>
      {dashboardSeen && (
        <div className={tab === "dashboard" ? "" : "hidden"}>
          <Dashboard />
        </div>
      )}
    </div>
  );
}
