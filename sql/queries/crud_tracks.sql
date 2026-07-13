-- M2 SQL Developer — Tracks, Albums, Artists CRUD Queries
-- Placeholder style: psycopg2 named parameters

-- 1. SEARCH TRACKS
-- Pass NULL for search/genre_name to ignore those filters.
SELECT
    t.track_id,
    t.title AS track_title,
    t.duration_sec,
    t.play_count,
    al.album_id,
    al.title AS album_title,
    ar.artist_id,
    ar.name AS artist_name,
    g.genre_id,
    g.name AS genre_name
FROM tracks t
JOIN albums al  ON al.album_id = t.album_id
JOIN artists ar ON ar.artist_id = al.artist_id
LEFT JOIN genres g ON g.genre_id = t.genre_id
WHERE (%(search)s IS NULL OR (
        t.title ILIKE '%' || %(search)s || '%'
     OR al.title ILIKE '%' || %(search)s || '%'
     OR ar.name  ILIKE '%' || %(search)s || '%'
))
  AND (%(genre_name)s IS NULL OR g.name = %(genre_name)s)
ORDER BY t.play_count DESC, t.title ASC
LIMIT %(limit)s OFFSET %(offset)s;

-- 2. GET TRACK DETAILS BY ID
SELECT
    t.track_id,
    t.title AS track_title,
    t.duration_sec,
    t.play_count,
    al.album_id,
    al.title AS album_title,
    al.release_date,
    ar.artist_id,
    ar.name AS artist_name,
    ar.bio,
    g.genre_id,
    g.name AS genre_name
FROM tracks t
JOIN albums al  ON al.album_id = t.album_id
JOIN artists ar ON ar.artist_id = al.artist_id
LEFT JOIN genres g ON g.genre_id = t.genre_id
WHERE t.track_id = %(track_id)s;

-- 3. CREATE ARTIST
INSERT INTO artists (name, bio)
VALUES (%(name)s, %(bio)s)
RETURNING artist_id, name, bio;

-- 4. CREATE ALBUM
INSERT INTO albums (artist_id, title, release_date)
VALUES (%(artist_id)s, %(title)s, %(release_date)s)
RETURNING album_id, artist_id, title, release_date;

-- 5. CREATE TRACK
INSERT INTO tracks (album_id, genre_id, title, duration_sec)
VALUES (%(album_id)s, %(genre_id)s, %(title)s, %(duration_sec)s)
RETURNING track_id, album_id, genre_id, title, duration_sec, play_count;

-- 6. CREATE GENRE IF MISSING
INSERT INTO genres (name)
VALUES (%(name)s)
ON CONFLICT (name) DO UPDATE SET name = EXCLUDED.name
RETURNING genre_id, name;

-- 7. UPDATE TRACK METADATA
UPDATE tracks
SET
    album_id     = COALESCE(%(album_id)s, album_id),
    genre_id     = COALESCE(%(genre_id)s, genre_id),
    title        = COALESCE(%(title)s, title),
    duration_sec = COALESCE(%(duration_sec)s, duration_sec)
WHERE track_id = %(track_id)s
RETURNING track_id, album_id, genre_id, title, duration_sec, play_count;

-- 8. DELETE TRACK
-- Cascades to playlist_tracks and play_history.
DELETE FROM tracks
WHERE track_id = %(track_id)s
RETURNING track_id, title;

-- 9. LOG A TRACK PLAY
-- Trigger increments tracks.play_count.
WITH inserted_play AS (
    INSERT INTO play_history (user_id, track_id)
    VALUES (%(user_id)s, %(track_id)s)
    RETURNING history_id, user_id, track_id, played_at
)
SELECT
    ip.history_id,
    ip.user_id,
    ip.track_id,
    ip.played_at,
    t.play_count
FROM inserted_play ip
JOIN tracks t ON t.track_id = ip.track_id;

-- 10. FOLLOW ARTIST
INSERT INTO user_follows_artist (user_id, artist_id)
VALUES (%(user_id)s, %(artist_id)s)
ON CONFLICT (user_id, artist_id) DO NOTHING
RETURNING user_id, artist_id, followed_at;

-- 11. UNFOLLOW ARTIST
DELETE FROM user_follows_artist
WHERE user_id = %(user_id)s
  AND artist_id = %(artist_id)s
RETURNING user_id, artist_id;
