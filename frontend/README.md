# Frontend — M5 (Frontend & Report Lead)

## Suggested pages

| Page | Route | Key features |
|------|-------|-------------|
| Login / Register | `/login` | Form → POST /login | EDIT: login is located at base url
| Home / Browse | `/` | Search tracks, browse genres | EDIT: under /browse
| Track detail | `/tracks/<id>` | Play button, add to playlist |
| My Playlists | `/playlists` | Create, edit, delete playlists |
| Recommendations | `/recommend` | Cards from Neo4j traversal |
| Admin / Stats | `/stats` | Top tracks by play_count (nested SQL query demo) |

## Tech choice

Plain HTML + CSS + vanilla JS is fine — this is a DB module, not a frontend module. Keep it simple so your demo is stable.

Alternatively: React + fetch() to the Flask API if the team is comfortable.

## Report assembly checklist (M5 owns this)

Collect the following from each member and assemble into the final report:

- [ ] M1: ER diagram, schema design rationale, normalisation justification
- [ ] M2: CRUD SQL, trigger explanation, nested query walkthrough
- [ ] M3: Neo4j schema, Cypher queries, SQL vs NoSQL comparison
- [ ] M4: System architecture, dual-write explanation, API design
- [ ] Everyone: GenAI reflection (M3 drafts, everyone reviews)
- [ ] Optional: performance analysis (M2 + M3)

## Video demo script (suggested flow)

1. Register a new user → shows INSERT + subscription trigger
2. Browse and play 3 tracks → shows play_history inserts + play_count trigger firing
3. Create a playlist and add tracks → shows many-to-many junction table
4. Open Recommendations page → shows Neo4j traversal result
5. Show pgAdmin / Neo4j Browser side by side briefly

Aim for 5–8 minutes.
