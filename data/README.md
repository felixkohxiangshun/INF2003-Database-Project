# Data

This folder holds raw dataset files. It is **gitignored** — do not commit CSV files.

## Dataset to download

**Spotify Tracks Dataset** by Maharshi Pandya  
https://www.kaggle.com/datasets/maharshipandya/-spotify-tracks-dataset

### Steps

1. Create a free Kaggle account if you don't have one
2. Go to the link above and click **Download**
3. Unzip and place `dataset.csv` in this `data/` folder
4. Run `python sql/seed.py` from the project root

### What the seed script uses

| CSV column | Maps to |
|------------|---------|
| `artists` | `artists.name` (first artist in semicolon list) |
| `album_name` | `albums.title` |
| `track_name` | `tracks.title` |
| `track_genre` | `genres.name` |
| `duration_ms` | `tracks.duration_sec` (converted ÷ 1000) |

Audio feature columns (`danceability`, `energy`, `tempo`, etc.) are not loaded into PostgreSQL — they will be used by M3 to compute `SIMILAR_TO` edge weights in Neo4j.
