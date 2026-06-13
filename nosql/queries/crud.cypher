// Create or update a User node
MERGE (u:User {user_id: $user_id})
SET u.username = $username;

// Retrieve tracks performed by a specific Artist
MATCH (a:Artist {name: $artist_name})<-[:PERFORMED_BY]-(t:Track)
RETURN t.title;

// Update the play count and last played timestamp for a user's track
MATCH (u:User {user_id: $user_id})-[r:LISTENED_TO]->(t:Track {track_id: $track_id})
SET r.count = r.count + 1, r.last_played = datetime();

// Delete a User and all their relationships
MATCH (u:User {user_id: $user_id})
DETACH DELETE u;