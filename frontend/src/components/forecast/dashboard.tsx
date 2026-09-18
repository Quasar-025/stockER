"use client";

import { useMemo } from "react";
import dynamic from "next/dynamic";
import { ForecastResponse, ImpactForecast, SimilarEvent, CausalPath } from "@/lib/api";

const ForceGraph2D = dynamic(() => import("react-force-graph-2d"), { ssr: false });

export function ForecastCard({ impact }: { impact: ImpactForecast }) {
  const prob = impact.direction_probability ?? 50;
  const conf = impact.model_confidence ?? 5;
  const samples = impact.sample_count || 0;
  const horizon = impact.time_horizon_days || 30;
  
  return (
    <article className="card">
      <p>Horizon · {horizon}d</p>
      <h3 title={impact.company_name || ""}>{impact.ticker} {impact.company_name ? <span style={{fontSize: '0.6em', color: '#888', fontWeight: 'normal'}}>{impact.company_name}</span> : ""}</h3>
      <div className="metrics">
        <span>Direction likelihood<strong>{prob}%</strong></span>
        <span>Model reliability<strong>{conf}%</strong></span>
      </div>
      <small>{samples} comparable observations {impact.insufficient_evidence ? "· insufficient historical evidence" : ""}</small>
    </article>
  );
}

export function EffectDecompositionPanel({ impact }: { impact: ImpactForecast | null }) {
  if (!impact) return null;
  const decomp = impact.decomposition;
  
  if (!decomp && impact.return_range) {
     return (
        <section className="panel">
          <h2>Return Range · {impact.ticker}</h2>
          <div className="effect"><span>25th Percentile</span><i /><b>{impact.return_range.p25}%</b></div>
          <div className="effect"><span>Median (50th)</span><i /><b>{impact.return_range.p50}%</b></div>
          <div className="effect"><span>75th Percentile</span><i /><b>{impact.return_range.p75}%</b></div>
          <small>Range of historical outcomes for similar events.</small>
        </section>
     );
  }
  
  if (!decomp) return null;
  
  return (
    <section className="panel">
      <h2>Effect decomposition · {impact.ticker}</h2>
      {["direct_event", "sector", "market", "competitive", "residual"].map((name) => (
        <div className="effect" key={name}>
          <span>{name.replace("_", " ")}</span>
          <i />
          <b>{((decomp[name] || 0) * 100).toFixed(2)}%</b>
        </div>
      ))}
      <small>Channels remain separate; zero means unknown here, not no risk.</small>
    </section>
  );
}

export function EntityImpactTable({ impacts }: { impacts: ImpactForecast[] }) { 
  return (
    <section className="panel">
      <h2>Entity impact ledger</h2>
      <table>
        <thead>
          <tr><th>Entity</th><th>Horizon</th><th>Likelihood</th><th>Reliability</th><th>Sample</th><th>State</th></tr>
        </thead>
        <tbody>
          {impacts.map((item, i) => {
            const prob = item.direction_probability ?? 50;
            const conf = item.model_confidence ?? 5;
            const sampleCount = item.sample_count || 0;
            const state = sampleCount > 5 ? "Robust" : sampleCount > 0 ? "Sparse" : "Insufficient evidence";
            return (
              <tr key={`${item.ticker}-${item.time_horizon_days}-${i}`}>
                <th>{item.ticker} {item.company_name ? <span style={{fontSize: '0.8em', color: '#888'}}>{item.company_name}</span> : ""}</th>
                <td>{item.time_horizon_days}d</td>
                <td>{prob}%</td>
                <td>{conf}%</td>
                <td>{item.sample_count || 0}</td>
                <td>{state}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </section>
  ); 
}

export function EvidencePanel({ similarEvents, explanation }: { similarEvents: SimilarEvent[], explanation?: string }) { 
  return (
    <section className="panel">
      <h2>Historical evidence & Explanation</h2>
      {explanation && <p style={{marginBottom: "1rem", fontStyle: "italic"}}>{explanation}</p>}
      <div className="columns">
        <p><b>Supporting Events</b><br />
          {similarEvents?.length > 0 ? similarEvents.map((e, i) => {
            // similar_events inside forecast contain EventOntologySchema
            const title = e.title || e.event_title || "Unknown event";
            return <span key={i}>• {title}<br/></span>;
          }) : "No empirical observations loaded."}
        </p>
      </div>
    </section>
  ); 
}

export function DataHealthStatus({ sampleSize }: { sampleSize: number }) { 
  return (
    <section className="panel">
      <h2>Data health</h2>
      <ul>
        <li>Providers <b>{sampleSize > 0 ? "Available" : "Unavailable"}</b></li>
        <li>Historical outcomes <b>{sampleSize > 0 ? "Collected" : "Uncollected"}</b></li>
        <li>Graph <b>Approximate</b></li>
      </ul>
    </section>
  ); 
}

// Graph Interfaces
interface GraphNode {
  id: string;
  name: string;
  color: string;
  val: number;
  x?: number;
  y?: number;
  __bckgDimensions?: number[];
}

interface GraphLink {
  source: string;
  target: string;
  name: string;
}

export function CausalGraphPanel({ causalPaths, event, impacts }: { causalPaths?: CausalPath[], event?: Record<string, unknown>, impacts: ImpactForecast[] }) {
  const graphData = useMemo(() => {
    const nodes = new Map<string, GraphNode>();
    const links: GraphLink[] = [];

    if (!causalPaths || causalPaths.length === 0) {
      // Fallback: build a star graph from the event to the affected tickers
      const eventId = (event?.title as string) || "Event";
      nodes.set(eventId, { id: eventId, name: eventId, color: "#ff6600", val: 3 });
      
      impacts.forEach(impact => {
        nodes.set(impact.ticker, { id: impact.ticker, name: impact.ticker, color: "#00ffcc", val: 1 });
        links.push({
          source: eventId,
          target: impact.ticker,
          name: "AFFECTS"
        });
      });
    } else {
      causalPaths.forEach(path => {
        const tickers = path.path_tickers || [];
        const rels = path.path_rels || [];
        
        for (let i = 0; i < tickers.length; i++) {
          const t = tickers[i];
          if (!nodes.has(t)) {
            nodes.set(t, { id: t, name: t, color: "#00ffcc", val: 1 });
          }
          
          if (i < rels.length) {
            links.push({
              source: t,
              target: tickers[i+1],
              name: rels[i]
            });
          }
        }
      });
    }
    
    return {
      nodes: Array.from(nodes.values()),
      links: links
    };
  }, [causalPaths, event, impacts]);

  if (graphData.nodes.length === 0) return null;

  return (
    <section className="panel" style={{gridColumn: '1 / -1', minHeight: '400px'}}>
      <h2>Causal Graph</h2>
      <div style={{ height: '350px', width: '100%', border: '1px solid #333', borderRadius: '4px', overflow: 'hidden' }}>
        <ForceGraph2D
          graphData={graphData}
          width={800}
          height={350}
          nodeLabel="name"
          nodeColor={(node: object) => (node as GraphNode).color || "#00ffcc"}
          nodeVal={(node: object) => (node as GraphNode).val || 1}
          nodeCanvasObject={(node: object, ctx, globalScale) => {
            const graphNode = node as GraphNode;
            const label = graphNode.name;
            const fontSize = 12 / globalScale;
            ctx.font = `${fontSize}px Sans-Serif`;
            const textWidth = ctx.measureText(label).width;
            const bckgDimensions = [textWidth, fontSize].map(n => n + fontSize * 0.2);

            ctx.fillStyle = 'rgba(20, 20, 30, 0.8)';
            if (graphNode.x !== undefined && graphNode.y !== undefined) {
              ctx.fillRect(graphNode.x - bckgDimensions[0] / 2, graphNode.y - bckgDimensions[1] / 2, bckgDimensions[0], bckgDimensions[1]);
            }

            ctx.textAlign = 'center';
            ctx.textBaseline = 'middle';
            ctx.fillStyle = graphNode.color || '#00ffcc';
            if (graphNode.x !== undefined && graphNode.y !== undefined) {
              ctx.fillText(label, graphNode.x, graphNode.y);
            }

            graphNode.__bckgDimensions = bckgDimensions;
          }}
          nodePointerAreaPaint={(node: object, color, ctx) => {
            const graphNode = node as GraphNode;
            ctx.fillStyle = color;
            const bckgDimensions = graphNode.__bckgDimensions;
            if (bckgDimensions && graphNode.x !== undefined && graphNode.y !== undefined) {
              ctx.fillRect(graphNode.x - bckgDimensions[0] / 2, graphNode.y - bckgDimensions[1] / 2, bckgDimensions[0], bckgDimensions[1]);
            }
          }}
          linkColor={() => "#555"}
          linkDirectionalArrowLength={3.5}
          linkDirectionalArrowRelPos={1}
          linkCurvature={0.25}
          d3VelocityDecay={0.3}
          cooldownTicks={100}
          onEngineStop={() => {}}
        />
      </div>
    </section>
  );
}

export function Dashboard({ data }: { data?: ForecastResponse | null }) { 
  if (!data) return null;
  
  const impacts = data.forecasts || data.impact_forecasts || [];
  const primaryImpact = impacts[0] || null;
  const sampleSize = primaryImpact?.sample_count || primaryImpact?.historical_sample_size || 0;

  return (
    <>
      <section className="cards">
        {impacts.slice(0, 4).map((impact: ImpactForecast, i: number) => (
          <ForecastCard impact={impact} key={`${impact.ticker as string}-${i}`} />
        ))}
      </section>
      
      <section className="two">
        <EffectDecompositionPanel impact={primaryImpact} />
      </section>
      
      <EntityImpactTable impacts={impacts} />
      
      {impacts.length > 0 && (
         <CausalGraphPanel causalPaths={data.causal_paths} event={data.event} impacts={impacts} />
      )}
      
      <section className="two">
        <EvidencePanel similarEvents={primaryImpact?.similar_events || data.similar_events || []} explanation={data.explanation} />
        <DataHealthStatus sampleSize={sampleSize} />
      </section>
    </>
  ); 
}
