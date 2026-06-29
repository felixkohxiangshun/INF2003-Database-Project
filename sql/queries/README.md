# SQL Queries — M2 (SQL Developer)

Add your query files here. Suggested structure:

```
sql/queries/
├── crud_users.sql          # INSERT / SELECT / UPDATE / DELETE for users
├── crud_tracks.sql         # CRUD for tracks, albums, artists
├── crud_playlists.sql      # CRUD for playlists and playlist_tracks
├── nested_queries.sql      # Complex / nested queries
└── analysis.sql            # Optional: EXPLAIN ANALYZE performance tests
```

## Schema reference

All tables are in `sql/schema.sql`. Key relationships:

- `play_history(user_id, track_id)` — log a play here; trigger auto-updates `tracks.play_count`
- `playlist_tracks(playlist_id, track_id, position)` — junction table, position must be unique per playlist
- `user_follows_artist(user_id, artist_id)` — many-to-many follow graph used for artist recommendations

## Demo users (already seeded)

| email | username | password |
|-------|----------|----------|
| alice@example.com | alice | password123 |
| bob@example.com | bob | password123 |
| carol@example.com | carol | password123 |

## Suggested nested queries to implement

1. Top 5 most-played tracks per genre this month
2. Users on the Free plan who have played more than 20 tracks today
3. Artists followed by users who also follow a given artist (collaborative filter seed)
4. Playlists containing a track, ordered by number of followers of the playlist owner
