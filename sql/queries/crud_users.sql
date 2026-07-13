-- M2 SQL Developer — User CRUD Queries
-- Placeholder style: psycopg2 named parameters, e.g. %(user_id)s

-- 1. CREATE USER
-- Used by backend POST /register.
INSERT INTO users (email, username, password_hash)
VALUES (%(email)s, %(username)s, %(password_hash)s)
RETURNING user_id, email, username, created_at;

-- 2. READ USER BY ID
SELECT
    u.user_id,
    u.email,
    u.username,
    u.created_at
FROM users u
WHERE u.user_id = %(user_id)s;

-- 3. READ USER BY EMAIL
-- Used by login/auth flow.
SELECT user_id, email, username, password_hash, created_at
FROM users
WHERE email = %(email)s;

-- 4. UPDATE USER PROFILE
-- COALESCE keeps old value when backend passes NULL.
UPDATE users
SET
    email    = COALESCE(%(email)s, email),
    username = COALESCE(%(username)s, username)
WHERE user_id = %(user_id)s
RETURNING user_id, email, username, created_at;

-- 5. UPDATE PASSWORD HASH
UPDATE users
SET password_hash = %(password_hash)s
WHERE user_id = %(user_id)s
RETURNING user_id, email, username;

-- 6. DELETE USER
-- Cascades to playlists, play_history, and artist follows.
DELETE FROM users
WHERE user_id = %(user_id)s
RETURNING user_id, email, username;

-- 7. USER LISTENING SUMMARY
SELECT
    u.user_id,
    u.username,
    COUNT(ph.history_id) AS total_plays,
    COUNT(DISTINCT ph.track_id) AS unique_tracks_played,
    MAX(ph.played_at) AS last_played_at
FROM users u
LEFT JOIN play_history ph ON ph.user_id = u.user_id
WHERE u.user_id = %(user_id)s
GROUP BY u.user_id, u.username;
