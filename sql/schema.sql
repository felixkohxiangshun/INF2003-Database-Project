-- INF2003 Music Streaming App — PostgreSQL Schema
-- Author : M1 (Database Architect)
-- DB     : music_streaming

-- Run order matters — tables with no FK dependencies come first.

-- 1. USERS
CREATE TABLE IF NOT EXISTS users (
    user_id       SERIAL PRIMARY KEY,
    email         VARCHAR(512)   NOT NULL UNIQUE,
    username      VARCHAR(512)   NOT NULL UNIQUE,
    password_hash VARCHAR(512)   NOT NULL,
    created_at    TIMESTAMP      NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- 2. GENRES
-- Normalised lookup table — avoids free-text genre strings on each track.
CREATE TABLE IF NOT EXISTS genres (
    genre_id  SERIAL PRIMARY KEY,
    name      VARCHAR(100) NOT NULL UNIQUE
);

-- 3. ARTISTS
CREATE TABLE IF NOT EXISTS artists (
    artist_id  SERIAL PRIMARY KEY,
    name       VARCHAR(512) NOT NULL,
    bio        TEXT
);

-- 4. ALBUMS
CREATE TABLE IF NOT EXISTS albums (
    album_id     SERIAL PRIMARY KEY,
    artist_id    INT          NOT NULL REFERENCES artists(artist_id) ON DELETE CASCADE,
    title        VARCHAR(512) NOT NULL,
    release_date DATE
);

-- 5. TRACKS
-- play_count is a denormalised counter updated by trigger (see triggers.sql)
-- for fast read performance.
CREATE TABLE IF NOT EXISTS tracks (
    track_id     SERIAL PRIMARY KEY,
    album_id     INT          NOT NULL REFERENCES albums(album_id)  ON DELETE CASCADE,
    genre_id     INT                   REFERENCES genres(genre_id)  ON DELETE SET NULL,
    title        VARCHAR(512) NOT NULL,
    duration_sec INT          NOT NULL CHECK (duration_sec > 0),
    play_count   INT          NOT NULL DEFAULT 0
);

-- 6. PLAYLISTS
CREATE TABLE IF NOT EXISTS playlists (
    playlist_id  SERIAL PRIMARY KEY,
    user_id      INT          NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    name         VARCHAR(512) NOT NULL,
    is_public    BOOLEAN      NOT NULL DEFAULT TRUE,
    created_at   TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- 7. PLAYLIST_TRACKS  [many-to-many junction]
-- position allows ordered track lists within a playlist.
CREATE TABLE IF NOT EXISTS playlist_tracks (
    playlist_id  INT NOT NULL REFERENCES playlists(playlist_id) ON DELETE CASCADE,
    track_id     INT NOT NULL REFERENCES tracks(track_id)       ON DELETE CASCADE,
    position     INT NOT NULL CHECK (position >= 1),
    PRIMARY KEY (playlist_id, track_id),
    UNIQUE (playlist_id, position)   -- no duplicate positions within a playlist
);

-- 8. PLAY_HISTORY
-- Every completed play is logged here. INSERT fires the trigger in
-- triggers.sql which increments tracks.play_count automatically.
CREATE TABLE IF NOT EXISTS play_history (
    history_id  SERIAL PRIMARY KEY,
    user_id     INT       NOT NULL REFERENCES users(user_id)   ON DELETE CASCADE,
    track_id    INT       NOT NULL REFERENCES tracks(track_id) ON DELETE CASCADE,
    played_at   TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- 9. USER_FOLLOWS_ARTIST  [many-to-many junction]
CREATE TABLE IF NOT EXISTS user_follows_artist (
    user_id     INT       NOT NULL REFERENCES users(user_id)    ON DELETE CASCADE,
    artist_id   INT       NOT NULL REFERENCES artists(artist_id) ON DELETE CASCADE,
    followed_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, artist_id)
);

-- 10. AUDIT_LOG
-- Records every UPDATE to the users table (email / username changes),
-- populated automatically by trg_audit_users.
CREATE TABLE IF NOT EXISTS audit_log (
    log_id      SERIAL PRIMARY KEY,
    table_name  VARCHAR(64)  NOT NULL DEFAULT 'users',
    record_id   INT          NOT NULL,
    changed_at  TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    changed_by  VARCHAR(512),          -- username at time of change
    field_name  VARCHAR(64)  NOT NULL,
    old_value   TEXT,
    new_value   TEXT
);

CREATE INDEX IF NOT EXISTS idx_audit_log_record_id  ON audit_log(record_id);
CREATE INDEX IF NOT EXISTS idx_audit_log_changed_at ON audit_log(changed_at);

-- Indexes on columns used frequently in JOINs and WHERE clauses.
CREATE INDEX IF NOT EXISTS idx_albums_artist_id       ON albums(artist_id);
CREATE INDEX IF NOT EXISTS idx_tracks_album_id        ON tracks(album_id);
CREATE INDEX IF NOT EXISTS idx_tracks_genre_id        ON tracks(genre_id);
CREATE INDEX IF NOT EXISTS idx_play_history_user_id   ON play_history(user_id);
CREATE INDEX IF NOT EXISTS idx_play_history_track_id  ON play_history(track_id);
CREATE INDEX IF NOT EXISTS idx_play_history_played_at ON play_history(played_at);
CREATE INDEX IF NOT EXISTS idx_playlists_user_id      ON playlists(user_id);
