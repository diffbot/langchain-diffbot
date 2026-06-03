/* Mirrors the JSON returned by the FastAPI backend (`POST /api/query`). */

export interface Column {
  path: string;
  label: string;
}

export interface Step {
  tool: string;
  args: Record<string, unknown>;
  output: string;
}

export interface QueryResponse {
  question: string;
  entity_type: string;
  dql: string;
  notes: string | null;
  columns: Column[];
  rows: Array<Record<string, string>>;
  hits: number;
  steps: Step[];
  trace_url: string | null;
  error: string | null;
}

/* ---- Dashboard (`POST /api/dashboard`) ---- */

export interface DashboardRequest {
  min_employees: number;
  date_from: string;
  date_to: string;
}

export interface IndustryRow {
  industry: string;
  "M&A": number;
  IPO: number;
  total: number;
}

export interface CountryRow {
  country: string;
  "M&A": number;
  IPO: number;
  total: number;
}

export interface ExchangeRow {
  exchange: string;
  "M&A": number;
  IPO: number;
  total: number;
}

export interface MonthRow {
  month: string;
  ma: number;
  ipo: number;
  total: number;
}

export interface DealEvent {
  type: "M&A" | "IPO";
  name: string | null;
  date: string | null;
  industry: string;
  country: string;
  employees: number | null;
  amount_usd: number | null;
  exchange: string | null;
  counterparty: string | null;
}

export interface DashboardResponse {
  min_employees: number;
  date_from: string;
  date_to: string;
  totals: {
    events: number;
    ma: number;
    ipo: number;
    deal_value_usd: number;
    fetched: number;
    is_sample: boolean;
  };
  by_industry: IndustryRow[];
  by_month: MonthRow[];
  by_country: CountryRow[];
  by_exchange: ExchangeRow[];
  top_deals: DealEvent[];
  events: DealEvent[];
  queries: { ma?: string; ipo?: string };
  error: string | null;
}
