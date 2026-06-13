"""
test_m4_api.py
==============
API integration tests for M4's Flask backend.

Tests (in order):
  1.  Health check         — GET  /health
  2.  Register             — POST /auth/register
  3.  Duplicate register   — POST /auth/register (same email/username)
  4.  Login (wrong pass)   — POST /auth/login
  5.  Login                — POST /auth/login
  6.  Get profile          — GET  /auth/me
  7.  Update profile       — PUT  /auth/me
  8.  Change password      — PUT  /auth/password
  9.  List genres          — GET  /genres
  10. List tracks          — GET  /tracks
  11. Search tracks        — GET  /tracks?q=...
  12. Get track by ID      — GET  /tracks/<id>
  13. Get track (missing)  — GET  /tracks/99999999
  14. List artists         — GET  /artists
  15. Get artist by ID     — GET  /artists/<id>
  16. Follow artist        — POST /artists/<id>/follow
  17. Follow status        — GET  /artists/<id>/follow
  18. Unfollow artist      — DELETE /artists/<id>/follow
  19. Create playlist      — POST /playlists
  20. List my playlists    — GET  /playlists/mine
  21. List public playlists— GET  /playlists
  22. Get playlist         — GET  /playlists/<id>
  23. Update playlist      — PUT  /playlists/<id>
  24. Add track to playlist— POST /playlists/<id>/tracks
  25. Remove track         — DELETE /playlists/<id>/tracks/<tid>
  26. Delete playlist      — DELETE /playlists/<id>
  27. Logout               — POST /auth/logout
  28. Auth guard check     — GET  /auth/me (after logout)

Usage:
    # In a separate terminal, start the Flask app first:
    FLASK_PORT=5001 python3 -m backend.app

    # Then run this script:
    cd INF2003-Database-Project
    source venv/bin/activate
    python3 backend/test_m4_api.py
"""

import sys
import requests

BASE_URL = "http://localhost:5001"

# Test user credentials
TEST_EMAIL    = "m4test@example.com"
TEST_USERNAME = "m4testuser"
TEST_PASSWORD = "testpass123"
NEW_PASSWORD  = "newpass456"

PASS = "\033[92m[PASS]\033[0m"
FAIL = "\033[91m[FAIL]\033[0m"
INFO = "\033[94m[INFO]\033[0m"

results  = []
session  = requests.Session()  # maintains cookies across requests
track_id   = None
artist_id  = None
playlist_id = None


def check(label, condition, detail=""):
    if condition:
        print(f"  {PASS} {label}")
        results.append((label, True, None))
    else:
        print(f"  {FAIL} {label}" + (f"\n         {detail}" if detail else ""))
        results.append((label, False, detail))

def section(title, description=""):
    print(f"\n{'=' * 60}")
    print(title)
    if description:
        print(f"  {description}")
    print('=' * 60)


# ── Test functions ─────────────────────────────────────────────────────────────

def test_health():
    section("TEST 1 — Health Check", "GET /health")
    r = session.get(f"{BASE_URL}/health")
    check("Status 200", r.status_code == 200, r.text)
    check("PostgreSQL up", r.json().get("postgresql") == "up")
    check("Status ok", r.json().get("status") == "ok")


def test_register():
    global track_id, artist_id
    section("TEST 2 — Register", "POST /auth/register")

    # Clean up any leftover test user from previous runs
    # (done via login + delete, or just let duplicate check handle it)

    r = session.post(f"{BASE_URL}/auth/register", json={
        "email":    TEST_EMAIL,
        "username": TEST_USERNAME,
        "password": TEST_PASSWORD,
        "country":  "SG",
    })
    # 201 = created, 409 = already exists from previous run (acceptable)
    check("Status 201 or 409", r.status_code in (201, 409), r.text)
    if r.status_code == 201:
        data = r.json()
        check("Returns user_id", "user_id" in data)
        check("Returns username", data.get("username") == TEST_USERNAME)
        check("Returns email", data.get("email") == TEST_EMAIL)


def test_duplicate_register():
    section("TEST 3 — Duplicate Register", "POST /auth/register (same credentials)")

    r = session.post(f"{BASE_URL}/auth/register", json={
        "email":    TEST_EMAIL,
        "username": TEST_USERNAME,
        "password": TEST_PASSWORD,
    })
    check("Status 409 for duplicate email/username", r.status_code == 409, r.text)


def test_login_wrong_password():
    section("TEST 4 — Login (wrong password)", "POST /auth/login")
    r = session.post(f"{BASE_URL}/auth/login", json={
        "email":    TEST_EMAIL,
        "password": "wrongpassword",
    })
    check("Status 401 for wrong password", r.status_code == 401, r.text)


def test_login():
    section("TEST 5 — Login", "POST /auth/login")
    r = session.post(f"{BASE_URL}/auth/login", json={
        "email":    TEST_EMAIL,
        "password": TEST_PASSWORD,
    })
    check("Status 200", r.status_code == 200, r.text)
    data = r.json()
    check("Returns user_id", "user_id" in data)
    check("Returns username", data.get("username") == TEST_USERNAME)


def test_get_profile():
    section("TEST 6 — Get Profile", "GET /auth/me")
    r = session.get(f"{BASE_URL}/auth/me")
    check("Status 200", r.status_code == 200, r.text)
    data = r.json()
    check("Returns user_id", "user_id" in data)
    check("Returns current_plan", "current_plan" in data)
    check("Auto-assigned Free plan", data.get("current_plan") == "Free")


def test_update_profile():
    section("TEST 7 — Update Profile", "PUT /auth/me")
    r = session.put(f"{BASE_URL}/auth/me", json={"username": "m4updated"})
    check("Status 200", r.status_code == 200, r.text)
    check("Username updated", r.json().get("username") == "m4updated")

    # Restore username
    session.put(f"{BASE_URL}/auth/me", json={"username": TEST_USERNAME})


def test_change_password():
    section("TEST 8 — Change Password", "PUT /auth/password")

    # Wrong current password
    r = session.put(f"{BASE_URL}/auth/password", json={
        "current_password": "wrongpass",
        "new_password":     NEW_PASSWORD,
    })
    check("Status 401 for wrong current password", r.status_code == 401, r.text)

    # Correct change
    r = session.put(f"{BASE_URL}/auth/password", json={
        "current_password": TEST_PASSWORD,
        "new_password":     NEW_PASSWORD,
    })
    check("Status 200 for valid change", r.status_code == 200, r.text)

    # Verify new password works
    r = session.post(f"{BASE_URL}/auth/login", json={
        "email": TEST_EMAIL, "password": NEW_PASSWORD
    })
    check("Can login with new password", r.status_code == 200, r.text)


def test_list_genres():
    section("TEST 9 — List Genres", "GET /genres")
    r = session.get(f"{BASE_URL}/genres")
    check("Status 200", r.status_code == 200, r.text)
    data = r.json()
    check("Returns a list", isinstance(data, list))
    check("Has genres (seeded 113)", len(data) >= 100)
    check("Each genre has genre_id and name", all("genre_id" in g and "name" in g for g in data[:5]))


def test_list_tracks():
    global track_id
    section("TEST 10 — List Tracks", "GET /tracks")
    r = session.get(f"{BASE_URL}/tracks?limit=5")
    check("Status 200", r.status_code == 200, r.text)
    data = r.json()
    check("Returns a list", isinstance(data, list))
    check("Returns up to 5 tracks", len(data) <= 5)
    if data:
        track_id = data[0]["track_id"]
        check("Track has required fields", all(
            k in data[0] for k in ("track_id", "track_title", "artist_name", "genre_name")
        ))


def test_search_tracks():
    section("TEST 11 — Search Tracks", "GET /tracks?q=love")
    r = session.get(f"{BASE_URL}/tracks?q=love&limit=5")
    check("Status 200", r.status_code == 200, r.text)
    data = r.json()
    check("Returns list", isinstance(data, list))
    if data:
        titles = [t["track_title"].lower() + t.get("artist_name","").lower() + t.get("album_title","").lower()
                  for t in data]
        check("Results contain search term", any("love" in t for t in titles))


def test_get_track():
    section("TEST 12 — Get Track by ID", f"GET /tracks/{track_id}")
    if not track_id:
        print(f"  {INFO} Skipped — no track_id from previous test")
        return
    r = session.get(f"{BASE_URL}/tracks/{track_id}")
    check("Status 200", r.status_code == 200, r.text)
    data = r.json()
    check("Returns correct track_id", data.get("track_id") == track_id)
    check("Has artist info", "artist_name" in data)
    check("Has album info", "album_title" in data)


def test_get_track_missing():
    section("TEST 13 — Get Track (missing)", "GET /tracks/99999999")
    r = session.get(f"{BASE_URL}/tracks/99999999")
    check("Status 404", r.status_code == 404, r.text)


def test_list_artists():
    global artist_id
    section("TEST 14 — List Artists", "GET /artists")
    r = session.get(f"{BASE_URL}/artists?limit=5")
    check("Status 200", r.status_code == 200, r.text)
    data = r.json()
    check("Returns a list", isinstance(data, list))
    if data:
        artist_id = data[0]["artist_id"]
        check("Artist has required fields", all(
            k in data[0] for k in ("artist_id", "name")
        ))


def test_get_artist():
    section("TEST 15 — Get Artist by ID", f"GET /artists/{artist_id}")
    if not artist_id:
        print(f"  {INFO} Skipped — no artist_id from previous test")
        return
    r = session.get(f"{BASE_URL}/artists/{artist_id}")
    check("Status 200", r.status_code == 200, r.text)
    data = r.json()
    check("Returns correct artist_id", data.get("artist_id") == artist_id)
    check("Has albums list", "albums" in data)


def test_follow_artist():
    section("TEST 16 — Follow Artist", f"POST /artists/{artist_id}/follow")
    if not artist_id:
        print(f"  {INFO} Skipped — no artist_id")
        return
    r = session.post(f"{BASE_URL}/artists/{artist_id}/follow")
    check("Status 201", r.status_code == 201, r.text)
    check("following is True", r.json().get("following") is True)


def test_follow_status():
    section("TEST 17 — Follow Status", f"GET /artists/{artist_id}/follow")
    if not artist_id:
        print(f"  {INFO} Skipped — no artist_id")
        return
    r = session.get(f"{BASE_URL}/artists/{artist_id}/follow")
    check("Status 200", r.status_code == 200, r.text)
    check("following is True", r.json().get("following") is True)


def test_unfollow_artist():
    section("TEST 18 — Unfollow Artist", f"DELETE /artists/{artist_id}/follow")
    if not artist_id:
        print(f"  {INFO} Skipped — no artist_id")
        return
    r = session.delete(f"{BASE_URL}/artists/{artist_id}/follow")
    check("Status 200", r.status_code == 200, r.text)
    check("following is False", r.json().get("following") is False)


def test_create_playlist():
    global playlist_id
    section("TEST 19 — Create Playlist", "POST /playlists")
    r = session.post(f"{BASE_URL}/playlists", json={
        "name": "My Test Playlist",
        "is_public": True,
    })
    check("Status 201", r.status_code == 201, r.text)
    data = r.json()
    check("Returns playlist_id", "playlist_id" in data)
    check("Name matches", data.get("name") == "My Test Playlist")
    playlist_id = data.get("playlist_id")


def test_my_playlists():
    section("TEST 20 — My Playlists", "GET /playlists/mine")
    r = session.get(f"{BASE_URL}/playlists/mine")
    check("Status 200", r.status_code == 200, r.text)
    data = r.json()
    check("Returns a list", isinstance(data, list))
    check("Contains created playlist", any(p["playlist_id"] == playlist_id for p in data))


def test_list_public_playlists():
    section("TEST 21 — List Public Playlists", "GET /playlists")
    r = session.get(f"{BASE_URL}/playlists?limit=5")
    check("Status 200", r.status_code == 200, r.text)
    check("Returns a list", isinstance(r.json(), list))


def test_get_playlist():
    section("TEST 22 — Get Playlist", f"GET /playlists/{playlist_id}")
    if not playlist_id:
        print(f"  {INFO} Skipped — no playlist_id")
        return
    r = session.get(f"{BASE_URL}/playlists/{playlist_id}")
    check("Status 200", r.status_code == 200, r.text)
    data = r.json()
    check("Returns playlist_id", data.get("playlist_id") == playlist_id)
    check("Has tracks list", "tracks" in data)


def test_update_playlist():
    section("TEST 23 — Update Playlist", f"PUT /playlists/{playlist_id}")
    if not playlist_id:
        print(f"  {INFO} Skipped — no playlist_id")
        return
    r = session.put(f"{BASE_URL}/playlists/{playlist_id}", json={"name": "Renamed Playlist"})
    check("Status 200", r.status_code == 200, r.text)
    check("Name updated", r.json().get("name") == "Renamed Playlist")


def test_add_track():
    section("TEST 24 — Add Track to Playlist", f"POST /playlists/{playlist_id}/tracks")
    if not playlist_id or not track_id:
        print(f"  {INFO} Skipped — missing playlist_id or track_id")
        return
    r = session.post(f"{BASE_URL}/playlists/{playlist_id}/tracks", json={"track_id": track_id})
    check("Status 201 or 200", r.status_code in (201, 200), r.text)
    if r.status_code == 201:
        check("Returns track_id", r.json().get("track_id") == track_id)


def test_remove_track():
    section("TEST 25 — Remove Track from Playlist", f"DELETE /playlists/{playlist_id}/tracks/{track_id}")
    if not playlist_id or not track_id:
        print(f"  {INFO} Skipped — missing playlist_id or track_id")
        return
    r = session.delete(f"{BASE_URL}/playlists/{playlist_id}/tracks/{track_id}")
    check("Status 200", r.status_code == 200, r.text)
    check("Message confirms removal", "removed" in r.json().get("message", "").lower())


def test_delete_playlist():
    section("TEST 26 — Delete Playlist", f"DELETE /playlists/{playlist_id}")
    if not playlist_id:
        print(f"  {INFO} Skipped — no playlist_id")
        return
    r = session.delete(f"{BASE_URL}/playlists/{playlist_id}")
    check("Status 200", r.status_code == 200, r.text)

    # Verify it's gone
    r2 = session.get(f"{BASE_URL}/playlists/{playlist_id}")
    check("Playlist no longer accessible after delete", r2.status_code == 404)


def test_logout():
    section("TEST 27 — Logout", "POST /auth/logout")
    r = session.post(f"{BASE_URL}/auth/logout")
    check("Status 200", r.status_code == 200, r.text)
    check("Message confirms logout", "logged out" in r.json().get("message", "").lower())


def test_auth_guard():
    section("TEST 28 — Auth Guard", "GET /auth/me after logout")
    r = session.get(f"{BASE_URL}/auth/me")
    check("Status 401 after logout", r.status_code == 401, r.text)


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    print(f"\n{INFO} Testing Flask API at {BASE_URL}")
    print(f"{INFO} Make sure the server is running: FLASK_PORT=5001 python3 -m backend.app\n")

    # Quick connectivity check
    try:
        requests.get(f"{BASE_URL}/health", timeout=3)
    except requests.ConnectionError:
        print(f"\n{FAIL} Cannot connect to {BASE_URL}. Is the Flask server running?")
        sys.exit(1)

    test_health()
    test_register()
    test_duplicate_register()
    test_login_wrong_password()
    test_login()
    test_get_profile()
    test_update_profile()
    test_change_password()
    test_list_genres()
    test_list_tracks()
    test_search_tracks()
    test_get_track()
    test_get_track_missing()
    test_list_artists()
    test_get_artist()
    test_follow_artist()
    test_follow_status()
    test_unfollow_artist()
    test_create_playlist()
    test_my_playlists()
    test_list_public_playlists()
    test_get_playlist()
    test_update_playlist()
    test_add_track()
    test_remove_track()
    test_delete_playlist()
    test_logout()
    test_auth_guard()

    # Summary
    print(f"\n{'=' * 60}")
    print("SUMMARY")
    print('=' * 60)
    passed = [r for r in results if r[1]]
    failed = [r for r in results if not r[1]]
    print(f"  {PASS} {len(passed)} passed")
    if failed:
        print(f"  {FAIL} {len(failed)} failed:")
        for label, _, err in failed:
            print(f"       • {label}: {err}")
    else:
        print(f"\n  All API tests passed. M4 is ready to merge.")
    print()


if __name__ == "__main__":
    main()
