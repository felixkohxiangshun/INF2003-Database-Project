const CONFIG = {
  // When true, the app serves data from the in-memory MOCK below instead of the Flask API.
  USE_MOCK: false,
  API_BASE: "",  // empty = same origin as Flask server (http://localhost:5001)
};

/* API contract — what the frontend expects the Flask backend to return.
   All requests send cookies (credentials: include) for Flask session auth.

     POST   /register   {email, username, password}
                        -> { user: {user_id, username, email} }
     POST   /login      {email, password}
                        -> { user: {...} }
     POST   /logout     -> { ok: true }
     GET    /me         -> { user: {...} | null }     (session check)

     GET    /genres     -> { genres: [{genre_id, name}] }
     GET    /tracks?q=&genre=&sort=&limit=
                        -> { tracks: [Track] }
     GET    /tracks/:id -> { track: Track }

     POST   /play       {track_id}
                        -> { ok: true, play_count: <new int> }
              (server INSERTs into play_history; the SQL trigger
               trg_increment_play_count bumps tracks.play_count,
               which is the value returned here.)

     GET    /playlists           -> { playlists: [{playlist_id, name, is_public, track_count}] }
     POST   /playlists           {name, is_public} -> { playlist: {...} }
     GET    /playlists/:id       -> { playlist: {playlist_id, name, is_public, tracks: [Track w/ position]} }
     PATCH  /playlists/:id       {name?, is_public?} -> { playlist: {...} }
     DELETE /playlists/:id       -> { ok: true }
     POST   /playlists/:id/tracks   {track_id} -> { ok: true, position }
     DELETE /playlists/:id/tracks/:track_id -> { ok: true }

     GET    /recommend  -> { recommendations: [{track_id, title, artist, score}] }
     GET    /stats      -> { top_tracks:  [{track_id, title, artist, play_count}],
                             top_genres:  [{name, play_count}] }

   Track = {
     track_id, title, artist, album, genre,
     duration_sec, play_count
   }
*/

const API = {
  async _req(method, path, body) {
    if (CONFIG.USE_MOCK) return Mock.handle(method, path, body);
    const res = await fetch(CONFIG.API_BASE + path, {
      method,
      credentials: "include",
      headers: body ? { "Content-Type": "application/json" } : undefined,
      body: body ? JSON.stringify(body) : undefined,
    });
    let data = null;
    try { data = await res.json(); } catch (_) { /* no body */ }
    if (!res.ok) throw new Error((data && data.error) || `Request failed (${res.status})`);
    return data;
  },

  // Auth — M4 uses /auth/* prefix and returns user object directly (not wrapped in { user })
  register: async (b) => { const d = await API._req("POST", "/auth/register", b); return { user: d }; },
  login:    async (b) => { const d = await API._req("POST", "/auth/login", b);    return { user: d }; },
  logout:   () => API._req("POST", "/auth/logout"),
  me:       async () => {
    try { const d = await API._req("GET", "/auth/me"); return { user: d }; }
    catch (_) { return { user: null }; }
  },

  // Catalogue — M4 returns arrays directly (not wrapped in { tracks } / { genres })
  genres:   async () => { const d = await API._req("GET", "/genres"); return { genres: d }; },
  tracks:   async (params = {}) => {
    const qs = new URLSearchParams(
      Object.entries(params).filter(([, v]) => v != null && v !== "")
    ).toString();
    const d = await API._req("GET", "/tracks" + (qs ? `?${qs}` : ""));
    // M4 field names: track_title, artist_name, album_title, genre_name — normalise to what M5 expects
    const normalise = (t) => ({
      ...t,
      title:      t.track_title  ?? t.title,
      artist:     t.artist_name  ?? t.artist,
      album:      t.album_title  ?? t.album,
      genre:      t.genre_name   ?? t.genre,
      user_plays: t.user_plays   ?? 0,
    });
    return { tracks: d.map(normalise) };
  },
  track: async (id) => {
    const t = await API._req("GET", `/tracks/${id}`);
    return { track: {
      ...t,
      title:     t.track_title  ?? t.title,
      artist:    t.artist_name  ?? t.artist,
      album:     t.album_title  ?? t.album,
      genre:     t.genre_name   ?? t.genre,
      artist_id: t.artist_id    ?? null,
    }};
  },

  // Play logging — not yet implemented in M4; gracefully no-op so player still works
  play: async (track_id) => {
    try { return await API._req("POST", "/play", { track_id }); }
    catch (_) { return { play_count: null }; }
  },

  // Playlists — M4 uses /playlists/mine for own playlists, PUT not PATCH
  playlists: async () => {
    const d = await API._req("GET", "/playlists/mine");
    return { playlists: d };
  },
  playlist: async (id) => {
    const d = await API._req("GET", `/playlists/${id}`);
    // M4 returns { playlist_id, playlist_name, tracks: [{track_title, artist_name,...}] }
    const normTrack = (t) => ({
      ...t,
      title:  t.track_title  ?? t.title,
      artist: t.artist_name  ?? t.artist,
      album:  t.album_title  ?? t.album,
      genre:  t.genre_name   ?? t.genre,
    });
    return { playlist: { ...d, name: d.playlist_name ?? d.name, tracks: (d.tracks || []).map(normTrack) }};
  },
  createPlaylist: async (b) => { const d = await API._req("POST", "/playlists", b); return { playlist: d }; },
  updatePlaylist: (id, b) => API._req("PUT", `/playlists/${id}`, b),   // M4 uses PUT not PATCH
  deletePlaylist: (id) => API._req("DELETE", `/playlists/${id}`),
  addToPlaylist:  (id, track_id) => API._req("POST", `/playlists/${id}/tracks`, { track_id }),
  removeFromPlaylist: (id, track_id) => API._req("DELETE", `/playlists/${id}/tracks/${track_id}`),
  moveTrack: (id, track_id, position) => API._req("PUT", `/playlists/${id}/tracks/${track_id}/position`, { position }),

  recommend: async () => {
    try { return await API._req("GET", "/recommend"); }
    catch (_) { return { recommendations: [] }; }
  },
  recommendArtists: async () => {
    try { return await API._req("GET", "/recommend/artists"); }
    catch (_) { return { artists: [] }; }
  },
  artists: async (limit = 20) => {
    try {
      const d = await API._req("GET", `/artists?limit=${limit}`);
      return { artists: Array.isArray(d) ? d : (d.artists ?? []) };
    } catch (_) { return { artists: [] }; }
  },
  artistPath: async (fromId, toId) => {
    return API._req("GET", `/artists/path?from_id=${fromId}&to_id=${toId}`);
  },
  userGraph: async () => {
    try { return await API._req("GET", "/graph/user"); }
    catch (_) { return { nodes: [], links: [] }; }
  },
  stats: async () => {
    try { return await API._req("GET", "/stats"); }
    catch (_) { return { top_tracks: [], top_genres: [] }; }
  },

  // Insights — exposed nested query endpoints
  topByGenre: async () => {
    try { return await API._req("GET", "/insights/top-by-genre"); }
    catch (_) { return { genres: {} }; }
  },
  relatedArtists: async (artistId) => {
    try { return await API._req("GET", `/artists/${artistId}/related`); }
    catch (_) { return { related: [] }; }
  },
  playlistCompletionists: async (playlistId) => {
    try { return await API._req("GET", `/playlists/${playlistId}/completionists`); }
    catch (_) { return { completionists: [] }; }
  },
  topPerformers: async () => {
    try { return await API._req("GET", "/artists/top-performers"); }
    catch (_) { return { artists: [] }; }
  },

  // Admin CRUD
  adminTracks: {
    create: (body)     => API._req("POST",   "/admin/tracks",       body),
    update: (id, body) => API._req("PUT",    `/admin/tracks/${id}`, body),
    delete: (id)       => API._req("DELETE", `/admin/tracks/${id}`),
  },
  adminArtists: {
    create: (body)     => API._req("POST",   "/admin/artists",       body),
    update: (id, body) => API._req("PUT",    `/admin/artists/${id}`, body),
    delete: (id)       => API._req("DELETE", `/admin/artists/${id}`),
  },
  adminAlbums: {
    create: (body)     => API._req("POST",   "/admin/albums",       body),
    update: (id, body) => API._req("PUT",    `/admin/albums/${id}`, body),
    delete: (id)       => API._req("DELETE", `/admin/albums/${id}`),
  },

  artist: async (id) => {
    try { return await API._req("GET", `/artists/${id}`); }
    catch (_) { return null; }
  },
  profile: async () => {
    try { return await API._req("GET", "/auth/profile"); }
    catch (_) { return null; }
  },

  followStatus: async (artistId) => {
    try { return await API._req("GET", `/artists/${artistId}/follow`); }
    catch (_) { return { following: false }; }
  },
  followArtist:   (artistId) => API._req("POST",   `/artists/${artistId}/follow`),
  unfollowArtist: (artistId) => API._req("DELETE",  `/artists/${artistId}/follow`),
};

// Mock backend — used only when CONFIG.USE_MOCK is true
const Mock = (() => {
  const genres = [
    { genre_id: 1, name: "pop" }, { genre_id: 2, name: "rock" },
    { genre_id: 3, name: "hip-hop" }, { genre_id: 4, name: "jazz" },
    { genre_id: 5, name: "electronic" }, { genre_id: 6, name: "r-n-b" },
    { genre_id: 7, name: "indie" }, { genre_id: 8, name: "classical" },
  ];

  let tracks = [
    { track_id: 1,  title: "Midnight Commuter",   artist: "Neon Tide",      album: "After Hours",      genre: "electronic", duration_sec: 214, play_count: 18432 },
    { track_id: 2,  title: "Paper Boats",          artist: "Marlowe Sun",    album: "Quiet Rooms",      genre: "indie",      duration_sec: 187, play_count: 9120 },
    { track_id: 3,  title: "Glass Avenue",         artist: "The Off-Hours",  album: "Glass Avenue",     genre: "rock",       duration_sec: 243, play_count: 27310 },
    { track_id: 4,  title: "Velvet Static",        artist: " Caro",          album: "Lowlight",         genre: "r-n-b",      duration_sec: 201, play_count: 15022 },
    { track_id: 5,  title: "Cassette Summer",      artist: "Marlowe Sun",    album: "Quiet Rooms",      genre: "indie",      duration_sec: 176, play_count: 6740 },
    { track_id: 6,  title: "Brass & Rain",         artist: "Hideo Quartet",  album: "Late Set",         genre: "jazz",       duration_sec: 298, play_count: 4310 },
    { track_id: 7,  title: "Concrete Garden",      artist: "Neon Tide",      album: "After Hours",      genre: "electronic", duration_sec: 229, play_count: 21004 },
    { track_id: 8,  title: "Northbound",           artist: "The Off-Hours",  album: "Glass Avenue",     genre: "rock",       duration_sec: 256, play_count: 13388 },
    { track_id: 9,  title: "Slow Tokyo",           artist: "Hideo Quartet",  album: "Late Set",         genre: "jazz",       duration_sec: 312, play_count: 3902 },
    { track_id: 10, title: "Overpass",             artist: "Kite Theory",    album: "Signal",           genre: "hip-hop",    duration_sec: 198, play_count: 33871 },
    { track_id: 11, title: "Saltwater Logic",      artist: "Kite Theory",    album: "Signal",           genre: "hip-hop",    duration_sec: 184, play_count: 28190 },
    { track_id: 12, title: "Porcelain Sky",        artist: "caro",           album: "Lowlight",         genre: "r-n-b",      duration_sec: 222, play_count: 11760 },
    { track_id: 13, title: "Etude in Amber",       artist: "L. Vasquez",     album: "Nocturnes",        genre: "classical",  duration_sec: 341, play_count: 2055 },
    { track_id: 14, title: "Daylight Robbery",     artist: "The Off-Hours",  album: "Glass Avenue",     genre: "rock",       duration_sec: 211, play_count: 18920 },
    { track_id: 15, title: "Polaroid Heat",        artist: "Sunday Mode",    album: "Filters",          genre: "pop",        duration_sec: 193, play_count: 41203 },
    { track_id: 16, title: "Low Orbit",            artist: "Neon Tide",      album: "After Hours",      genre: "electronic", duration_sec: 268, play_count: 9540 },
  ];

  let playlists = [
    { playlist_id: 1, name: "Late Night Coding", is_public: true,  trackIds: [1, 7, 16, 10] },
    { playlist_id: 2, name: "Rainy Commute",     is_public: false, trackIds: [2, 5, 6] },
  ];

  let session = null;            // {user_id, username, email}
  let nextPlaylistId = 3;
  const followed = new Set();   // mock: set of followed artist_ids

  const findTrack = (id) => tracks.find((t) => t.track_id === Number(id));
  const ok = (extra = {}) => ({ ok: true, ...extra });
  const slim = (t) => ({ ...t });

  async function handle(method, path, body) {
    // simulate light network latency so loading states are visible
    await new Promise((r) => setTimeout(r, 180));
    const [route, query] = path.split("?");
    const params = new URLSearchParams(query || "");
    const parts = route.split("/").filter(Boolean); // e.g. ["playlists","1","tracks"]

    // ---- auth ----
    if (route === "/register" && method === "POST") {
      session = { user_id: 99, username: body.username, email: body.email };
      return { user: session };
    }
    if (route === "/login" && method === "POST") {
      const name = (body.email || "").split("@")[0] || "alice";
      session = { user_id: 1, username: name, email: body.email };
      return { user: session };
    }
    if (route === "/logout") { session = null; return ok(); }
    if (route === "/me") return { user: session };

    // ---- catalogue ----
    if (route === "/genres") return { genres };

    if (route === "/tracks" && method === "GET") {
      let out = tracks.slice();
      const q = (params.get("q") || "").toLowerCase();
      const genre = params.get("genre");
      const sort = params.get("sort");
      if (q) out = out.filter((t) =>
        t.title.toLowerCase().includes(q) ||
        t.artist.toLowerCase().includes(q) ||
        t.album.toLowerCase().includes(q));
      if (genre) out = out.filter((t) => t.genre === genre);
      if (sort === "play_count") out.sort((a, b) => b.play_count - a.play_count);
      return { tracks: out.map(slim) };
    }

    if (parts[0] === "tracks" && parts[1] && method === "GET") {
      const t = findTrack(parts[1]);
      return t ? { track: slim(t) } : Promise.reject(new Error("Track not found"));
    }

    if (route === "/play" && method === "POST") {
      const t = findTrack(body.track_id);
      if (!t) return Promise.reject(new Error("Track not found"));
      t.play_count += 1;                 // mimic the SQL trigger
      return ok({ play_count: t.play_count });
    }

    // ---- playlists ----
    if (route === "/playlists" && method === "GET") {
      return { playlists: playlists.map((p) => ({
        playlist_id: p.playlist_id, name: p.name, is_public: p.is_public, track_count: p.trackIds.length,
      })) };
    }
    if (route === "/playlists" && method === "POST") {
      const p = { playlist_id: nextPlaylistId++, name: body.name, is_public: !!body.is_public, trackIds: [] };
      playlists.push(p);
      return { playlist: { playlist_id: p.playlist_id, name: p.name, is_public: p.is_public, track_count: 0 } };
    }
    if (parts[0] === "playlists" && parts[1] && !parts[2]) {
      const p = playlists.find((x) => x.playlist_id === Number(parts[1]));
      if (!p) return Promise.reject(new Error("Playlist not found"));
      if (method === "GET") {
        const ts = p.trackIds.map((id, i) => ({ ...findTrack(id), position: i + 1 })).filter((t) => t.track_id);
        return { playlist: { playlist_id: p.playlist_id, name: p.name, is_public: p.is_public, tracks: ts } };
      }
      if (method === "PATCH") {
        if (body.name != null) p.name = body.name;
        if (body.is_public != null) p.is_public = !!body.is_public;
        return { playlist: { playlist_id: p.playlist_id, name: p.name, is_public: p.is_public, track_count: p.trackIds.length } };
      }
      if (method === "DELETE") {
        playlists = playlists.filter((x) => x.playlist_id !== p.playlist_id);
        return ok();
      }
    }
    if (parts[0] === "playlists" && parts[2] === "tracks") {
      const p = playlists.find((x) => x.playlist_id === Number(parts[1]));
      if (!p) return Promise.reject(new Error("Playlist not found"));
      if (method === "POST") {
        if (!p.trackIds.includes(Number(body.track_id))) p.trackIds.push(Number(body.track_id));
        return ok({ position: p.trackIds.length });
      }
      if (method === "DELETE") {
        p.trackIds = p.trackIds.filter((id) => id !== Number(parts[3]));
        return ok();
      }
    }

    // ---- recommendations (would come from Neo4j traversal) ----
    if (route === "/recommend") {
      const recs = tracks.slice().sort((a, b) => b.play_count - a.play_count).slice(2, 10)
        .map((t, i) => ({ track_id: t.track_id, title: t.title, artist: t.artist, score: 42 - i * 4 }));
      return { recommendations: recs };
    }
    if (route === "/recommend/artists") {
      return { artists: [
        { artist_id: 1, name: "Neon Tide",     bio: "Electronic duo from Tokyo.", track_count: 3 },
        { artist_id: 2, name: "Hideo Quartet", bio: "Jazz ensemble.",             track_count: 2 },
      ]};
    }
    if (route === "/artists/path") {
      return { path: [
        { artist_id: 1, name: "Neon Tide" },
        { artist_id: 3, name: "The Off-Hours" },
        { artist_id: 2, name: "Hideo Quartet" },
      ], hops: 2 };
    }
    if (route === "/artists") {
      const unique = [...new Map(tracks.map(t => [t.artist, { artist_id: tracks.indexOf(t) + 1, name: t.artist }])).values()];
      return unique;
    }

    // ---- follow / unfollow ----
    if (parts[0] === "artists" && parts[2] === "follow") {
      const aid = Number(parts[1]);
      if (method === "GET")    return { following: followed.has(aid) };
      if (method === "POST")   { followed.add(aid);    return ok({ following: true }); }
      if (method === "DELETE") { followed.delete(aid); return ok({ following: false }); }
    }

    // ---- insights ----
    if (route === "/insights/top-by-genre") return { genres: {} };
    if (route === "/artists/top-performers") return { artists: [] };
    if (parts[0] === "artists" && parts[2] === "related") return { related: [] };
    if (parts[0] === "playlists" && parts[2] === "completionists") return { completionists: [] };

    // ---- admin ----
    if (route === "/admin/genres") return genres;
    if (route === "/admin/audit-log") return [];

    // ---- stats (nested SQL query demo) ----
    if (route === "/stats") {
      const top_tracks = tracks.slice().sort((a, b) => b.play_count - a.play_count).slice(0, 8)
        .map((t) => ({ track_id: t.track_id, title: t.title, artist: t.artist, play_count: t.play_count }));
      const byGenre = {};
      tracks.forEach((t) => { byGenre[t.genre] = (byGenre[t.genre] || 0) + t.play_count; });
      const top_genres = Object.entries(byGenre).map(([name, play_count]) => ({ name, play_count }))
        .sort((a, b) => b.play_count - a.play_count);
      return { top_tracks, top_genres };
    }

    return Promise.reject(new Error(`Mock has no handler for ${method} ${route}`));
  }

  return { handle };
})();
