# Backend — M4 (Backend & Integration)

## Stack

- **Framework**: Flask (Python)
- **PostgreSQL driver**: psycopg2
- **Neo4j driver**: neo4j (official Python driver)
- **Auth**: bcrypt + Flask sessions

## Suggested file structure

```
backend/
├── app.py              # App factory + route registration
├── db.py               # PostgreSQL connection pool
├── graph.py            # Neo4j driver wrapper
├── routes/
│   ├── auth.py         # POST /login, POST /logout, POST /register
│   ├── tracks.py       # GET /tracks, GET /tracks/<id>, POST /play
│   ├── playlist.py     # CRUD /playlists
│   ├── history.py      # GET /history, GET /stats
│   └── recommendations.py  # GET /recommend  (Neo4j query)
└── middleware/
    └── auth_required.py    # Session guard decorator
```

## Key integration point — dual-write on play

When a user plays a track, `POST /play` must:

1. INSERT into `play_history` in PostgreSQL
   → trigger auto-increments `tracks.play_count`
2. MERGE the `LISTENED_TO` edge in Neo4j (increment count property)

```python
# routes/tracks.py (pseudocode)
def log_play(user_id, track_id):
    # 1. SQL
    pg.execute("INSERT INTO play_history (user_id, track_id) VALUES (%s, %s)", (user_id, track_id))

    # 2. Neo4j
    neo4j.run("""
        MATCH (u:User {user_id: $uid}), (t:Track {track_id: $tid})
        MERGE (u)-[r:LISTENED_TO]->(t)
        ON CREATE SET r.count = 1, r.last_played = datetime()
        ON MATCH  SET r.count = r.count + 1, r.last_played = datetime()
    """, uid=user_id, tid=track_id)
```

## Environment variables (from .env)

```
DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD
NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD
FLASK_SECRET_KEY, FLASK_DEBUG
```
