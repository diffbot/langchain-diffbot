/*
  Tiny dependency-free SVG charts. The dashboard only needs a donut and a couple
  of bar shapes, so we hand-roll them rather than pull a charting library (and
  its React-version peer-dep dance) into an example app. Each chart is a pure
  function of its data and inherits text color from Tailwind via `currentColor`.

  Colors live in palette.ts, not here: React Fast Refresh only hot-reloads
  modules whose exports are all components, so this file exports components only.
*/

export interface Slice {
  label: string;
  value: number;
  color: string;
}

function polar(cx: number, cy: number, r: number, angle: number) {
  const a = (angle - 90) * (Math.PI / 180);
  return [cx + r * Math.cos(a), cy + r * Math.sin(a)];
}

function arc(cx: number, cy: number, r: number, start: number, end: number) {
  const [sx, sy] = polar(cx, cy, r, end);
  const [ex, ey] = polar(cx, cy, r, start);
  const large = end - start <= 180 ? 0 : 1;
  return `M ${sx} ${sy} A ${r} ${r} 0 ${large} 0 ${ex} ${ey}`;
}

/* Donut chart with a centered total and a legend of label / count / percent. */
export function Donut({ slices, total }: { slices: Slice[]; total: number }) {
  const sum = slices.reduce((acc, s) => acc + s.value, 0) || 1;
  const size = 180;
  const r = 70;
  const cx = size / 2;
  const cy = size / 2;
  let cursor = 0;

  return (
    <div className="flex flex-wrap items-center gap-5">
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} className="shrink-0">
        {slices.map((s) => {
          const sweep = (s.value / sum) * 360;
          const start = cursor;
          const end = cursor + sweep;
          cursor = end;
          // A single full slice can't be drawn as an arc; render a ring instead.
          if (sweep >= 359.999) {
            return (
              <circle
                key={s.label}
                cx={cx}
                cy={cy}
                r={r}
                fill="none"
                stroke={s.color}
                strokeWidth={22}
              />
            );
          }
          return (
            <path
              key={s.label}
              d={arc(cx, cy, r, start, end)}
              fill="none"
              stroke={s.color}
              strokeWidth={22}
            />
          );
        })}
        <text
          x={cx}
          y={cy - 4}
          textAnchor="middle"
          className="fill-current text-2xl font-semibold"
        >
          {total}
        </text>
        <text
          x={cx}
          y={cy + 16}
          textAnchor="middle"
          className="fill-slate-400 text-xs"
        >
          events
        </text>
      </svg>
      <ul className="min-w-[10rem] flex-1 space-y-1 text-sm">
        {slices.map((s) => (
          <li key={s.label} className="flex items-center gap-2">
            <span
              className="inline-block h-3 w-3 shrink-0 rounded-sm"
              style={{ backgroundColor: s.color }}
            />
            <span className="min-w-0 truncate" title={s.label}>
              {s.label}
            </span>
            <span className="ml-auto shrink-0 whitespace-nowrap tabular-nums text-slate-500 dark:text-slate-400">
              {s.value} · {Math.round((s.value / sum) * 100)}%
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}

export interface Series {
  key: string;
  label: string;
  color: string;
}

export interface BarRow {
  label: string;
  values: Record<string, number>;
}

/* Vertical stacked bars — used for the monthly M&A vs IPO timeline. */
export function VBars({ rows, series }: { rows: BarRow[]; series: Series[] }) {
  const max =
    Math.max(
      1,
      ...rows.map((r) => series.reduce((a, s) => a + (r.values[s.key] || 0), 0)),
    ) || 1;
  const plotH = 170; // pixels available for the tallest bar
  const labelH = 18; // headroom reserved for the value label above each bar

  return (
    <div>
      <div
        className="flex items-end gap-2 border-b border-slate-200 dark:border-slate-700"
        style={{ height: plotH + labelH }}
      >
        {rows.map((r) => {
          const stackTotal = series.reduce((a, s) => a + (r.values[s.key] || 0), 0);
          return (
            <div
              key={r.label}
              className="flex h-full flex-1 flex-col items-center justify-end"
              title={`${r.label}: ${stackTotal}`}
            >
              <span className="mb-1 text-xs tabular-nums text-slate-400">
                {stackTotal || ""}
              </span>
              {/* Outer height encodes the stack total; segments grow in proportion.
                  Series are reversed so the first DOM child is the top segment, which
                  takes the rounded top corners. */}
              <div
                className="flex w-full max-w-[2.75rem] flex-col"
                style={{ height: (stackTotal / max) * plotH }}
              >
                {[...series].reverse().map((s) => {
                  const v = r.values[s.key] || 0;
                  if (!v) return null;
                  return (
                    <div
                      key={s.key}
                      style={{ flexGrow: v, backgroundColor: s.color }}
                      className="min-h-[2px] first:rounded-t-sm"
                    />
                  );
                })}
              </div>
            </div>
          );
        })}
      </div>
      <div className="mt-1.5 flex gap-2">
        {rows.map((r) => (
          <div
            key={r.label}
            className="flex-1 text-center text-xs text-slate-500 dark:text-slate-400"
          >
            {r.label}
          </div>
        ))}
      </div>
      <Legend series={series} />
    </div>
  );
}

/* Horizontal stacked bars — used for country / exchange breakdowns (long labels). */
export function HBars({ rows, series }: { rows: BarRow[]; series: Series[] }) {
  const max =
    Math.max(
      1,
      ...rows.map((r) => series.reduce((a, s) => a + (r.values[s.key] || 0), 0)),
    ) || 1;

  return (
    <div>
      <ul className="space-y-2">
        {rows.map((r) => {
          const total = series.reduce((a, s) => a + (r.values[s.key] || 0), 0);
          return (
            <li key={r.label} className="text-sm">
              <div className="mb-0.5 flex justify-between gap-2">
                <span className="truncate" title={r.label}>
                  {r.label}
                </span>
                <span className="tabular-nums text-slate-500 dark:text-slate-400">
                  {total}
                </span>
              </div>
              <div className="flex h-3 overflow-hidden rounded-full bg-slate-100 dark:bg-slate-800">
                {series.map((s) => {
                  const v = r.values[s.key] || 0;
                  if (!v) return null;
                  return (
                    <div
                      key={s.key}
                      style={{
                        width: `${(v / max) * 100}%`,
                        backgroundColor: s.color,
                      }}
                      // Round the outer ends of the colored bar (left of the first
                      // segment, right of the last) so the data bar is pill-capped.
                      className="first:rounded-l-full last:rounded-r-full"
                    />
                  );
                })}
              </div>
            </li>
          );
        })}
      </ul>
      <Legend series={series} />
    </div>
  );
}

function Legend({ series }: { series: Series[] }) {
  return (
    <div className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-xs text-slate-500 dark:text-slate-400">
      {series.map((s) => (
        <span key={s.key} className="flex items-center gap-1.5">
          <span
            className="inline-block h-2.5 w-2.5 rounded-sm"
            style={{ backgroundColor: s.color }}
          />
          {s.label}
        </span>
      ))}
    </div>
  );
}
