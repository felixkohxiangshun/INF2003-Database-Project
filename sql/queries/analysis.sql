-- =============================================================
-- M2 SQL Developer — EXPLAIN ANALYZE / Performance Checks
-- Project: Music Streaming Database
-- Target DB: PostgreSQL
-- =============================================================

-- -------------------------------------------------------------
-- 1. Check indexed history lookup by user.
-- Expected index used: idx_play_history_user_id
-- -------------------------------------------------------------
EXPLAIN ANALYZE
SELECT *
FROM play_history
WHERE user_id = 1
ORDER BY played_at DESC
LIMIT 20;

-- -------------------------------------------------------------
-- 2. Check indexed history lookup by played_at.
-- Expected index used: idx_play_history_played_at
-- -------------------------------------------------------------
EXPLAIN ANALYZE
SELECT COUNT(*)
FROM play_history
WHERE played_at >= date_trunc('month', CURRENT_DATE);

-- -------------------------------------------------------------
-- 3. Check track search with joins.
-- Note: ILIKE '%term%' may require trigram index for large datasets.
-- Basic B-tree indexes help joins, not contains search.
-- -------------------------------------------------------------
EXPLAIN ANALYZE
SELECT
    t.track_id,
    t.title,
    ar.name AS artist_name,
    g.name AS genre_name
FROM tracks t
JOIN albums al ON al.album_id = t.album_id
JOIN artists ar ON ar.artist_id = al.artist_id
LEFT JOIN genres g ON g.genre_id = t.genre_id
WHERE t.title ILIKE '%love%'
ORDER BY t.play_count DESC
LIMIT 20;

-- -------------------------------------------------------------
-- 4. Recommended optional indexes for search-heavy app routes.
-- Only run these if lecturer allows schema/index improvements.
-- pg_trgm makes ILIKE '%keyword%' much faster.
-- -------------------------------------------------------------
-- CREATE EXTENSION IF NOT EXISTS pg_trgm;
-- CREATE INDEX idx_tracks_title_trgm  ON tracks  USING GIN (title gin_trgm_ops);
-- CREATE INDEX idx_artists_name_trgm  ON artists USING GIN (name gin_trgm_ops);
-- CREATE INDEX idx_albums_title_trgm  ON albums  USING GIN (title gin_trgm_ops);

-- -------------------------------------------------------------
-- 5. Consistency check: denormalised tracks.play_count vs history count.
-- Should return zero rows if trigger worked correctly.
-- -------------------------------------------------------------
SELECT
    t.track_id,
    t.title,
    t.play_count AS stored_play_count,
    COUNT(ph.history_id) AS actual_play_count
FROM tracks t
LEFT JOIN play_history ph ON ph.track_id = t.track_id
GROUP BY t.track_id, t.title, t.play_count
HAVING t.play_count <> COUNT(ph.history_id);
