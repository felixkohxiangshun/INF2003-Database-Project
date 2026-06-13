// =============================================================
// Neo4j Setup — Constraints & Indexes
// Project: Music Streaming Database
// Run once before sync.py.
// Usage: paste into Neo4j Browser, or run via cypher-shell:
//   cypher-shell -u neo4j -p <password> -f nosql/setup.cypher
// =============================================================


// -------------------------------------------------------------
// UNIQUENESS CONSTRAINTS
// Ensures no duplicate nodes for the same entity and
// automatically creates a backing index for fast MERGE lookups.
// -------------------------------------------------------------

CREATE CONSTRAINT user_id_unique IF NOT EXISTS
FOR (u:User) REQUIRE u.user_id IS UNIQUE;

CREATE CONSTRAINT track_id_unique IF NOT EXISTS
FOR (t:Track) REQUIRE t.track_id IS UNIQUE;

CREATE CONSTRAINT artist_id_unique IF NOT EXISTS
FOR (a:Artist) REQUIRE a.artist_id IS UNIQUE;


// -------------------------------------------------------------
// ADDITIONAL INDEXES
// Speed up lookups that aren't covered by the unique constraints.
// -------------------------------------------------------------

// Genre lookups on Track (used by genre-based recommendations)
CREATE INDEX track_genre_index IF NOT EXISTS
FOR (t:Track) ON (t.genre);

// Artist name lookups (used in crud.cypher read by name)
CREATE INDEX artist_name_index IF NOT EXISTS
FOR (a:Artist) ON (a.name);
