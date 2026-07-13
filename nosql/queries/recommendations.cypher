// M3 Cypher — Recommendation Queries


// 1. Collaborative filtering: tracks listened to by users who share
// listening history with the current user, excluding already-heard tracks.
MATCH (u:User {user_id: $user_id})-[:LISTENED_TO]->(t:Track)<-[:LISTENED_TO]-(similar:User)-[:LISTENED_TO]->(rec:Track)
WHERE NOT (u)-[:LISTENED_TO]->(rec) AND u <> similar
RETURN rec.title, rec.track_id, count(DISTINCT similar) AS score
ORDER BY score DESC
LIMIT 10;


// 2. Artist similarity: tracks from artists similar to those the user follows.
MATCH (u:User {user_id: $user_id})-[:FOLLOWS]->(a:Artist)-[:SIMILAR_TO]-(suggestedArtist:Artist)<-[:PERFORMED_BY]-(rec:Track)
WHERE NOT (u)-[:LISTENED_TO]->(rec)
RETURN rec.title, suggestedArtist.name, count(*) AS weight
ORDER BY weight DESC
LIMIT 5;


// 3. Seed SIMILAR_TO relationships: artists are similar if their tracks
// share a genre; similarity_score = number of shared genres.
// Run once after sync.py populates the graph.
MATCH (a1:Artist)<-[:PERFORMED_BY]-(t1:Track),
      (a2:Artist)<-[:PERFORMED_BY]-(t2:Track)
WHERE a1 <> a2
  AND t1.genre = t2.genre
  AND t1.genre IS NOT NULL
WITH a1, a2, count(DISTINCT t1.genre) AS shared_genres
WHERE shared_genres > 0
MERGE (a1)-[r:SIMILAR_TO]-(a2)
SET r.similarity_score = shared_genres;


// 4. Genre-based fallback: recommend tracks in the genres the user
// listens to most. Useful when there isn't enough history for
// collaborative filtering.
MATCH (u:User {user_id: $user_id})-[:LISTENED_TO]->(t:Track)
WITH u, t.genre AS genre, count(*) AS genre_plays
ORDER BY genre_plays DESC
LIMIT 3
MATCH (rec:Track {genre: genre})
WHERE NOT (u)-[:LISTENED_TO]->(rec)
RETURN rec.title, rec.track_id, genre, genre_plays AS genre_affinity
ORDER BY genre_plays DESC
LIMIT 10;
