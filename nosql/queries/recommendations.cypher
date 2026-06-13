// Collaborative Filtering Recommendation:
// Find tracks listened to by users who listened to the same tracks as the current user,
// excluding tracks the current user has already listened to.

MATCH (u:User {user_id: $user_id})-[:LISTENED_TO]->(t:Track)<-[:LISTENED_TO]-(similar:User)-[:LISTENED_TO]->(rec:Track)
WHERE NOT (u)-[:LISTENED_TO]->(rec) AND u <> similar
RETURN rec.title, rec.track_id, count(DISTINCT similar) AS score
ORDER BY score DESC
LIMIT 10;

// Artist-based Recommendation:
// Recommend tracks from artists similar to those the user follows,
// excluding tracks the user has already listened to.

MATCH (u:User {user_id: $user_id})-[:FOLLOWS]->(a:Artist)-[:SIMILAR_TO]-(suggestedArtist:Artist)<-[:PERFORMED_BY]-(rec:Track)
WHERE NOT (u)-[:LISTENED_TO]->(rec)
RETURN rec.title, suggestedArtist.name, count(*) AS weight
ORDER BY weight DESC
LIMIT 5;