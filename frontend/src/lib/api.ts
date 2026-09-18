export const API_BASE = "http://localhost:8000/api";

export interface ForecastRequest {
  title: string;
  description: string;
  affected_tickers?: string[];
}

export interface ReturnRange {
  p25: number;
  p50: number;
  p75: number;
}

export interface ImpactForecast {
  ticker: string;
  company_name?: string | null;
  horizon?: number;
  time_horizon_days?: number;
  predicted_impact_pct?: number | null;
  direction_probability?: number | null;
  direction?: "up" | "down" | "neutral";
  model_confidence?: number | null;
  reliability_score?: number | null;
  regime?: string;
  historical_sample_size?: number;
  sample_count?: number;
  insufficient_evidence?: boolean;
  decomposition?: Record<string, number>;
  return_range?: ReturnRange;
  similar_events?: SimilarEvent[];
}

export interface CausalPath {
  path_tickers?: string[];
  path_rels?: string[];
}

export interface SimilarEvent {
  title?: string;
  event_title?: string;
  [key: string]: unknown;
}

export interface ForecastResponse {
  forecast_id?: string;
  event?: Record<string, unknown>;
  similar_events?: SimilarEvent[];
  impact_forecasts?: ImpactForecast[];
  forecasts?: ImpactForecast[];
  causal_paths?: CausalPath[];
  explanation?: string;
}

export async function generateForecast(data: ForecastRequest): Promise<ForecastResponse> {
  const res = await fetch(`${API_BASE}/forecast`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(data),
  });

  if (!res.ok) {
    throw new Error(`API error: ${res.statusText}`);
  }

  return res.json();
}

export interface EventRecord {
  id: string;
  title: string;
  description?: string;
  category?: string;
  affected_tickers?: string[];
  [key: string]: unknown;
}

export interface EventsResponse {
  events: EventRecord[];
}

export async function getEvents(): Promise<EventsResponse> {
  const res = await fetch(`${API_BASE}/events`, {
    method: "GET",
  });
  if (!res.ok) {
    throw new Error(`API error: ${res.statusText}`);
  }
  return res.json();
}
