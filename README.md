# Music Streaming Database — INF2003 Group Project

A database application backed by **PostgreSQL** (relational) and **Neo4j** (graph) demonstrating music streaming, playlist management, and track recommendations.

## Team & ownership

| Member | Role | Folder |
|--------|------|--------|
| M1 | Database Architect | `sql/` — schema, triggers, seed |
| M2 | SQL Developer | `sql/queries/` — CRUD, nested queries |
| M3 | NoSQL / Neo4j Developer | `nosql/` — graph schema, Cypher queries |
| M4 | Backend & Integration | `backend/` — Flask app, API routes |
| M5 | Frontend & Report Lead | `frontend/` — UI, report assembly |

## Project structure

```
music-streaming-db/
├── sql/
│   ├── schema.sql          # All CREATE TABLE statements (M1)
│   ├── triggers.sql        # Play count trigger (M1)
│   ├── seed.py             # Load Kaggle dataset into PostgreSQL (M1)
│   └── queries/            # M2 adds CRUD + complex queries here
├── nosql/
│   ├── graph_schema.md     # Neo4j node/edge design (M3)
│   └── queries/            # M3 adds Cypher scripts here
├── backend/
│   └── app.py              # Flask app entry point (M4)
├── frontend/               # HTML/CSS/JS or React (M5)
├── data/                   # Place downloaded CSV files here (gitignored)
├── docs/
│   └── erd.md              # ER diagram description
└── README.md
```

## Quick start

### Prerequisites
- Python 3.10+
- PostgreSQL 15+
- Neo4j 5+ (Community Edition)

### 1. Clone the repo

### 2. Set up Python environment
```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Configure environment variables
```bash
cp .env.example .env
# Edit .env with your PostgreSQL and Neo4j credentials
```

### 4. Create the database
```bash
createdb music_streaming        # or use pgAdmin
psql -d music_streaming -f sql/schema.sql
psql -d music_streaming -f sql/triggers.sql
```

### 5. Download the dataset
Download **Spotify Tracks Dataset** from Kaggle:
https://www.kaggle.com/datasets/maharshipandya/-spotify-tracks-dataset

Place `dataset.csv` inside the `data/` folder (already gitignored).

### 6. Seed the database
```bash
python sql/seed.py
```

### 7. Run the app (once M4 is ready)
```bash
python backend/app.py
```

## Branching convention

Work on your own branch and open a pull request to `main` when ready.

```
main
├── m1/schema-setup
├── m2/sql-queries
├── m3/neo4j-setup
├── m4/backend
└── m5/frontend
```

## Deadlines

| Date | Deliverable |
|------|-------------|
| Mon 22 Jun | Proposal & Progress Report |
| Mon 13 Jul | Slides, Video & Report |
| Fri 17 Jul | Peer Review & Supplementary Files |
