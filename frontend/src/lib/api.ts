const API_BASE = "http://localhost:8000/api";

export interface ForecastRequest {
  title: string;
  description: string;
  affected_tickers?: string[];
}

export interface ImpactForecast {
  ticker: string;
  company_name?: string | null;
  horizon: number;
  predicted_impact_pct: number | null;
  direction_probability: number | null;
  direction: "up" | "down" | "neutral";
  model_confidence: number | null;
  reliability_score: number | null;
  regime: string;
  historical_sample_size: number;
  decomposition: Record<string, unknown>;
}

export interface ForecastResponse {
  forecast_id: string;
  event: Record<string, unknown>;
  similar_events: Record<string, unknown>[];
  impact_forecasts: ImpactForecast[];
  causal_paths?: Record<string, unknown>[];
  explanation: string;
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

export async function getEvents(): Promise<Record<string, unknown>> {
  const res = await fetch(`${API_BASE}/events`, {
    method: "GET",
  });
  if (!res.ok) {
    throw new Error(`API error: ${res.statusText}`);
  }
  return res.json();
}
