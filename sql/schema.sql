-- =============================================================
-- INF2003 Music Streaming App — PostgreSQL Schema
-- Author : M1 (Database Architect)
-- DB     : music_streaming
-- =============================================================

-- Run order matters — tables with no FK dependencies come first.

-- -------------------------------------------------------------
-- 1. PLANS
--    Defines subscription tiers (free, premium, etc.)
--    No foreign keys — must be created before SUBSCRIPTIONS.
-- -------------------------------------------------------------
CREATE TABLE plans (
    plan_id       SERIAL PRIMARY KEY,
    name          VARCHAR(50)    NOT NULL UNIQUE,
    monthly_price DECIMAL(6, 2)  NOT NULL CHECK (monthly_price >= 0),
    skip_limit    INT            NOT NULL DEFAULT -1  -- -1 means unlimited
);

-- -------------------------------------------------------------
-- 2. USERS
--    Core user account table.
--    country uses ISO 3166-1 alpha-2 codes (e.g. 'SG', 'US').
-- -------------------------------------------------------------
CREATE TABLE users (
    user_id       SERIAL PRIMARY KEY,
    email         VARCHAR(255)   NOT NULL UNIQUE,
    username      VARCHAR(100)   NOT NULL UNIQUE,
    password_hash VARCHAR(255)   NOT NULL,
    country       CHAR(2),
    created_at    TIMESTAMP      NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- -------------------------------------------------------------
-- 3. SUBSCRIPTIONS
--    Tracks which plan a user is on and its validity window.
--    Relationship: USERS (1) — (many) SUBSCRIPTIONS
--                  PLANS  (1) — (many) SUBSCRIPTIONS
-- -------------------------------------------------------------
CREATE TABLE subscriptions (
    subscription_id SERIAL PRIMARY KEY,
    user_id         INT          NOT NULL REFERENCES users(user_id)  ON DELETE CASCADE,
    plan_id         INT          NOT NULL REFERENCES plans(plan_id)  ON DELETE RESTRICT,
    start_date      DATE         NOT NULL DEFAULT CURRENT_DATE,
    end_date        DATE,
    status          VARCHAR(20)  NOT NULL DEFAULT 'active'
                        CHECK (status IN ('active', 'cancelled', 'expired')),
    CONSTRAINT chk_date_order CHECK (end_date IS NULL OR end_date >= start_date)
);

-- -------------------------------------------------------------
-- 4. GENRES
--    Normalised genre lookup — avoids free-text genre strings
--    on each track.
-- -------------------------------------------------------------
CREATE TABLE genres (
    genre_id  SERIAL PRIMARY KEY,
    name      VARCHAR(100) NOT NULL UNIQUE
);

-- -------------------------------------------------------------
-- 5. ARTISTS
-- -------------------------------------------------------------
CREATE TABLE artists (
    artist_id  SERIAL PRIMARY KEY,
    name       VARCHAR(255) NOT NULL,
    bio        TEXT,
    country    CHAR(2)
);

-- -------------------------------------------------------------
-- 6. ALBUMS
--    Relationship: ARTISTS (1) — (many) ALBUMS
-- -------------------------------------------------------------
CREATE TABLE albums (
    album_id     SERIAL PRIMARY KEY,
    artist_id    INT          NOT NULL REFERENCES artists(artist_id) ON DELETE CASCADE,
    title        VARCHAR(255) NOT NULL,
    release_date DATE
);

-- -------------------------------------------------------------
-- 7. TRACKS
--    Relationship: ALBUMS (1) — (many) TRACKS
--                  GENRES (1) — (many) TRACKS
--
--    play_count is a denormalised counter updated by trigger
--    (see triggers.sql) for fast read performance.
-- -------------------------------------------------------------
CREATE TABLE tracks (
    track_id     SERIAL PRIMARY KEY,
    album_id     INT          NOT NULL REFERENCES albums(album_id)  ON DELETE CASCADE,
    genre_id     INT                   REFERENCES genres(genre_id)  ON DELETE SET NULL,
    title        VARCHAR(255) NOT NULL,
    duration_sec INT          NOT NULL CHECK (duration_sec > 0),
    play_count   INT          NOT NULL DEFAULT 0
);

-- -------------------------------------------------------------
-- 8. PLAYLISTS
--    Relationship: USERS (1) — (many) PLAYLISTS
-- -------------------------------------------------------------
CREATE TABLE playlists (
    playlist_id  SERIAL PRIMARY KEY,
    user_id      INT          NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    name         VARCHAR(255) NOT NULL,
    is_public    BOOLEAN      NOT NULL DEFAULT TRUE,
    created_at   TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- -------------------------------------------------------------
-- 9. PLAYLIST_TRACKS  [many-to-many junction]
--    Relationship: PLAYLISTS (many) — (many) TRACKS
--    position allows ordered track lists within a playlist.
-- -------------------------------------------------------------
CREATE TABLE playlist_tracks (
    playlist_id  INT NOT NULL REFERENCES playlists(playlist_id) ON DELETE CASCADE,
    track_id     INT NOT NULL REFERENCES tracks(track_id)       ON DELETE CASCADE,
    position     INT NOT NULL CHECK (position >= 1),
    PRIMARY KEY (playlist_id, track_id),
    UNIQUE (playlist_id, position)   -- no duplicate positions within a playlist
);

-- -------------------------------------------------------------
-- 10. PLAY_HISTORY
--     Every completed play is logged here.
--     Relationship: USERS (1) — (many) PLAY_HISTORY
--                   TRACKS (1) — (many) PLAY_HISTORY
--
--     INSERT into this table fires the trigger in triggers.sql
--     which increments tracks.play_count automatically.
-- -------------------------------------------------------------
CREATE TABLE play_history (
    history_id  SERIAL PRIMARY KEY,
    user_id     INT       NOT NULL REFERENCES users(user_id)  ON DELETE CASCADE,
    track_id    INT       NOT NULL REFERENCES tracks(track_id) ON DELETE CASCADE,
    played_at   TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- -------------------------------------------------------------
-- 11. USER_FOLLOWS_ARTIST  [many-to-many junction]
--     Relationship: USERS (many) — (many) ARTISTS
-- -------------------------------------------------------------
CREATE TABLE user_follows_artist (
    user_id     INT       NOT NULL REFERENCES users(user_id)    ON DELETE CASCADE,
    artist_id   INT       NOT NULL REFERENCES artists(artist_id) ON DELETE CASCADE,
    followed_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, artist_id)
);

-- =============================================================
-- INDEXES
-- Added on columns used frequently in JOINs and WHERE clauses.
-- =============================================================

-- Speed up subscription lookups by user
CREATE INDEX idx_subscriptions_user_id  ON subscriptions(user_id);
-- Speed up album lookups by artist
CREATE INDEX idx_albums_artist_id       ON albums(artist_id);
-- Speed up track lookups by album and genre
CREATE INDEX idx_tracks_album_id        ON tracks(album_id);
CREATE INDEX idx_tracks_genre_id        ON tracks(genre_id);
-- Speed up history queries by user and by track
CREATE INDEX idx_play_history_user_id   ON play_history(user_id);
CREATE INDEX idx_play_history_track_id  ON play_history(track_id);
-- Speed up time-range queries on play history
CREATE INDEX idx_play_history_played_at ON play_history(played_at);
-- Speed up playlist ownership queries
CREATE INDEX idx_playlists_user_id      ON playlists(user_id);
