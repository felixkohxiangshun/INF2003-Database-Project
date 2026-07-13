"""Artist graph routes.

These use Neo4j instead of SQL because SIMILAR_TO traversal needs multi-hop
joins SQL can't express cleanly, and shortestPath() has no SQL equivalent
without recursive CTEs of unknown depth.
"""

from __future__ import annotations

import logging

from flask import Blueprint, g, jsonify, request

from backend.db import query, query_one
from backend.graph import neo4j_query
from backend.middleware.auth_required import auth_required

log = logging.getLogger(__name__)
bp  = Blueprint("artists_graph", __name__)


@bp.route("/recommend/artists", methods=["GET"])
@auth_required
def recommend_artists():
    """Score = total plays of the bridging artist the user already listens to."""
    user_id = g.user_id

    recs = neo4j_query(
        """
        MATCH (u:User {user_id: $user_id})-[r:LISTENED_TO]->(t:Track)
              -[:PERFORMED_BY]->(a:Artist)
        WITH u, a, sum(r.count) AS affinity
        MATCH (a)-[:SIMILAR_TO]-(similar:Artist)
        WHERE NOT EXISTS {
            MATCH (u)-[:LISTENED_TO]->(:Track)-[:PERFORMED_BY]->(similar)
        }
        AND NOT (u)-[:FOLLOWS]->(similar)
        RETURN similar.artist_id AS artist_id,
               similar.name      AS name,
               sum(affinity)     AS score
        ORDER BY score DESC
        LIMIT 6
        """,
        {"user_id": user_id},
    )

    if not recs:
        return jsonify({"artists": []})

    # enrich with bio + track count from PostgreSQL
    artist_ids = [r["artist_id"] for r in recs]
    scores     = {r["artist_id"]: r["score"] for r in recs}

    rows = query(
        """
        SELECT ar.artist_id,
               ar.name,
               ar.bio,
               COUNT(DISTINCT t.track_id) AS track_count
        FROM   artists ar
        LEFT JOIN albums al ON al.artist_id = ar.artist_id
        LEFT JOIN tracks t  ON t.album_id   = al.album_id
        WHERE  ar.artist_id = ANY(%(ids)s)
        GROUP  BY ar.artist_id, ar.name, ar.bio
        """,
        {"ids": artist_ids},
    )

    artist_map = {r["artist_id"]: dict(r) for r in rows}
    result = []
    for aid in artist_ids:
        if aid in artist_map:
            a = artist_map[aid]
            a["score"] = scores[aid]
            result.append(a)

    return jsonify({"artists": result})


@bp.route("/artists/path", methods=["GET"])
@auth_required
def artist_path():
    """Shortest SIMILAR_TO path between two artists via Neo4j shortestPath()."""
    from_id = request.args.get("from_id", type=int)
    to_id   = request.args.get("to_id",   type=int)

    if not from_id or not to_id:
        return jsonify({"error": "from_id and to_id are required"}), 400
    if from_id == to_id:
        return jsonify({"error": "Choose two different artists"}), 400

    result = neo4j_query(
        """
        MATCH (a1:Artist {artist_id: $from_id}),
              (a2:Artist {artist_id: $to_id})
        MATCH path = shortestPath((a1)-[:SIMILAR_TO*1..8]-(a2))
        RETURN [n IN nodes(path) | {artist_id: n.artist_id, name: n.name}]
                 AS path_nodes,
               length(path) AS hops
        """,
        {"from_id": from_id, "to_id": to_id},
    )

    if not result:
        return jsonify({"path": None, "hops": None,
                        "message": "No connection found — these artists share no genre links."})

    row = result[0]
    return jsonify({"path": row["path_nodes"], "hops": row["hops"]})


@bp.route("/graph/user", methods=["GET"])
@auth_required
def user_graph():
    """Logged-in user's listening subgraph as nodes + links for D3."""
    user_id = g.user_id

    listened = neo4j_query(
        """
        MATCH (u:User {user_id: $user_id})-[r:LISTENED_TO]->(t:Track)
              -[:PERFORMED_BY]->(a:Artist)
        RETURN t.track_id  AS track_id,
               t.title     AS title,
               t.genre     AS genre,
               a.artist_id AS artist_id,
               a.name      AS artist_name,
               r.count     AS play_count
        ORDER BY r.count DESC LIMIT 20
        """,
        {"user_id": user_id},
    )

    if not listened:
        return jsonify({"nodes": [], "links": [],
                        "message": "No listening history yet — play some tracks first."})

    user_row = query_one(
        "SELECT username FROM users WHERE user_id = %(id)s", {"id": user_id}
    )
    username = user_row["username"] if user_row else "User"

    nodes = {}
    links = []
    seen_links = set()

    nodes[f"u{user_id}"] = {
        "id": f"u{user_id}", "label": username,
        "type": "User", "meta": f"user_id: {user_id}",
    }

    for row in listened:
        tid = f"t{row['track_id']}"
        aid = f"a{row['artist_id']}"
        title = (row["title"] or "Unknown")[:28]

        if tid not in nodes:
            nodes[tid] = {
                "id": tid, "label": title,
                "type": "Track",
                "meta": f"{row['genre'] or 'unknown'} · {row['play_count']} plays",
            }
        if aid not in nodes:
            nodes[aid] = {
                "id": aid, "label": row["artist_name"] or "Unknown",
                "type": "Artist", "meta": row["artist_name"] or "",
            }

        k1 = f"u{user_id}->{tid}"
        if k1 not in seen_links:
            links.append({"source": f"u{user_id}", "target": tid,
                          "type": "LISTENED_TO", "count": row["play_count"]})
            seen_links.add(k1)

        k2 = f"{tid}->{aid}"
        if k2 not in seen_links:
            links.append({"source": tid, "target": aid, "type": "PERFORMED_BY"})
            seen_links.add(k2)

    # SIMILAR_TO edges between artists already in the subgraph
    artist_ids = [int(k[1:]) for k in nodes if k.startswith("a")]
    if len(artist_ids) > 1:
        similar = neo4j_query(
            """
            MATCH (a1:Artist)-[:SIMILAR_TO]-(a2:Artist)
            WHERE a1.artist_id IN $ids AND a2.artist_id IN $ids
              AND a1.artist_id < a2.artist_id
            RETURN a1.artist_id AS from_id, a2.artist_id AS to_id
            """,
            {"ids": artist_ids},
        )
        for s in (similar or []):
            links.append({
                "source": f"a{s['from_id']}",
                "target": f"a{s['to_id']}",
                "type": "SIMILAR_TO",
            })

    return jsonify({"nodes": list(nodes.values()), "links": links})
