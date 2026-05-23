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


-- -------------------------------------------------------------
-- TRIGGER: trg_deactivate_old_subscription
--
-- Purpose:
--   When a new 'active' subscription is inserted for a user,
--   automatically mark their previous subscription as 'expired'.
--   Enforces the business rule: one active plan per user.
--
-- When it fires:
--   AFTER INSERT on subscriptions, only when status = 'active'.
-- -------------------------------------------------------------

CREATE OR REPLACE FUNCTION fn_deactivate_old_subscription()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.status = 'active' THEN
        UPDATE subscriptions
        SET    status   = 'expired',
               end_date = CURRENT_DATE
        WHERE  user_id  = NEW.user_id
          AND  status   = 'active'
          AND  subscription_id <> NEW.subscription_id;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;


CREATE OR REPLACE TRIGGER trg_deactivate_old_subscription
    AFTER INSERT ON subscriptions
    FOR EACH ROW
    EXECUTE FUNCTION fn_deactivate_old_subscription();
