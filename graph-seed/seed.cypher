// StockER v2 demo graph. This is source-labelled bootstrap topology, not a
// learned predictive model. Every strength is a direction-neutral cold-start
// prior; rigorous PIT evaluation excludes temporal approximations.
// Run with: cypher-shell -u neo4j -p "$NEO4J_PASSWORD" -f graph-seed/seed.cypher

CREATE CONSTRAINT company_ticker IF NOT EXISTS FOR (c:Company) REQUIRE c.ticker IS UNIQUE;
CREATE INDEX company_name_idx IF NOT EXISTS FOR (c:Company) ON (c.name);

MERGE (:Company {ticker: 'TSM', name: 'Taiwan Semiconductor Manufacturing'})
MERGE (:Company {ticker: 'NVDA', name: 'NVIDIA'})
MERGE (:Company {ticker: 'AAPL', name: 'Apple'})
MERGE (:Company {ticker: 'AMD', name: 'Advanced Micro Devices'})
MERGE (:Company {ticker: 'MSFT', name: 'Microsoft'})
MERGE (:Company {ticker: 'ORCL', name: 'Oracle'})
MERGE (:Company {ticker: '005930.KS', name: 'Samsung Electronics'})
MERGE (:Company {ticker: 'SOXX', name: 'iShares Semiconductor ETF'});

MATCH (tsm:Company {ticker:'TSM'}), (nvda:Company {ticker:'NVDA'})
MERGE (tsm)-[:SUPPLIES {
  channel_type:'SUPPLY_EXPOSURE', strength:0.15, dependency_exposure:0.75, substitutability:0.25,
  historical_observation_count:0, estimation_method:'manual_prior', is_prior:true,
  typical_time_lag_days:7, min_lag_days:5, max_lag_days:21,
  relationship_created_at:datetime('2024-01-01T00:00:00Z'), relationship_verified_at:null,
  source_date:datetime('2024-01-01T00:00:00Z'), temporal_approximation:true,
  confidence:0.55, evidence_count:1,
  evidence_sources:['https://investor.nvidia.com/financial-info/annual-reports-and-proxies/default.aspx'], verification_status:'approximate'
}]->(nvda);

MATCH (tsm:Company {ticker:'TSM'}), (aapl:Company {ticker:'AAPL'})
MERGE (tsm)-[:SUPPLIES {
  channel_type:'SUPPLY_EXPOSURE', strength:0.15, dependency_exposure:0.60, substitutability:0.35,
  historical_observation_count:0, estimation_method:'manual_prior', is_prior:true,
  typical_time_lag_days:14, min_lag_days:12, max_lag_days:28,
  relationship_created_at:datetime('2024-01-01T00:00:00Z'), relationship_verified_at:null,
  source_date:datetime('2024-01-01T00:00:00Z'), temporal_approximation:true,
  confidence:0.55, evidence_count:1,
  evidence_sources:['https://investor.tsmc.com/english/annual-reports'], verification_status:'approximate'
}]->(aapl);

MATCH (tsm:Company {ticker:'TSM'}), (amd:Company {ticker:'AMD'})
MERGE (tsm)-[:SUPPLIES {
  channel_type:'SUPPLY_EXPOSURE', strength:0.15, dependency_exposure:0.70, substitutability:0.30,
  historical_observation_count:0, estimation_method:'manual_prior', is_prior:true,
  typical_time_lag_days:7, min_lag_days:5, max_lag_days:21,
  relationship_created_at:datetime('2024-01-01T00:00:00Z'), relationship_verified_at:null,
  source_date:datetime('2024-01-01T00:00:00Z'), temporal_approximation:true,
  confidence:0.55, evidence_count:1,
  evidence_sources:['https://ir.amd.com/financial-information/sec-filings'], verification_status:'approximate'
}]->(amd);

MATCH (nvda:Company {ticker:'NVDA'}), (msft:Company {ticker:'MSFT'})
MERGE (nvda)-[:SUPPLIES {
  channel_type:'SUPPLY_EXPOSURE', strength:0.15, dependency_exposure:0.45, substitutability:0.45,
  historical_observation_count:0, estimation_method:'manual_prior', is_prior:true,
  typical_time_lag_days:21, min_lag_days:19, max_lag_days:35,
  relationship_created_at:datetime('2024-01-01T00:00:00Z'), relationship_verified_at:null,
  source_date:datetime('2024-01-01T00:00:00Z'), temporal_approximation:true,
  confidence:0.55, evidence_count:1,
  evidence_sources:['https://www.microsoft.com/en-us/annualreports'], verification_status:'approximate'
}]->(msft);

MATCH (msft:Company {ticker:'MSFT'}), (orcl:Company {ticker:'ORCL'})
MERGE (msft)-[:COMPETES_WITH {
  channel_type:'SUBSTITUTION', strength:0.15, dependency_exposure:0.35, substitutability:0.60,
  historical_observation_count:0, estimation_method:'manual_prior', is_prior:true,
  typical_time_lag_days:30, min_lag_days:28, max_lag_days:60,
  relationship_created_at:datetime('2024-01-01T00:00:00Z'), relationship_verified_at:null,
  source_date:datetime('2024-01-01T00:00:00Z'), temporal_approximation:true,
  confidence:0.55, evidence_count:1,
  evidence_sources:['https://www.oracle.com/corporate/investor-relations/financials/'], verification_status:'approximate'
}]->(orcl);

MATCH (amd:Company {ticker:'AMD'}), (nvda:Company {ticker:'NVDA'})
MERGE (amd)-[:COMPETES_WITH {
  channel_type:'SUBSTITUTION', strength:0.15, dependency_exposure:0.55, substitutability:0.65,
  historical_observation_count:0, estimation_method:'manual_prior', is_prior:true,
  typical_time_lag_days:14, min_lag_days:12, max_lag_days:28,
  relationship_created_at:datetime('2024-01-01T00:00:00Z'), relationship_verified_at:null,
  source_date:datetime('2024-01-01T00:00:00Z'), temporal_approximation:true,
  confidence:0.55, evidence_count:1,
  evidence_sources:['https://ir.amd.com/financial-information/sec-filings'], verification_status:'approximate'
}]->(nvda);

MATCH (tsm:Company {ticker:'TSM'}), (samsung:Company {ticker:'005930.KS'})
MERGE (tsm)-[:COMPETES_WITH {
  channel_type:'SUBSTITUTION', strength:0.15, dependency_exposure:0.45, substitutability:0.50,
  historical_observation_count:0, estimation_method:'manual_prior', is_prior:true,
  typical_time_lag_days:30, min_lag_days:28, max_lag_days:60,
  relationship_created_at:datetime('2024-01-01T00:00:00Z'), relationship_verified_at:null,
  source_date:datetime('2024-01-01T00:00:00Z'), temporal_approximation:true,
  confidence:0.55, evidence_count:1,
  evidence_sources:['https://images.samsung.com/is/content/samsung/assets/global/ir/docs/2024_Annual_Report.pdf'], verification_status:'approximate'
}]->(samsung);

// Context only: this edge must never be traversed as a causal path.
MATCH (tsm:Company {ticker:'TSM'}), (soxx:Company {ticker:'SOXX'})
MERGE (tsm)-[:CORRELATED_WITH {
  channel_type:'COMMON_FACTOR', strength:0.15, dependency_exposure:0.0, substitutability:0.0,
  historical_observation_count:0, estimation_method:'manual_prior', is_prior:true,
  typical_time_lag_days:0, min_lag_days:0, max_lag_days:0,
  relationship_created_at:datetime('2024-01-01T00:00:00Z'), relationship_verified_at:null,
  source_date:datetime('2024-01-01T00:00:00Z'), temporal_approximation:true,
  confidence:0.55, evidence_count:1,
  evidence_sources:['https://www.ishares.com/us/products/239705/ishares-phlx-semiconductor-etf'], verification_status:'approximate'
}]->(soxx);
