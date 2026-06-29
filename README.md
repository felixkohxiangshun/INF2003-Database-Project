# Resonate - Music Streaming & Recommendation App

A full-stack music streaming and recommendation application built for INF2003 Database Systems. Demonstrates dual-database architecture with **PostgreSQL** (relational) for persistent storage and **Neo4j** (graph) for relationship-based recommendations.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python 3, Flask 3 |
| Relational DB | PostgreSQL 15+ with psycopg2 connection pool |
| Graph DB | Neo4j 5+ with Bolt driver |
| Frontend | Vanilla JS (SPA with hash router), HTML5, CSS3 |

---

## Team

| Member | Name | Role | Primary Files |
|---|---|---|---|
| M1 | Felix Koh | Database Architect | `sql/schema.sql`, `sql/triggers.sql`, `sql/seed.py` |
| M2 | Wong Jun Kai | SQL Developer | `sql/queries/` — CRUD, nested queries, analysis |
| M3 | Vania Teng | NoSQL / Neo4j Developer | `nosql/` — graph schema, Cypher queries, sync |
| M4 | Tan Yan Ting | Backend & Integration | `backend/` — Flask app, API routes, middleware |
| M5 | Ning Haiquan | Backend & Integration | `backend/` - Graph app, Recommendation engine, History routes |
| M6 | Liew Jia Jun| Frontend | `frontend/` — HTML templates, CSS design |

---

## Project Structure

```
INF2003-Database-Project/
├── sql/
│   ├── schema.sql                  Table definitions (9 tables + audit_log)
│   ├── triggers.sql                3 triggers (see below)
│   ├── seed.py                     Loads Kaggle dataset into PostgreSQL
│   └── queries/
│       ├── crud_users.sql
│       ├── crud_tracks.sql
│       ├── crud_playlists.sql
│       ├── nested_queries.sql      CTEs, window functions, relational division
│       └── analysis.sql
│
├── nosql/
│   ├── graph_schema.md             Node/edge design doc
│   ├── setup.cypher                Constraints and indexes for Neo4j
│   ├── sync.py                     One-time bulk sync from PostgreSQL → Neo4j
│   └── queries/
│       ├── crud.cypher
│       └── recommendations.cypher
│
├── backend/
│   ├── app.py                      Flask app factory, blueprint registration
│   ├── db.py                       PostgreSQL connection pool helpers
│   ├── graph.py                    Neo4j driver + query helpers
│   ├── utils.py                    Shared serialization helper
│   ├── startup_sync.py             Background Neo4j sync on startup
│   ├── middleware/
│   │   └── auth_required.py        Session auth guard decorator
│   └── routes/
│       ├── auth.py                 Register, login, profile, password
│       ├── tracks.py               Browse, search, play, follow artist
│       ├── playlist.py             Playlist CRUD + track management
│       ├── history.py              Play history
│       ├── recommendations.py      Neo4j collaborative filtering
│       ├── artists.py              Artist graph routes
│       ├── admin.py                Admin CRUD (tracks/artists/albums/genres)
│       └── insights.py             Live nested query endpoints
│
├── frontend/
│   ├── index.html
│   ├── css/
│   │   ├── variables.css           Design tokens (colours, fonts, radii)
│   │   ├── components.css          Shared button, field, panel components
│   │   ├── layout.css              Nav, sidebar, main content
│   │   ├── browse.css              Track list, track detail
│   │   ├── charts.css              Stats, genre breakdown
│   │   ├── playlists.css
│   │   ├── profile.css
│   │   ├── admin.css               Admin panel
│   │   └── ...
│   └── js/
│       ├── config.js               API client + mock fallback
│       ├── helpers.js              DOM builder (el), formatters, toast
│       ├── router.js               Hash-based SPA router
│       ├── player.js               Audio player state
│       ├── auth.js                 Login/register forms
│       ├── modals.js               Add-to-playlist modal
│       └── views/
│           ├── browse.js           Track list + detail page
│           ├── playlists.js        Playlist manager
│           ├── charts.js           Stats + top-by-genre
│           ├── recommendations.js  Neo4j recommendations view
│           ├── graph.js            Artist relationship graph
│           ├── explore.js          Artist explorer
│           ├── profile.js          User profile + audit log
│           └── admin.js            Admin CRUD panel
│
├── data/
│   └── dataset.csv                 Kaggle Spotify dataset (not committed)
│
├── .env                            Local credentials (not committed)
├── .env.example                    Template for .env
├── requirements.txt
└── README.md
```

---

## Prerequisites

Before starting, ensure the following are installed on your machine:

| Requirement | Version | Check |
|---|---|---|
| Python | 3.10+ | `python3 --version` (macOS) / `python --version` (Windows) |
| pip | latest | bundled with Python |
| PostgreSQL | 15+ | running locally on port 5432 |
| Neo4j Desktop or Community | 5+ | running locally on ports 7474 / 7687 |
| Git | any | `git --version` |

---

### Install Python

**macOS:**
```bash
brew install python@3.11
```
Or download the installer from https://www.python.org/downloads/

**Windows:**
Download and run the installer from https://www.python.org/downloads/
> During installation, check **"Add Python to PATH"**.

---

### Install PostgreSQL

**macOS:**
```bash
brew install postgresql@15
brew services start postgresql@15
```

**Windows:**
Download the installer from https://www.postgresql.org/download/windows/
Run the installer (includes pgAdmin and `psql`). Note the password you set for the `postgres` user.

> After installation on Windows, add PostgreSQL's `bin` folder to your PATH so `psql` and `createdb` are available in the terminal:
> `C:\Program Files\PostgreSQL\15\bin`

---

### Install Neo4j

**macOS and Windows:**
Download **Neo4j Desktop** from https://neo4j.com/download/ — this is the easiest option. After installing:
1. Open Neo4j Desktop
2. Create a new **Local DBMS**
3. Set a password and note it down
4. Click **Start** to run the database

> Neo4j runs on bolt://localhost:7687 (Bolt) and http://localhost:7474 (Browser UI) by default.

---

## Step-by-Step Setup

### 1. Clone the repository

**macOS:**
```bash
git clone <repo-url>
cd INF2003-Database-Project
```

**Windows (Command Prompt or PowerShell):**
```cmd
git clone <repo-url>
cd INF2003-Database-Project
```

---

### 2. Create a Python virtual environment

**macOS:**
```bash
python3 -m venv venv
source venv/bin/activate
```

**Windows (Command Prompt):**
```cmd
python -m venv venv
venv\Scripts\activate.bat
```

**Windows (PowerShell):**
```powershell
python -m venv venv
venv\Scripts\Activate.ps1
```

> If PowerShell blocks script execution, run first:
> `Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser`

When active, your terminal prompt will show `(venv)`. To deactivate later, run `deactivate`.

---

### 3. Install Python dependencies

**macOS and Windows (with venv active):**
```bash
pip install -r requirements.txt
```

Dependencies installed:
- `psycopg2-binary` — PostgreSQL driver
- `pandas` — dataset loading
- `python-dotenv` — .env file loader
- `flask` — web framework
- `flask-cors` — cross-origin headers
- `neo4j` — Neo4j Bolt driver
- `bcrypt` — password hashing

---

### 4. Configure environment variables

**macOS:**
```bash
cp .env.example .env
```

**Windows (Command Prompt):**
```cmd
copy .env.example .env
```

**Windows (PowerShell):**
```powershell
Copy-Item .env.example .env
```

Open `.env` in any text editor and fill in your credentials:

```env
# PostgreSQL
DB_HOST=localhost
DB_PORT=5432
DB_NAME=music_streaming
DB_USER=<your_postgres_username>
DB_PASSWORD=<your_postgres_password>

# Neo4j
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=<your_neo4j_password>

# Flask
SECRET_KEY=<generate a random key — see below>
FLASK_DEBUG=1
FLASK_PORT=8080
```

**Generate a SECRET_KEY:**

macOS:
```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

Windows:
```cmd
python -c "import secrets; print(secrets.token_hex(32))"
```

---

### 5. Create the PostgreSQL database

**macOS:**
```bash
createdb music_streaming
```

**Windows (Command Prompt — run as the postgres user):**
```cmd
createdb -U postgres music_streaming
```

**Alternative (both platforms) — via pgAdmin:**
1. Open pgAdmin
2. Right-click **Databases** → **Create** → **Database**
3. Name it `music_streaming` and click Save

---

### 6. Apply the schema and triggers

**macOS:**
```bash
psql -d music_streaming -f sql/schema.sql
psql -d music_streaming -f sql/triggers.sql
```

**Windows:**
```cmd
psql -U postgres -d music_streaming -f sql/schema.sql
psql -U postgres -d music_streaming -f sql/triggers.sql
```

> If `psql` is not found on Windows, use the full path:
> `"C:\Program Files\PostgreSQL\15\bin\psql.exe" -U postgres -d music_streaming -f sql/schema.sql`

This creates:
- **9 tables:** `users`, `genres`, `artists`, `albums`, `tracks`, `play_history`, `playlists`, `playlist_tracks`, `user_follows_artist`
- **1 audit table:** `audit_log`
- **3 triggers:**
  - `trg_increment_play_count` — increments `tracks.play_count` after every play (denormalised aggregate)
  - `trg_audit_users` — logs email/username/password changes to `audit_log`
  - `trg_prevent_duplicate_playlist_track` — blocks duplicate tracks in a playlist at the DB level

---

### 7. Download the dataset

Download the **Spotify Tracks Dataset** from Kaggle:
https://www.kaggle.com/datasets/maharshipandya/-spotify-tracks-dataset

Place `dataset.csv` inside the `data/` folder:
```
data/dataset.csv
```

---

### 8. Seed PostgreSQL

**macOS and Windows (with venv active):**
```bash
python3 sql/seed.py      # macOS
python sql/seed.py       # Windows
```

This parses `dataset.csv` and loads artists, albums, genres, and tracks into PostgreSQL. Expect ~100 genres and thousands of artists and tracks.

---

### 9. Set up Neo4j

**a) Create constraints and indexes**

Open Neo4j Browser at http://localhost:7474, log in with your credentials, and paste the contents of `nosql/setup.cypher` into the query box, then run it.

Alternatively, if you have `cypher-shell` available:

**macOS:**
```bash
cypher-shell -u neo4j -p <your_password> -f nosql/setup.cypher
```

**Windows:**
```cmd
cypher-shell -u neo4j -p <your_password> -f nosql/setup.cypher
```

> `cypher-shell` is bundled with Neo4j Desktop. On Windows, find it at:
> `C:\Users\<you>\.Neo4jDesktop\relate-data\dbmss\<dbms-id>\bin\cypher-shell.bat`

**b) Sync PostgreSQL data into Neo4j**

**macOS:**
```bash
python3 nosql/sync.py
```

**Windows:**
```cmd
python nosql/sync.py
```

This creates `Track`, `Artist`, and `User` nodes and `PERFORMED_BY` edges in Neo4j. The Flask app also runs this automatically in the background on startup.

---

### 10. Run the application

**macOS:**
```bash
python3 -m backend.app
```

**Windows:**
```cmd
python -m backend.app
```

Open **http://localhost:8080** in your browser.

> Always use `python3 -m backend.app` / `python -m backend.app` (not `python3 backend/app.py`) so Python resolves the `backend` package imports correctly.

**Demo accounts:**
```
Email:    alice@example.com   Password: password123
Email:    bob@example.com     Password: password123
```

Or register a new account from the login page.


---

## Features

| Feature | Description |
|---|---|
| Browse & Search | Browse all tracks; search by title, artist, or album; filter by genre |
| Track Detail | Per-user play count + global play count; play, add to playlist, follow artist |
| Playlists | Create, rename, reorder, delete playlists; add/remove tracks |
| Play History | View your listening history |
| Recommendations | Collaborative filtering via Neo4j LISTENED_TO graph |
| Artist Graph | Visualise artist relationships |
| Charts & Stats | Top 10 tracks overall; top 5 tracks per genre this month |
| Admin Panel | Full CRUD for tracks, artists, albums, genres; audit log viewer |
| Insights | Live endpoints for 4 nested SQL queries (CTE + window functions, relational division, collaborative filtering, HAVING subquery) |

---

## Database Design

### PostgreSQL — Key Tables

| Table | Purpose |
|---|---|
| `users` | Account credentials (bcrypt hashed passwords) |
| `tracks` | Track catalogue with denormalised `play_count` |
| `play_history` | Per-user play log (source of truth for counts) |
| `user_follows_artist` | Follow relationships |
| `playlist_tracks` | Ordered track list with `position` |
| `audit_log` | Tamper-evident log of user field changes |

### Neo4j — Nodes and Edges

| Nodes | Properties |
|---|---|
| `User` | user_id, username |
| `Artist` | artist_id, name |
| `Track` | track_id, title, genre, play_count |

| Edges | Meaning |
|---|---|
| `(User)-[:LISTENED_TO]->(Track)` | Listening history with count + last_played |
| `(User)-[:FOLLOWS]->(Artist)` | Follow relationship with followed_at |
| `(Track)-[:PERFORMED_BY]->(Artist)` | Track authorship |
| `(Track)-[:SIMILAR_TO]->(Track)` | Similarity edges (sync.py) |

### Dual-Write Pattern

Every write that affects both databases is done synchronously in the same request:
- `POST /play` → INSERT into `play_history` (Postgres) + MERGE `LISTENED_TO` edge (Neo4j)
- `POST /artists/<id>/follow` → INSERT into `user_follows_artist` (Postgres) + MERGE `FOLLOWS` edge (Neo4j)
- `PUT /auth/me` → UPDATE `users` (Postgres) + SET `u.username` on User node (Neo4j)

---

## API Endpoints

| Method | Path | Description |
|---|---|---|
| POST | `/auth/register` | Create account |
| POST | `/auth/login` | Login |
| GET/PUT | `/auth/me` | Get / update profile |
| PUT | `/auth/password` | Change password |
| GET | `/tracks` | List / search tracks |
| GET | `/tracks/<id>` | Track detail with user + global plays |
| POST | `/play` | Log a play (triggers + Neo4j write) |
| GET/POST/DELETE | `/artists/<id>/follow` | Follow status / follow / unfollow |
| GET/POST | `/playlists` | List public / create playlist |
| GET | `/playlists/mine` | My playlists |
| GET/PUT/DELETE | `/playlists/<id>` | Get / update / delete playlist |
| POST/DELETE | `/playlists/<id>/tracks` | Add / remove track |
| GET | `/recommend` | Neo4j collaborative filtering |
| GET | `/stats` | Top tracks + play counts |
| GET | `/insights/top-by-genre` | Top 5 per genre (CTE + window function) |
| GET | `/artists/top-performers` | Artists above genre average (HAVING subquery) |
| GET/POST | `/admin/tracks` | Admin: list / create tracks |
| PUT/DELETE | `/admin/tracks/<id>` | Admin: edit / delete track |
| GET | `/admin/audit-log` | View audit log entries |
| GET | `/health` | PostgreSQL + Neo4j health check |
