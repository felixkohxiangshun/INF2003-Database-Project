// =============================================================
// M3 Cypher — CRUD Operations
// Project: Music Streaming Database
// Target DB: Neo4j 5+
// Parameters use $param_name style (neo4j Python driver)
// =============================================================


// -------------------------------------------------------------
// NODES — CREATE / MERGE
// -------------------------------------------------------------

// Create or update a User node
// [UNCHANGED]
MERGE (u:User {user_id: $user_id})
SET u.username = $username;

// Create or update an Artist node                [ADDED]
// Called by sync.py when syncing artists from PostgreSQL.
MERGE (a:Artist {artist_id: $artist_id})
SET a.name = $name;

// Create or update a Track node                  [ADDED]
// genre moved here from Artist (see graph_schema.md).
MERGE (t:Track {track_id: $track_id})
SET t.title = $title,
    t.genre = $genre;


// -------------------------------------------------------------
// RELATIONSHIPS — CREATE / MERGE
// -------------------------------------------------------------

// Link a Track to its Artist (PERFORMED_BY)      [ADDED]
// Run after both Track and Artist nodes exist.
MATCH (t:Track {track_id: $track_id})
MATCH (a:Artist {artist_id: $artist_id})
MERGE (t)-[:PERFORMED_BY]->(a);

// Create FOLLOWS relationship when user follows an artist  [ADDED]
MATCH (u:User {user_id: $user_id})
MATCH (a:Artist {artist_id: $artist_id})
MERGE (u)-[r:FOLLOWS]->(a)
SET r.followed_at = $followed_at;

// Delete FOLLOWS relationship when user unfollows an artist  [ADDED]
MATCH (u:User {user_id: $user_id})-[r:FOLLOWS]->(a:Artist {artist_id: $artist_id})
DELETE r;

// Create LISTENED_TO relationship on first play  [ADDED]
// Use MERGE so replaying a track updates rather than duplicates.
MATCH (u:User {user_id: $user_id})
MATCH (t:Track {track_id: $track_id})
MERGE (u)-[r:LISTENED_TO]->(t)
ON CREATE SET r.count = 1, r.last_played = datetime()
ON MATCH  SET r.count = r.count + 1, r.last_played = datetime();


// -------------------------------------------------------------
// RELATIONSHIPS — UPDATE
// -------------------------------------------------------------

// Update the play count and last played timestamp for a user's track
// [UNCHANGED — kept for explicit increment use case]
MATCH (u:User {user_id: $user_id})-[r:LISTENED_TO]->(t:Track {track_id: $track_id})
SET r.count = r.count + 1, r.last_played = datetime();


// -------------------------------------------------------------
// NODES — READ
// -------------------------------------------------------------

// Retrieve tracks performed by a specific Artist
// [UNCHANGED]
MATCH (a:Artist {name: $artist_name})<-[:PERFORMED_BY]-(t:Track)
RETURN t.title;


// -------------------------------------------------------------
// NODES — DELETE
// -------------------------------------------------------------

// Delete a User and all their relationships
// [UNCHANGED]
MATCH (u:User {user_id: $user_id})
DETACH DELETE u;
