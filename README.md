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
INF2003 Database Project/
├── sql/                                M1 + M2
│   ├── schema.sql                      M1
│   ├── triggers.sql                    M1
│   ├── seed.py                         M1
│   └── queries/                        M2
│       ├── crud_users.sql              M2
│       ├── crud_tracks.sql             M2
│       ├── crud_playlists.sql          M2
│       ├── nested_queries.sql          M2
│       └── analysis.sql                M2
│ 
├── nosql/                              M3
│   ├── graph_schema.md                 M3
│   ├── setup.cypher                    M3
│   ├── sync.py                         M3
│   └── queries/                        M3
│       ├── crud.cypher                 M3
│       └── recommendations.cypher      M3
│ 
├── backend/                            M4 + M6
│   ├── app.py                          M4
│   ├── db.py                           M4
│   ├── middleware/                     M4
│   │   └── auth_required.py            M4
│   ├── graph.py                        M6      
│   └── routes/                         M4 + M6
│           ├── auth.py                 M4
│           ├── tracks.py               M4
│           ├── playlist.py             M4
│           ├── recommendations.py      M6
│           └── history.py              M6
│
│     
├── frontend/                           M5
│   ├── index.html                      M5
│   ├── style.css                       M5
│   └── app.js                          M5
│
├── data/  
│   └── dataset.csv           
│      
├── .env.example
├── .gitignore
├── requirements.txt        
└── README.md

```

## Quick start

### Prerequisites
- Python 3.10+
- PostgreSQL 15+ (running locally, e.g. via pgAdmin or Homebrew)
- Neo4j 5+ Community Edition (running locally on default ports 7474/7687)

### 1. Clone the repo

### 2. Set up Python environment
```bash
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Configure environment variables
```bash
cp .env.example .env
# Edit .env with your PostgreSQL and Neo4j credentials
```

### 4. Create the database and apply schema
```bash
createdb music_streaming        # or create via pgAdmin
psql -d music_streaming -f sql/schema.sql
psql -d music_streaming -f sql/triggers.sql
```

### 5. Download the dataset
Download the **Spotify Tracks Dataset** from Kaggle:
https://www.kaggle.com/datasets/maharshipandya/-spotify-tracks-dataset

Place `dataset.csv` inside the `data/` folder.

### 6. Seed PostgreSQL
```bash
python3 sql/seed.py
```

### 7. Set up Neo4j constraints and sync data
```bash
# In Neo4j Browser (http://localhost:7474), run:
# :source nosql/setup.cypher

# Then from terminal:
python3 nosql/sync.py
```

### 8. Run the app
```bash
python3 backend/app.py
```

Open http://localhost:5001 in your browser.

**Demo credentials:** alice@example.com / password123  or  bob@example.com / password123

## Deadlines

| Date | Deliverable |
|------|-------------|
| Mon 22 Jun | Proposal & Progress Report |
| Mon 13 Jul | Slides, Video & Report |
| Fri 17 Jul | Peer Review & Supplementary Files |
