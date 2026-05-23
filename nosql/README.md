# NoSQL / Neo4j — M3 (Graph DB Developer)

## What goes here

```
nosql/
├── graph_schema.md         # Node labels, relationship types, properties
├── setup.cypher            # Create constraints + indexes in Neo4j
├── sync.py                 # Reads from PostgreSQL, writes to Neo4j
└── queries/
    ├── crud.cypher         # Basic Cypher CRUD operations
    └── recommendations.cypher  # Graph traversal recommendation query
```

## Node labels to implement

| Label | Key properties | Source table |
|-------|---------------|--------------|
| `User` | user_id, username | `users` |
| `Track` | track_id, title | `tracks` |
| `Artist` | artist_id, name, genre | `artists` |

## Relationship types to implement

| Type | From → To | Properties | Source |
|------|-----------|------------|--------|
| `LISTENED_TO` | User → Track | count, last_played | `play_history` |
| `FOLLOWS` | User → Artist | followed_at | `user_follows_artist` |
| `PERFORMED_BY` | Track → Artist | — | derived from albums join |
| `SIMILAR_TO` | Artist → Artist | similarity_score | computed (no SQL equivalent) |

## Key recommendation query (to implement in recommendations.cypher)

```cypher
// "Users who listened to what you listened to also listened to…"
MATCH (u:User {user_id: $user_id})-[:LISTENED_TO]->(t:Track)
      <-[:LISTENED_TO]-(similar:User)-[:LISTENED_TO]->(rec:Track)
WHERE NOT (u)-[:LISTENED_TO]->(rec)
RETURN rec.title, rec.track_id, count(similar) AS score
ORDER BY score DESC
LIMIT 10
```

## Sync approach

`sync.py` should run after `sql/seed.py`. It:
1. Reads users, tracks, artists from PostgreSQL
2. Writes them as nodes into Neo4j
3. Reads `play_history` and creates `LISTENED_TO` edges
4. Reads `user_follows_artist` and creates `FOLLOWS` edges

For the live app, M4's backend will do dual-writes on each new play event.

## Report section to write

- Justify why a graph DB (not SQL) is the right model for recommendations
- Compare the Cypher traversal query vs equivalent SQL recursive join
- Discuss whether the Neo4j model is derived from or independent of the SQL schema
- Pros and cons of each approach
