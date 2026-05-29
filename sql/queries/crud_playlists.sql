-- =============================================================
-- M2 SQL Developer — Playlist CRUD Queries
-- Project: Music Streaming Database
-- Target DB: PostgreSQL
-- Placeholder style: psycopg2 named parameters
-- =============================================================

-- -------------------------------------------------------------
-- 1. CREATE PLAYLIST
-- -------------------------------------------------------------
INSERT INTO playlists (user_id, name, is_public)
VALUES (%(user_id)s, %(name)s, COALESCE(%(is_public)s, TRUE))
RETURNING playlist_id, user_id, name, is_public, created_at;

-- -------------------------------------------------------------
-- 2. LIST PLAYLISTS OWNED BY USER
-- -------------------------------------------------------------
SELECT
    p.playlist_id,
    p.user_id,
    p.name,
    p.is_public,
    p.created_at,
    COUNT(pt.track_id) AS track_count
FROM playlists p
LEFT JOIN playlist_tracks pt ON pt.playlist_id = p.playlist_id
WHERE p.user_id = %(user_id)s
GROUP BY p.playlist_id, p.user_id, p.name, p.is_public, p.created_at
ORDER BY p.created_at DESC;

-- -------------------------------------------------------------
-- 3. LIST PUBLIC PLAYLISTS
-- -------------------------------------------------------------
SELECT
    p.playlist_id,
    p.name,
    p.created_at,
    u.user_id AS owner_id,
    u.username AS owner_username,
    COUNT(pt.track_id) AS track_count
FROM playlists p
JOIN users u ON u.user_id = p.user_id
LEFT JOIN playlist_tracks pt ON pt.playlist_id = p.playlist_id
WHERE p.is_public = TRUE
GROUP BY p.playlist_id, p.name, p.created_at, u.user_id, u.username
ORDER BY p.created_at DESC
LIMIT %(limit)s OFFSET %(offset)s;

-- -------------------------------------------------------------
-- 4. GET PLAYLIST DETAILS WITH TRACKS
-- Allows owner to view private playlist; everyone can view public.
-- -------------------------------------------------------------
SELECT
    p.playlist_id,
    p.name AS playlist_name,
    p.is_public,
    p.created_at,
    u.username AS owner_username,
    pt.position,
    t.track_id,
    t.title AS track_title,
    t.duration_sec,
    t.play_count,
    ar.name AS artist_name,
    al.title AS album_title,
    g.name AS genre_name
FROM playlists p
JOIN users u ON u.user_id = p.user_id
LEFT JOIN playlist_tracks pt ON pt.playlist_id = p.playlist_id
LEFT JOIN tracks t ON t.track_id = pt.track_id
LEFT JOIN albums al ON al.album_id = t.album_id
LEFT JOIN artists ar ON ar.artist_id = al.artist_id
LEFT JOIN genres g ON g.genre_id = t.genre_id
WHERE p.playlist_id = %(playlist_id)s
  AND (p.is_public = TRUE OR p.user_id = %(requesting_user_id)s)
ORDER BY pt.position ASC NULLS LAST;

-- -------------------------------------------------------------
-- 5. UPDATE PLAYLIST NAME / VISIBILITY
-- -------------------------------------------------------------
UPDATE playlists
SET
    name = COALESCE(%(name)s, name),
    is_public = COALESCE(%(is_public)s, is_public)
WHERE playlist_id = %(playlist_id)s
  AND user_id = %(user_id)s
RETURNING playlist_id, user_id, name, is_public, created_at;

-- -------------------------------------------------------------
-- 6. DELETE PLAYLIST
-- -------------------------------------------------------------
DELETE FROM playlists
WHERE playlist_id = %(playlist_id)s
  AND user_id = %(user_id)s
RETURNING playlist_id, name;

-- -------------------------------------------------------------
-- 7. APPEND TRACK TO END OF PLAYLIST
-- Avoids position conflicts by calculating next position.
-- -------------------------------------------------------------
INSERT INTO playlist_tracks (playlist_id, track_id, position)
SELECT
    %(playlist_id)s,
    %(track_id)s,
    COALESCE(MAX(position), 0) + 1
FROM playlist_tracks
WHERE playlist_id = %(playlist_id)s
ON CONFLICT (playlist_id, track_id) DO NOTHING
RETURNING playlist_id, track_id, position;

-- -------------------------------------------------------------
-- 8. INSERT TRACK AT SPECIFIC POSITION
-- Two-phase position shift avoids UNIQUE(playlist_id, position) conflicts.
-- Run inside a transaction.
-- -------------------------------------------------------------
UPDATE playlist_tracks
SET position = position + 100000
WHERE playlist_id = %(playlist_id)s
  AND position >= %(position)s;

INSERT INTO playlist_tracks (playlist_id, track_id, position)
VALUES (%(playlist_id)s, %(track_id)s, %(position)s)
RETURNING playlist_id, track_id, position;

UPDATE playlist_tracks
SET position = position - 99999
WHERE playlist_id = %(playlist_id)s
  AND position >= 100000;

-- -------------------------------------------------------------
-- 9. REMOVE TRACK FROM PLAYLIST AND COMPACT POSITIONS
-- Run inside a transaction.
-- -------------------------------------------------------------
WITH removed AS (
    DELETE FROM playlist_tracks
    WHERE playlist_id = %(playlist_id)s
      AND track_id = %(track_id)s
    RETURNING playlist_id, position
), shifted AS (
    UPDATE playlist_tracks pt
    SET position = pt.position - 1
    FROM removed r
    WHERE pt.playlist_id = r.playlist_id
      AND pt.position > r.position
    RETURNING pt.playlist_id, pt.track_id, pt.position
)
SELECT * FROM removed;

-- -------------------------------------------------------------
-- 10. MOVE TRACK TO A NEW POSITION
-- Simple and safe method using row_number rebuild.
-- Run inside a transaction.
-- -------------------------------------------------------------
WITH current_rows AS (
    SELECT playlist_id, track_id, position
    FROM playlist_tracks
    WHERE playlist_id = %(playlist_id)s
), target AS (
    SELECT track_id, position AS old_position
    FROM current_rows
    WHERE track_id = %(track_id)s
), reordered AS (
    SELECT
        cr.track_id,
        ROW_NUMBER() OVER (
            ORDER BY
                CASE
                    WHEN cr.track_id = %(track_id)s THEN %(new_position)s
                    WHEN cr.position >= %(new_position)s AND cr.position < (SELECT old_position FROM target) THEN cr.position + 1
                    WHEN cr.position <= %(new_position)s AND cr.position > (SELECT old_position FROM target) THEN cr.position - 1
                    ELSE cr.position
                END,
                cr.position
        ) AS new_pos
    FROM current_rows cr
)
UPDATE playlist_tracks pt
SET position = r.new_pos + 100000
FROM reordered r
WHERE pt.playlist_id = %(playlist_id)s
  AND pt.track_id = r.track_id;

UPDATE playlist_tracks
SET position = position - 100000
WHERE playlist_id = %(playlist_id)s
  AND position > 100000
RETURNING playlist_id, track_id, position;
