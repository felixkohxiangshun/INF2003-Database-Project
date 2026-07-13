// M3 Cypher — CRUD Operations
// Parameters use $param_name style (neo4j Python driver)


MERGE (u:User {user_id: $user_id})
SET u.username = $username;

MERGE (a:Artist {artist_id: $artist_id})
SET a.name = $name;

// genre moved here from Artist (see graph_schema.md)
MERGE (t:Track {track_id: $track_id})
SET t.title = $title,
    t.genre = $genre;


MATCH (t:Track {track_id: $track_id})
MATCH (a:Artist {artist_id: $artist_id})
MERGE (t)-[:PERFORMED_BY]->(a);

MATCH (u:User {user_id: $user_id})
MATCH (a:Artist {artist_id: $artist_id})
MERGE (u)-[r:FOLLOWS]->(a)
SET r.followed_at = $followed_at;

MATCH (u:User {user_id: $user_id})-[r:FOLLOWS]->(a:Artist {artist_id: $artist_id})
DELETE r;

// MERGE so replaying a track updates the edge instead of duplicating it
MATCH (u:User {user_id: $user_id})
MATCH (t:Track {track_id: $track_id})
MERGE (u)-[r:LISTENED_TO]->(t)
ON CREATE SET r.count = 1, r.last_played = datetime()
ON MATCH  SET r.count = r.count + 1, r.last_played = datetime();


MATCH (u:User {user_id: $user_id})-[r:LISTENED_TO]->(t:Track {track_id: $track_id})
SET r.count = r.count + 1, r.last_played = datetime();


MATCH (a:Artist {name: $artist_name})<-[:PERFORMED_BY]-(t:Track)
RETURN t.title;


MATCH (u:User {user_id: $user_id})
DETACH DELETE u;
