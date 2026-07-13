-- =============================================================
-- INF2003 Music Streaming App — Triggers
-- Author : M1 (Database Architect)
-- Run    : psql -d music_streaming -f sql/triggers.sql
-- =============================================================

-- -------------------------------------------------------------
-- TRIGGER: trg_increment_play_count
--
-- Purpose:
--   Keeps tracks.play_count in sync without requiring a full
--   COUNT(*) query across play_history every time we display
--   a track's popularity.
--
-- When it fires:
--   AFTER every INSERT into play_history (one row at a time).
--
-- What it does:
--   Increments play_count by 1 on the track that was just played.
--
-- Design note:
--   play_count is intentionally denormalised. The authoritative
--   count is always derivable from play_history — this counter
--   exists purely for read performance on high-traffic queries
--   like "top 50 most played tracks".
-- -------------------------------------------------------------

CREATE OR REPLACE FUNCTION fn_increment_play_count()
RETURNS TRIGGER AS $$
BEGIN
    UPDATE tracks
    SET    play_count = play_count + 1
    WHERE  track_id   = NEW.track_id;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;


CREATE OR REPLACE TRIGGER trg_increment_play_count
    AFTER INSERT ON play_history
    FOR EACH ROW
    EXECUTE FUNCTION fn_increment_play_count();


CREATE OR REPLACE FUNCTION fn_audit_user_changes()
RETURNS TRIGGER AS $$
BEGIN
    IF OLD.email <> NEW.email THEN
        INSERT INTO audit_log (record_id, changed_by, field_name, old_value, new_value)
        VALUES (NEW.user_id, NEW.username, 'email', OLD.email, NEW.email);
    END IF;

    IF OLD.username <> NEW.username THEN
        INSERT INTO audit_log (record_id, changed_by, field_name, old_value, new_value)
        VALUES (NEW.user_id, NEW.username, 'username', OLD.username, NEW.username);
    END IF;

    IF OLD.password_hash <> NEW.password_hash THEN
        INSERT INTO audit_log (record_id, changed_by, field_name, old_value, new_value)
        VALUES (NEW.user_id, NEW.username, 'password_hash', '(hidden)', '(hidden)');
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;


CREATE OR REPLACE TRIGGER trg_audit_users
    AFTER UPDATE ON users
    FOR EACH ROW
    EXECUTE FUNCTION fn_audit_user_changes();


-- -------------------------------------------------------------
-- TRIGGER: trg_prevent_duplicate_playlist_track
--
-- Purpose:
--   Enforces the business rule that a track can appear at most
--   once in a given playlist, regardless of which application or
--   user submits the INSERT.
--
-- When it fires:
--   BEFORE every INSERT into playlist_tracks (row level).
--
-- What it does:
--   Checks whether the (playlist_id, track_id) pair already
--   exists. If it does, raises a database-level exception with
--   SQLSTATE P0001 so the calling code receives a clear, typed
--   error rather than a silent no-op.
--
-- Design note:
--   A unique constraint on (playlist_id, track_id) would prevent
--   duplicates too, but produces a generic "unique_violation"
--   error that is harder to distinguish from other constraint
--   failures. This trigger raises a named exception
--   ('duplicate_playlist_track') so the API layer can return
--   a precise 409 response without inspecting raw SQL state.
-- -------------------------------------------------------------

CREATE OR REPLACE FUNCTION fn_prevent_duplicate_playlist_track()
RETURNS TRIGGER AS $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM   playlist_tracks
        WHERE  playlist_id = NEW.playlist_id
          AND  track_id    = NEW.track_id
    ) THEN
        RAISE EXCEPTION 'duplicate_playlist_track'
            USING
                DETAIL = format(
                    'track_id %s is already in playlist_id %s',
                    NEW.track_id, NEW.playlist_id),
                HINT = 'Remove the existing entry before re-adding, '
                       'or choose a different track.';
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;


CREATE OR REPLACE TRIGGER trg_prevent_duplicate_playlist_track
    BEFORE INSERT ON playlist_tracks
    FOR EACH ROW
    EXECUTE FUNCTION fn_prevent_duplicate_playlist_track();


-- -------------------------------------------------------------
-- TRIGGER: trg_audit_artists / _albums / _tracks / _genres
--
-- Purpose:
--   Extends audit coverage to all catalogue tables.
--   Records every INSERT, UPDATE (name/title only), and DELETE
--   on artists, albums, tracks, and genres into audit_log.
--
-- When it fires:
--   AFTER INSERT OR UPDATE OR DELETE on each catalogue table.
--
-- What it does:
--   INSERT  → field_name = 'created',  new_value  = name or title
--   UPDATE  → field_name = 'name'/'title', old and new values
--   DELETE  → field_name = 'deleted',  old_value  = name or title
--
-- Design note:
--   A single generic function (fn_audit_catalogue) handles all
--   four tables by branching on TG_TABLE_NAME and TG_OP.
--   play_count bumps (via trg_increment_play_count) trigger an
--   UPDATE on tracks but are silently ignored here because only
--   title changes are logged.
-- -------------------------------------------------------------

-- PL/pgSQL evaluates all record field references at parse time, so a single
-- generic function using CASE TG_TABLE_NAME to branch field access fails when
-- the triggering table doesn't have that column. Four separate functions are
-- used instead — one per table.

CREATE OR REPLACE FUNCTION fn_audit_artists()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'INSERT' THEN
        INSERT INTO audit_log (table_name, record_id, changed_by, field_name, old_value, new_value)
        VALUES ('artists', NEW.artist_id, current_user, 'created', NULL, NEW.name);
        RETURN NEW;
    ELSIF TG_OP = 'UPDATE' THEN
        IF OLD.name IS DISTINCT FROM NEW.name THEN
            INSERT INTO audit_log (table_name, record_id, changed_by, field_name, old_value, new_value)
            VALUES ('artists', NEW.artist_id, current_user, 'name', OLD.name, NEW.name);
        END IF;
        RETURN NEW;
    ELSIF TG_OP = 'DELETE' THEN
        INSERT INTO audit_log (table_name, record_id, changed_by, field_name, old_value, new_value)
        VALUES ('artists', OLD.artist_id, current_user, 'deleted', OLD.name, NULL);
        RETURN OLD;
    END IF;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE TRIGGER trg_audit_artists
    AFTER INSERT OR UPDATE OR DELETE ON artists
    FOR EACH ROW EXECUTE FUNCTION fn_audit_artists();


CREATE OR REPLACE FUNCTION fn_audit_albums()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'INSERT' THEN
        INSERT INTO audit_log (table_name, record_id, changed_by, field_name, old_value, new_value)
        VALUES ('albums', NEW.album_id, current_user, 'created', NULL, NEW.title);
        RETURN NEW;
    ELSIF TG_OP = 'UPDATE' THEN
        IF OLD.title IS DISTINCT FROM NEW.title THEN
            INSERT INTO audit_log (table_name, record_id, changed_by, field_name, old_value, new_value)
            VALUES ('albums', NEW.album_id, current_user, 'title', OLD.title, NEW.title);
        END IF;
        RETURN NEW;
    ELSIF TG_OP = 'DELETE' THEN
        INSERT INTO audit_log (table_name, record_id, changed_by, field_name, old_value, new_value)
        VALUES ('albums', OLD.album_id, current_user, 'deleted', OLD.title, NULL);
        RETURN OLD;
    END IF;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE TRIGGER trg_audit_albums
    AFTER INSERT OR UPDATE OR DELETE ON albums
    FOR EACH ROW EXECUTE FUNCTION fn_audit_albums();


CREATE OR REPLACE FUNCTION fn_audit_tracks()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'INSERT' THEN
        INSERT INTO audit_log (table_name, record_id, changed_by, field_name, old_value, new_value)
        VALUES ('tracks', NEW.track_id, current_user, 'created', NULL, NEW.title);
        RETURN NEW;
    ELSIF TG_OP = 'UPDATE' THEN
        IF OLD.title IS DISTINCT FROM NEW.title THEN
            INSERT INTO audit_log (table_name, record_id, changed_by, field_name, old_value, new_value)
            VALUES ('tracks', NEW.track_id, current_user, 'title', OLD.title, NEW.title);
        END IF;
        RETURN NEW;
    ELSIF TG_OP = 'DELETE' THEN
        INSERT INTO audit_log (table_name, record_id, changed_by, field_name, old_value, new_value)
        VALUES ('tracks', OLD.track_id, current_user, 'deleted', OLD.title, NULL);
        RETURN OLD;
    END IF;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE TRIGGER trg_audit_tracks
    AFTER INSERT OR UPDATE OR DELETE ON tracks
    FOR EACH ROW EXECUTE FUNCTION fn_audit_tracks();


CREATE OR REPLACE FUNCTION fn_audit_genres()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'INSERT' THEN
        INSERT INTO audit_log (table_name, record_id, changed_by, field_name, old_value, new_value)
        VALUES ('genres', NEW.genre_id, current_user, 'created', NULL, NEW.name);
        RETURN NEW;
    ELSIF TG_OP = 'UPDATE' THEN
        IF OLD.name IS DISTINCT FROM NEW.name THEN
            INSERT INTO audit_log (table_name, record_id, changed_by, field_name, old_value, new_value)
            VALUES ('genres', NEW.genre_id, current_user, 'name', OLD.name, NEW.name);
        END IF;
        RETURN NEW;
    ELSIF TG_OP = 'DELETE' THEN
        INSERT INTO audit_log (table_name, record_id, changed_by, field_name, old_value, new_value)
        VALUES ('genres', OLD.genre_id, current_user, 'deleted', OLD.name, NULL);
        RETURN OLD;
    END IF;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE TRIGGER trg_audit_genres
    AFTER INSERT OR UPDATE OR DELETE ON genres
    FOR EACH ROW EXECUTE FUNCTION fn_audit_genres();
