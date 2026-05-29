-- =============================================================
-- M2 SQL Developer — User CRUD + Subscription Queries
-- Project: Music Streaming Database
-- Target DB: PostgreSQL
-- Placeholder style: psycopg2 named parameters, e.g. %(user_id)s
-- =============================================================

-- -------------------------------------------------------------
-- 1. CREATE USER
-- Used by backend POST /register.
-- -------------------------------------------------------------
INSERT INTO users (email, username, password_hash, country)
VALUES (%(email)s, %(username)s, %(password_hash)s, %(country)s)
RETURNING user_id, email, username, country, created_at;

-- -------------------------------------------------------------
-- 2. READ USER BY ID WITH CURRENT ACTIVE PLAN
-- Returns one user and their active subscription, if any.
-- -------------------------------------------------------------
SELECT
    u.user_id,
    u.email,
    u.username,
    u.country,
    u.created_at,
    p.name AS current_plan,
    p.monthly_price,
    p.skip_limit,
    s.subscription_id,
    s.start_date,
    s.end_date,
    s.status
FROM users u
LEFT JOIN subscriptions s
       ON s.user_id = u.user_id
      AND s.status = 'active'
LEFT JOIN plans p
       ON p.plan_id = s.plan_id
WHERE u.user_id = %(user_id)s;

-- -------------------------------------------------------------
-- 3. READ USER BY EMAIL
-- Used by login/auth flow.
-- -------------------------------------------------------------
SELECT user_id, email, username, password_hash, country, created_at
FROM users
WHERE email = %(email)s;

-- -------------------------------------------------------------
-- 4. UPDATE USER PROFILE
-- COALESCE keeps old value when backend passes NULL.
-- -------------------------------------------------------------
UPDATE users
SET
    email    = COALESCE(%(email)s, email),
    username = COALESCE(%(username)s, username),
    country  = COALESCE(%(country)s, country)
WHERE user_id = %(user_id)s
RETURNING user_id, email, username, country, created_at;

-- -------------------------------------------------------------
-- 5. UPDATE PASSWORD HASH
-- -------------------------------------------------------------
UPDATE users
SET password_hash = %(password_hash)s
WHERE user_id = %(user_id)s
RETURNING user_id, email, username;

-- -------------------------------------------------------------
-- 6. DELETE USER
-- Cascades to subscriptions, playlists, play_history, follows.
-- -------------------------------------------------------------
DELETE FROM users
WHERE user_id = %(user_id)s
RETURNING user_id, email, username;

-- -------------------------------------------------------------
-- 7. CHANGE USER SUBSCRIPTION PLAN
-- Inserting a new active subscription fires trigger
-- trg_deactivate_old_subscription to expire previous active plans.
-- -------------------------------------------------------------
INSERT INTO subscriptions (user_id, plan_id, start_date, status)
SELECT %(user_id)s, p.plan_id, CURRENT_DATE, 'active'
FROM plans p
WHERE p.name = %(plan_name)s
RETURNING subscription_id, user_id, plan_id, start_date, end_date, status;

-- -------------------------------------------------------------
-- 8. CANCEL ACTIVE SUBSCRIPTION
-- -------------------------------------------------------------
UPDATE subscriptions
SET status = 'cancelled',
    end_date = CURRENT_DATE
WHERE user_id = %(user_id)s
  AND status = 'active'
RETURNING subscription_id, user_id, plan_id, start_date, end_date, status;

-- -------------------------------------------------------------
-- 9. USER LISTENING SUMMARY
-- Useful for profile/dashboard page.
-- -------------------------------------------------------------
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
