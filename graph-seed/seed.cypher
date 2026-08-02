// Neo4j seed script — Initial graph population
// Run with: cat seed.cypher | cypher-shell -u neo4j -p stocker_dev

// ============================================================
// CONSTRAINTS & INDEXES
// ============================================================
CREATE CONSTRAINT company_ticker IF NOT EXISTS FOR (c:Company) REQUIRE c.ticker IS UNIQUE;
CREATE CONSTRAINT sector_name IF NOT EXISTS FOR (s:Sector) REQUIRE s.name IS UNIQUE;
CREATE CONSTRAINT country_name IF NOT EXISTS FOR (c:Country) REQUIRE c.name IS UNIQUE;
CREATE CONSTRAINT commodity_name IF NOT EXISTS FOR (c:Commodity) REQUIRE c.name IS UNIQUE;
CREATE CONSTRAINT indicator_name IF NOT EXISTS FOR (i:Indicator) REQUIRE i.name IS UNIQUE;

CREATE INDEX company_name_idx IF NOT EXISTS FOR (c:Company) ON (c.name);
CREATE INDEX sector_sub_idx IF NOT EXISTS FOR (s:Sector) ON (s.sub_sector);

// ============================================================
// SEED DATA — Will be populated in commit #25
// ============================================================
// Placeholder — S&P 500 companies, supply chain relationships,
// sector correlations, and commodity dependencies will be loaded
// from CSV files in this directory.
