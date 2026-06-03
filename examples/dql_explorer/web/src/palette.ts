/*
  Chart colors, kept in a component-free module. React Fast Refresh only works
  for modules that export components and nothing else; exporting these value
  constants from charts.tsx made Vite fall back to a full reload on every edit
  (and could briefly leave importers seeing `PALETTE` as undefined). Keeping them
  here lets charts.tsx hot-reload cleanly.
*/

export const PALETTE = [
  "#3b82f6", // blue
  "#f97316", // orange
  "#10b981", // emerald
  "#a855f7", // purple
  "#ef4444", // red
  "#eab308", // yellow
  "#06b6d4", // cyan
  "#ec4899", // pink
  "#84cc16", // lime
  "#6366f1", // indigo
  "#14b8a6", // teal
  "#94a3b8", // slate (Other / fallback)
];

export const TYPE_COLORS = { "M&A": "#3b82f6", IPO: "#10b981" } as const;
