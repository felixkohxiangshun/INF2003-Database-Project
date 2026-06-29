-- =============================================================
-- M2 SQL Developer — Nested / Complex Queries
-- Project: Music Streaming Database
-- Target DB: PostgreSQL
-- Placeholder style: psycopg2 named parameters
--
-- API endpoints (backend/routes/insights.py):
--   Query 1 → GET /insights/top-by-genre      (Charts page)
--   Query 3 → GET /artists/<id>/related        (Artist page)
--   Query 6 → GET /playlists/<id>/completionists
--   Query 7 → GET /artists/top-performers
-- =============================================================

-- -------------------------------------------------------------
-- 1. TOP 5 MOST-PLAYED TRACKS PER GENRE THIS MONTH
-- Uses CTE + window function.
-- -------------------------------------------------------------
WITH monthly_track_plays AS (
    SELECT
        g.genre_id,
        g.name AS genre_name,
        t.track_id,
        t.title AS track_title,
        ar.name AS artist_name,
        COUNT(ph.history_id) AS plays_this_month
    FROM play_history ph
    JOIN tracks t ON t.track_id = ph.track_id
    JOIN albums al ON al.album_id = t.album_id
    JOIN artists ar ON ar.artist_id = al.artist_id
    LEFT JOIN genres g ON g.genre_id = t.genre_id
    WHERE ph.played_at >= date_trunc('month', CURRENT_DATE)
      AND ph.played_at <  date_trunc('month', CURRENT_DATE) + INTERVAL '1 month'
    GROUP BY g.genre_id, g.name, t.track_id, t.title, ar.name
), ranked AS (
    SELECT
        *,
        ROW_NUMBER() OVER (
            PARTITION BY genre_id
            ORDER BY plays_this_month DESC, track_title ASC
        ) AS genre_rank
    FROM monthly_track_plays
)
SELECT genre_name, genre_rank, track_id, track_title, artist_name, plays_this_month
FROM ranked
WHERE genre_rank <= 5
ORDER BY genre_name, genre_rank;

-- -------------------------------------------------------------
-- 2. FREE PLAN USERS WHO PLAYED MORE THAN 20 TRACKS TODAY
-- Uses HAVING to filter highly active users on a given day.
-- -------------------------------------------------------------
SELECT
    u.user_id,
    u.username,
    u.email,
    COUNT(ph.history_id) AS plays_today
FROM users u
JOIN play_history ph ON ph.user_id = u.user_id
WHERE ph.played_at >= CURRENT_DATE
  AND ph.played_at <  CURRENT_DATE + INTERVAL '1 day'
GROUP BY u.user_id, u.username, u.email
HAVING COUNT(ph.history_id) > 20
ORDER BY plays_today DESC;

-- -------------------------------------------------------------
-- 3. ARTISTS FOLLOWED BY USERS WHO ALSO FOLLOW A GIVEN ARTIST
-- Collaborative-filter seed: people who follow artist X also follow...
-- -------------------------------------------------------------
SELECT
    other_artist.artist_id,
    other_artist.name AS recommended_artist,
    COUNT(DISTINCT similar_user.user_id) AS shared_follower_count
FROM user_follows_artist seed_follow
JOIN user_follows_artist similar_user
     ON similar_user.user_id = seed_follow.user_id
JOIN artists other_artist
     ON other_artist.artist_id = similar_user.artist_id
WHERE seed_follow.artist_id = %(artist_id)s
  AND similar_user.artist_id <> %(artist_id)s
GROUP BY other_artist.artist_id, other_artist.name
ORDER BY shared_follower_count DESC, recommended_artist ASC
LIMIT 10;

-- -------------------------------------------------------------
-- 4. PLAYLISTS CONTAINING A TRACK, ORDERED BY OWNER POPULARITY
-- The schema has no playlist followers table, so owner popularity is
-- approximated by artist follows + total listening activity.
-- -------------------------------------------------------------
WITH owner_popularity AS (
    SELECT
        u.user_id,
        COUNT(DISTINCT ufa.artist_id) AS followed_artists,
        COUNT(DISTINCT ph.history_id) AS total_plays,
        COUNT(DISTINCT ufa.artist_id) + COUNT(DISTINCT ph.history_id) AS popularity_score
    FROM users u
    LEFT JOIN user_follows_artist ufa ON ufa.user_id = u.user_id
    LEFT JOIN play_history ph ON ph.user_id = u.user_id
    GROUP BY u.user_id
)
SELECT
    p.playlist_id,
    p.name AS playlist_name,
    p.is_public,
    u.user_id AS owner_id,
    u.username AS owner_username,
    op.followed_artists,
    op.total_plays,
    op.popularity_score
FROM playlist_tracks pt
JOIN playlists p ON p.playlist_id = pt.playlist_id
JOIN users u ON u.user_id = p.user_id
JOIN owner_popularity op ON op.user_id = u.user_id
WHERE pt.track_id = %(track_id)s
  AND p.is_public = TRUE
ORDER BY op.popularity_score DESC, p.created_at DESC;

-- -------------------------------------------------------------
-- 5. PERSONALIZED SQL RECOMMENDATION: SAME GENRES AS USER'S HISTORY
-- Useful SQL baseline before Neo4j recommendation is ready.
-- Excludes tracks the user has already played.
-- -------------------------------------------------------------
WITH user_genre_counts AS (
    SELECT
        t.genre_id,
        COUNT(*) AS user_genre_plays
    FROM play_history ph
    JOIN tracks t ON t.track_id = ph.track_id
    WHERE ph.user_id = %(user_id)s
    GROUP BY t.genre_id
), candidate_tracks AS (
    SELECT
        t.track_id,
        t.title AS track_title,
        ar.name AS artist_name,
        g.name AS genre_name,
        t.play_count,
        ugc.user_genre_plays,
        (ugc.user_genre_plays * 0.7 + t.play_count * 0.3) AS recommendation_score
    FROM tracks t
    JOIN user_genre_counts ugc ON ugc.genre_id = t.genre_id
    JOIN albums al ON al.album_id = t.album_id
    JOIN artists ar ON ar.artist_id = al.artist_id
    LEFT JOIN genres g ON g.genre_id = t.genre_id
    WHERE NOT EXISTS (
        SELECT 1
        FROM play_history ph2
        WHERE ph2.user_id = %(user_id)s
          AND ph2.track_id = t.track_id
    )
)
SELECT *
FROM candidate_tracks
ORDER BY recommendation_score DESC, play_count DESC
LIMIT 10;

-- -------------------------------------------------------------
-- 6. USERS WHO LISTENED TO ALL TRACKS IN A GIVEN PLAYLIST
-- Uses NOT EXISTS double-negative relational division pattern.
-- -------------------------------------------------------------
SELECT u.user_id, u.username
FROM users u
WHERE NOT EXISTS (
    SELECT 1
    FROM playlist_tracks pt
    WHERE pt.playlist_id = %(playlist_id)s
      AND NOT EXISTS (
          SELECT 1
          FROM play_history ph
          WHERE ph.user_id = u.user_id
            AND ph.track_id = pt.track_id
      )
);

-- -------------------------------------------------------------
-- 7. ARTISTS WITH ABOVE-AVERAGE TRACK POPULARITY IN THEIR GENRE
-- Uses nested aggregate comparison.
-- -------------------------------------------------------------
SELECT
    ar.artist_id,
    ar.name AS artist_name,
    g.name AS genre_name,
    AVG(t.play_count) AS artist_avg_play_count
FROM artists ar
JOIN albums al ON al.artist_id = ar.artist_id
JOIN tracks t ON t.album_id = al.album_id
LEFT JOIN genres g ON g.genre_id = t.genre_id
GROUP BY ar.artist_id, ar.name, g.genre_id, g.name
HAVING AVG(t.play_count) > (
    SELECT AVG(t2.play_count)
    FROM tracks t2
    WHERE t2.genre_id IS NOT DISTINCT FROM g.genre_id
)
ORDER BY artist_avg_play_count DESC;
