# Graph Schema Definition

## Node Labels
- **User**: Represents listeners.
  - Properties:
    - `user_id` (Primary Key)
    - `username`

- **Track**: Represents songs.
  - Properties:
    - `track_id` (Primary Key)
    - `title`
    - `genre`

- **Artist**: Represents music creators.
  - Properties:
    - `artist_id` (Primary Key)
    - `name`


## Relationship Types
- `(User)-[:LISTENED_TO {count, last_played}]->(Track)`
- `(User)-[:FOLLOWS {followed_at}]->(Artist)`
- `(Track)-[:PERFORMED_BY]->(Artist)`
- `(Artist)-[:SIMILAR_TO {similarity_score}]->(Artist)`