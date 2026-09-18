"use client";

import { useState, useEffect } from "react";
import { Dashboard } from "@/components/forecast/dashboard";
import { generateForecast, ForecastResponse, getEvents } from "@/lib/api";

export default function Home() {
  const [loading, setLoading] = useState(false);
  const [data, setData] = useState<ForecastResponse | null>(null);
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [tickers, setTickers] = useState("");
  
  const [pastEvents, setPastEvents] = useState<any[]>([]);

  useEffect(() => {
    getEvents().then(res => {
      if (res.events) setPastEvents(res.events);
    }).catch(console.error);
  }, []);

  const handleSelectEvent = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const ev = pastEvents.find(p => p.id === e.target.value);
    if (ev) {
      setTitle(ev.title || "");
      setDescription(ev.description || ev.category || "");
      setTickers(ev.affected_tickers ? ev.affected_tickers.join(", ") : "");
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!title) return;
    
    setLoading(true);
    try {
      const affected_tickers = tickers.split(",").map(t => t.trim()).filter(Boolean);
      const res = await generateForecast({
        title,
        description,
        affected_tickers
      });
      setData(res);
    } catch (err) {
      console.error(err);
      alert("Failed to generate forecast.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="dashboard">
      <header>
        <p>StockER v2</p>
        <h1>Probabilistic causal event forecasting</h1>
        <span>Live forecast engine</span>
      </header>

      <section className="panel" style={{ marginBottom: "2rem" }}>
        <div style={{display: "flex", justifyContent: "space-between", alignItems: "center"}}>
          <h2>Generate Forecast</h2>
          {pastEvents.length > 0 && (
            <select onChange={handleSelectEvent} style={{padding: "0.5rem", background: "#222", color: "white", border: "1px solid #444"}}>
              <option value="">-- Load past event (Auto Mode) --</option>
              {pastEvents.map(ev => (
                <option key={ev.id} value={ev.id}>{ev.title}</option>
              ))}
            </select>
          )}
        </div>
        
        <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: "1rem", marginTop: "1rem" }}>
          <div>
            <label style={{display: "block", marginBottom: "0.5rem"}}>Event Title (e.g., TSMC factories halted)</label>
            <input 
              type="text" 
              value={title} 
              onChange={e => setTitle(e.target.value)} 
              style={{width: "100%", padding: "0.5rem", background: "transparent", border: "1px solid #333", color: "white"}}
              required
            />
          </div>
          <div>
            <label style={{display: "block", marginBottom: "0.5rem"}}>Event Description</label>
            <textarea 
              value={description} 
              onChange={e => setDescription(e.target.value)} 
              style={{width: "100%", padding: "0.5rem", background: "transparent", border: "1px solid #333", color: "white", minHeight: "80px"}}
            />
          </div>
          <div>
            <label style={{display: "block", marginBottom: "0.5rem"}}>Directly Affected Tickers (comma separated, e.g., TSM)</label>
            <input 
              type="text" 
              value={tickers} 
              onChange={e => setTickers(e.target.value)} 
              style={{width: "100%", padding: "0.5rem", background: "transparent", border: "1px solid #333", color: "white"}}
            />
          </div>
          <button 
            type="submit" 
            disabled={loading}
            style={{padding: "0.75rem", background: "#333", color: "white", border: "none", cursor: loading ? "wait" : "pointer"}}
          >
            {loading ? "Forecasting..." : "Run Forecast"}
          </button>
        </form>
      </section>

      {data ? (
        <Dashboard data={data} />
      ) : (
        <div className="notice">
          <b>Awaiting input.</b> Enter a hypothetical scenario above or select a past event to generate a live market forecast.
        </div>
      )}
      
      <footer>Relationships are propagation channels, not direction rules. The system may return insufficient historical evidence.</footer>
    </main>
  );
}
