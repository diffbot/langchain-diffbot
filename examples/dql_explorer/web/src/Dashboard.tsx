import { useEffect, useRef, useState } from "react";
import { postDashboard } from "./api";
import { Donut, HBars, VBars } from "./charts";
import type { BarRow, Series, Slice } from "./charts";
import { PALETTE, TYPE_COLORS } from "./palette";
import type { DashboardResponse, DealEvent } from "./types";

const EMP_PRESETS = [0, 1000, 4000, 10000, 50000];
const RANGE_PRESETS: { label: string; days: number }[] = [
  { label: "1m", days: 31 },
  { label: "3m", days: 92 },
  { label: "6m", days: 183 },
  { label: "12m", days: 366 },
];

function isoDaysAgo(days: number): string {
  const d = new Date();
  d.setDate(d.getDate() - days);
  return d.toISOString().slice(0, 10);
}
function todayISO(): string {
  return new Date().toISOString().slice(0, 10);
}

function fmtUSD(v: number | null): string {
  if (!v) return "—";
  if (v >= 1e9) return `$${(v / 1e9).toFixed(1)}B`;
  if (v >= 1e6) return `$${Math.round(v / 1e6)}M`;
  return `$${v.toLocaleString()}`;
}

/* Collapse a per-type breakdown into donut slices: top 8 + an "Other" bucket. */
function toSlices(
  rows: { total: number }[],
  label: (r: any) => string,
): Slice[] {
  const top = rows.slice(0, 8);
  const rest = rows.slice(8).reduce((a, r) => a + r.total, 0);
  const slices: Slice[] = top.map((r, i) => ({
    label: label(r),
    value: r.total,
    color: PALETTE[i % PALETTE.length],
  }));
  if (rest > 0)
    slices.push({ label: "Other", value: rest, color: PALETTE[PALETTE.length - 1] });
  return slices;
}

const TYPE_SERIES: Series[] = [
  { key: "M&A", label: "M&A", color: TYPE_COLORS["M&A"] },
  { key: "IPO", label: "IPO", color: TYPE_COLORS.IPO },
];

export function Dashboard() {
  const [minEmployees, setMinEmployees] = useState(4000);
  const [dateFrom, setDateFrom] = useState(isoDaysAgo(92));
  const [dateTo, setDateTo] = useState(todayISO());
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [data, setData] = useState<DashboardResponse | null>(null);
  // Monotonic request id: only the latest in-flight query is allowed to write
  // state, so fast config changes can't land out of order.
  const reqId = useRef(0);

  // Re-query whenever any control changes (and once on mount). Debounced so
  // dragging the number field or editing a date doesn't fire a request per
  // keystroke; an invalid window (from > to) just waits for a valid one.
  useEffect(() => {
    if (dateFrom > dateTo) return;
    const handle = setTimeout(() => {
      const id = ++reqId.current;
      setLoading(true);
      setError(null);
      void postDashboard({
        min_employees: minEmployees,
        date_from: dateFrom,
        date_to: dateTo,
      })
        .then((res) => {
          if (id !== reqId.current) return; // superseded by a newer request
          setData(res);
          setError(res.error ?? null);
        })
        .catch((e) => {
          if (id !== reqId.current) return;
          setError(e instanceof Error ? e.message : String(e));
        })
        .finally(() => {
          if (id === reqId.current) setLoading(false);
        });
    }, 400);
    return () => clearTimeout(handle);
  }, [minEmployees, dateFrom, dateTo]);

  return (
    <div>
      <header className="mb-5">
        <h1 className="text-2xl font-semibold">M&amp;A / IPO Dashboard</h1>
        <p className="mt-1 max-w-prose text-slate-500 dark:text-slate-400">
          Recent acquisitions and IPOs from the Diffbot Knowledge Graph, broken
          down by industry, geography, and time. Tune the company-size floor and
          date window — the charts re-query the graph automatically.
        </p>
      </header>

      <Controls
        minEmployees={minEmployees}
        dateFrom={dateFrom}
        dateTo={dateTo}
        loading={loading}
        onMinEmployees={setMinEmployees}
        onDateFrom={setDateFrom}
        onDateTo={setDateTo}
      />

      {error && (
        <p className="mt-4 rounded-lg border border-red-300 bg-red-50 px-3 py-2.5 text-red-700 dark:border-red-900 dark:bg-red-950/50 dark:text-red-300">
          {error}
        </p>
      )}

      {loading && !data && (
        <p className="mt-6 text-slate-500 dark:text-slate-400">
          Querying the graph…
        </p>
      )}

      {data && !data.error && <DashboardView data={data} loading={loading} />}
    </div>
  );
}

function Controls(props: {
  minEmployees: number;
  dateFrom: string;
  dateTo: string;
  loading: boolean;
  onMinEmployees: (n: number) => void;
  onDateFrom: (s: string) => void;
  onDateTo: (s: string) => void;
}) {
  const {
    minEmployees,
    dateFrom,
    dateTo,
    loading,
    onMinEmployees,
    onDateFrom,
    onDateTo,
  } = props;

  const inputCls =
    "rounded-md border border-slate-300 bg-white px-2.5 py-1.5 text-sm outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-500/30 dark:border-slate-600 dark:bg-slate-800";

  return (
    <div className="flex flex-wrap items-end gap-x-6 gap-y-4 rounded-xl border border-slate-200 bg-slate-50/60 p-4 dark:border-slate-700 dark:bg-slate-800/40">
      <div>
        <label className="block text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
          Min. employees
        </label>
        <div className="mt-1.5 flex items-center gap-2">
          <input
            type="number"
            min={0}
            step={500}
            value={minEmployees}
            onChange={(e) => onMinEmployees(Number(e.target.value) || 0)}
            className={`${inputCls} w-28`}
          />
          <div className="flex gap-1">
            {EMP_PRESETS.map((n) => (
              <button
                key={n}
                type="button"
                onClick={() => onMinEmployees(n)}
                className={`rounded-full border px-2 py-0.5 text-xs ${
                  minEmployees === n
                    ? "border-blue-500 bg-blue-100 text-blue-700 dark:bg-blue-950 dark:text-blue-300"
                    : "border-slate-300 text-slate-500 hover:bg-slate-100 dark:border-slate-600 dark:text-slate-400 dark:hover:bg-slate-800"
                }`}
              >
                {n >= 1000 ? `${n / 1000}k` : n}
              </button>
            ))}
          </div>
        </div>
      </div>

      <div>
        <label className="block text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
          Date range
        </label>
        <div className="mt-1.5 flex flex-wrap items-center gap-2">
          <input
            type="date"
            value={dateFrom}
            max={dateTo}
            onChange={(e) => onDateFrom(e.target.value)}
            className={inputCls}
          />
          <span className="text-slate-400">→</span>
          <input
            type="date"
            value={dateTo}
            min={dateFrom}
            max={todayISO()}
            onChange={(e) => onDateTo(e.target.value)}
            className={inputCls}
          />
          <div className="flex gap-1">
            {RANGE_PRESETS.map((p) => (
              <button
                key={p.label}
                type="button"
                onClick={() => {
                  onDateFrom(isoDaysAgo(p.days));
                  onDateTo(todayISO());
                }}
                className="rounded-full border border-slate-300 px-2 py-0.5 text-xs text-slate-500 hover:bg-slate-100 dark:border-slate-600 dark:text-slate-400 dark:hover:bg-slate-800"
              >
                {p.label}
              </button>
            ))}
          </div>
        </div>
      </div>

      <span
        className={`ml-auto flex items-center gap-2 text-sm text-slate-500 transition-opacity dark:text-slate-400 ${
          loading ? "opacity-100" : "opacity-0"
        }`}
      >
        <span className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-slate-300 border-t-blue-600 dark:border-slate-600 dark:border-t-blue-400" />
        Updating…
      </span>
    </div>
  );
}

function DashboardView({
  data,
  loading,
}: {
  data: DashboardResponse;
  loading: boolean;
}) {
  const { totals } = data;
  const industrySlices = toSlices(data.by_industry, (r) => r.industry);
  const monthRows: BarRow[] = data.by_month.map((m) => ({
    label: m.month.slice(2), // "2026-03" -> "26-03"
    values: { "M&A": m.ma, IPO: m.ipo },
  }));
  const countryRows: BarRow[] = data.by_country
    .slice(0, 8)
    .map((c) => ({ label: c.country, values: { "M&A": c["M&A"], IPO: c.IPO } }));
  const exchangeRows: BarRow[] = data.by_exchange
    .slice(0, 8)
    .map((e) => ({ label: e.exchange, values: { IPO: e.IPO } }));

  const empty = totals.events === 0;

  return (
    <div className={loading ? "opacity-60 transition-opacity" : ""}>
      <div className="mt-5 grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Stat label="Total events" value={totals.events.toLocaleString()} />
        <Stat label="Acquisitions" value={totals.ma.toLocaleString()} accent="#3b82f6" />
        <Stat label="IPOs" value={totals.ipo.toLocaleString()} accent="#10b981" />
        <Stat label="M&A deal value" value={fmtUSD(totals.deal_value_usd)} />
      </div>

      {totals.is_sample && (
        <p className="mt-2 text-xs text-slate-400">
          Charts roll up the {totals.fetched} most recent of {(totals.ma + totals.ipo).toLocaleString()} matching events.
        </p>
      )}

      {empty ? (
        <p className="mt-8 text-slate-500 dark:text-slate-400">
          No M&amp;A or IPO events match these filters. Lower the employee floor or
          widen the date range.
        </p>
      ) : (
        <>
          <div className="mt-6 grid gap-5 lg:grid-cols-2">
            <Card title="Events by industry">
              <Donut slices={industrySlices} total={totals.events} />
            </Card>
            <Card title="Events over time">
              <VBars rows={monthRows} series={TYPE_SERIES} />
            </Card>
            <Card title="Top countries">
              <HBars rows={countryRows} series={TYPE_SERIES} />
            </Card>
            <Card title="IPOs by stock exchange">
              {exchangeRows.length ? (
                <HBars
                  rows={exchangeRows}
                  series={[{ key: "IPO", label: "IPO", color: TYPE_COLORS.IPO }]}
                />
              ) : (
                <p className="text-sm text-slate-400">No IPOs in this window.</p>
              )}
            </Card>
          </div>

          {data.top_deals.length > 0 && (
            <Card title="Largest acquisitions" className="mt-5">
              <TopDeals deals={data.top_deals} />
            </Card>
          )}
        </>
      )}

      {(data.queries.ma || data.queries.ipo) && (
        <details className="mt-5 text-sm">
          <summary className="cursor-pointer text-slate-500 dark:text-slate-400">
            DQL behind this dashboard
          </summary>
          <pre className="mt-2 overflow-x-auto whitespace-pre-wrap rounded-lg border border-slate-200 bg-slate-50 p-4 font-mono text-[13px] leading-relaxed text-slate-800 dark:border-slate-700 dark:bg-slate-800/60 dark:text-slate-100">
            {`# Acquisitions\n${data.queries.ma ?? ""}\n\n# IPOs\n${data.queries.ipo ?? ""}`}
          </pre>
        </details>
      )}
    </div>
  );
}

function Stat({
  label,
  value,
  accent,
}: {
  label: string;
  value: string;
  accent?: string;
}) {
  return (
    <div className="rounded-xl border border-slate-200 p-4 dark:border-slate-700">
      <div
        className="text-2xl font-semibold tabular-nums"
        style={accent ? { color: accent } : undefined}
      >
        {value}
      </div>
      <div className="mt-0.5 text-xs uppercase tracking-wide text-slate-500 dark:text-slate-400">
        {label}
      </div>
    </div>
  );
}

function Card({
  title,
  children,
  className = "",
}: {
  title: string;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <section
      className={`rounded-xl border border-slate-200 p-4 dark:border-slate-700 ${className}`}
    >
      <h2 className="mb-4 text-sm font-semibold text-slate-600 dark:text-slate-300">
        {title}
      </h2>
      {children}
    </section>
  );
}

function TopDeals({ deals }: { deals: DealEvent[] }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full border-collapse text-sm">
        <thead>
          <tr className="text-left text-slate-500 dark:text-slate-400">
            <th className="border-b border-slate-200 px-2 py-1.5 font-medium dark:border-slate-700">
              Company
            </th>
            <th className="border-b border-slate-200 px-2 py-1.5 font-medium dark:border-slate-700">
              Industry
            </th>
            <th className="border-b border-slate-200 px-2 py-1.5 font-medium dark:border-slate-700">
              Acquirer
            </th>
            <th className="border-b border-slate-200 px-2 py-1.5 text-right font-medium dark:border-slate-700">
              Value
            </th>
            <th className="border-b border-slate-200 px-2 py-1.5 font-medium dark:border-slate-700">
              Date
            </th>
          </tr>
        </thead>
        <tbody>
          {deals.map((d, i) => (
            <tr key={i}>
              <td className="border-b border-slate-100 px-2 py-1.5 dark:border-slate-800">
                {d.name ?? "—"}
              </td>
              <td className="border-b border-slate-100 px-2 py-1.5 text-slate-500 dark:border-slate-800 dark:text-slate-400">
                {d.industry}
              </td>
              <td className="border-b border-slate-100 px-2 py-1.5 text-slate-500 dark:border-slate-800 dark:text-slate-400">
                {d.counterparty ?? "—"}
              </td>
              <td className="border-b border-slate-100 px-2 py-1.5 text-right tabular-nums dark:border-slate-800">
                {fmtUSD(d.amount_usd)}
              </td>
              <td className="border-b border-slate-100 px-2 py-1.5 tabular-nums text-slate-500 dark:border-slate-800 dark:text-slate-400">
                {d.date ?? "—"}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
