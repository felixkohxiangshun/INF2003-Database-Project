/* ============================================================
   Resonate — Music Streaming frontend logic  (INF2003, M5)
   Vanilla JS, no framework, no build step.

   HOW THIS FILE IS ORGANISED
     1. CONFIG          — flip USE_MOCK to false once M4's API is live
     2. API CONTRACT    — every backend endpoint this UI calls, with
                          the exact JSON shape it expects back. Hand
                          this section to M4/M6 so the routes match.
     3. MOCK BACKEND    — in-memory fake data so the frontend runs and
                          demos with zero backend. Mirrors the contract.
     4. STATE + HELPERS — session, toasts, formatting
     5. ROUTER          — hash routes (#/browse, #/tracks/12, …)
     6. VIEWS           — one render function per page
     7. PLAYER          — persistent now-playing bar + play logging
     8. AUTH + BOOT     — login/register wiring and startup
   ============================================================ */

/* ============================================================
   1. CONFIG
   ============================================================ */
const CONFIG = {
  // When true, the app serves data from the in-memory MOCK below.
  // When M4's Flask API is running, set this to false and point
  // API_BASE at it (Flask default is http://localhost:5000).
  USE_MOCK: true,
  API_BASE: "http://localhost:5000",
};

/* ============================================================
   2. API CONTRACT  (what the frontend asks the backend for)
   ------------------------------------------------------------
   Every method returns a Promise that resolves to the JSON
   described in its comment. M4: match these and the UI works
   untouched. All requests send cookies (credentials: include)
   for Flask session auth.

     POST   /register   {email, username, password, country}
                        -> { user: {user_id, username, email, country} }
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
   ============================================================ */

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

  register: (b) => API._req("POST", "/register", b),
  login:    (b) => API._req("POST", "/login", b),
  logout:   () => API._req("POST", "/logout"),
  me:       () => API._req("GET", "/me"),

  genres:   () => API._req("GET", "/genres"),
  tracks:   (params = {}) => {
    const qs = new URLSearchParams(
      Object.entries(params).filter(([, v]) => v != null && v !== "")
    ).toString();
    return API._req("GET", "/tracks" + (qs ? `?${qs}` : ""));
  },
  track:    (id) => API._req("GET", `/tracks/${id}`),
  play:     (track_id) => API._req("POST", "/play", { track_id }),

  playlists:      () => API._req("GET", "/playlists"),
  playlist:       (id) => API._req("GET", `/playlists/${id}`),
  createPlaylist: (b) => API._req("POST", "/playlists", b),
  updatePlaylist: (id, b) => API._req("PATCH", `/playlists/${id}`, b),
  deletePlaylist: (id) => API._req("DELETE", `/playlists/${id}`),
  addToPlaylist:  (id, track_id) => API._req("POST", `/playlists/${id}/tracks`, { track_id }),
  removeFromPlaylist: (id, track_id) => API._req("DELETE", `/playlists/${id}/tracks/${track_id}`),

  recommend: () => API._req("GET", "/recommend"),
  stats:     () => API._req("GET", "/stats"),
};

/* ============================================================
   3. MOCK BACKEND  (delete or ignore once API is live)
   ============================================================ */
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

  let session = null;            // {user_id, username, email, country}
  let nextPlaylistId = 3;

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
      session = { user_id: 99, username: body.username, email: body.email, country: (body.country || "SG").toUpperCase() };
      return { user: session };
    }
    if (route === "/login" && method === "POST") {
      const name = (body.email || "").split("@")[0] || "alice";
      session = { user_id: 1, username: name, email: body.email, country: "SG" };
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

/* ============================================================
   4. STATE + HELPERS
   ============================================================ */
const State = {
  user: null,
  genres: [],
  search: "",
  genreFilter: "",
  nowPlaying: null,   // Track currently in the player
};

const $  = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];

// Build DOM safely from a tag + props + children (avoids innerHTML for data)
function el(tag, props = {}, ...children) {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(props)) {
    if (k === "class") node.className = v;
    else if (k === "dataset") Object.assign(node.dataset, v);
    else if (k.startsWith("on") && typeof v === "function") node.addEventListener(k.slice(2).toLowerCase(), v);
    else if (v != null) node.setAttribute(k, v);
  }
  for (const c of children.flat()) {
    if (c == null || c === false) continue;
    node.append(c.nodeType ? c : document.createTextNode(String(c)));
  }
  return node;
}

const fmtDuration = (sec) => {
  const m = Math.floor(sec / 60);
  const s = sec % 60;
  return `${m}:${String(s).padStart(2, "0")}`;
};
const fmtCount = (n) => n.toLocaleString("en-US");

function toast(message, kind = "") {
  const t = el("div", { class: `toast ${kind ? "toast--" + kind : ""}` }, message);
  $("#toast-stack").append(t);
  setTimeout(() => { t.style.opacity = "0"; setTimeout(() => t.remove(), 250); }, 2800);
}

/* ============================================================
   5. ROUTER
   ============================================================ */
const routes = {
  browse:    renderBrowse,
  tracks:    renderTrackDetail,   // #/tracks/:id
  playlists: renderPlaylists,     // #/playlists  and  #/playlists/:id
  recommend: renderRecommend,
  stats:     renderStats,
};

function parseHash() {
  const raw = location.hash.replace(/^#\/?/, "");
  const [name, ...rest] = raw.split("/");
  return { name: name || "browse", params: rest };
}

async function router() {
  if (!State.user) return;
  const { name, params } = parseHash();
  const fn = routes[name] || renderBrowse;

  // highlight active nav
  $$(".nav__link").forEach((a) => a.classList.toggle("is-active", a.dataset.route === name));
  // genre chips only matter on browse
  $("#genre-chips").style.display = name === "browse" ? "flex" : "none";

  const root = $("#view-root");
  root.innerHTML = "";
  root.append(skeleton());
  try {
    const view = await fn(params);
    root.innerHTML = "";
    root.append(view);
  } catch (err) {
    root.innerHTML = "";
    root.append(errorState(err.message));
  }
  root.scrollTop = 0;
}

function go(hash) { location.hash = hash; }

/* ============================================================
   6. VIEWS
   ============================================================ */
function skeleton() {
  const wrap = el("div");
  for (let i = 0; i < 6; i++) wrap.append(el("div", { class: "skeleton-row" }));
  return wrap;
}
function errorState(msg) {
  return el("div", { class: "empty" },
    el("strong", {}, "Couldn't load this"),
    el("div", {}, msg),
    CONFIG.USE_MOCK ? null : el("div", { style: "margin-top:8px;font-size:.85rem" },
      "Is the backend running? Check CONFIG.API_BASE in app.js."));
}

/* ---- Track row (reused by Browse / Playlist / Charts) ---- */
function trackRow(t, index, opts = {}) {
  const countEl = el("span", { class: "track-row__count", title: "tracks.play_count" }, fmtCount(t.play_count ?? 0));
  const row = el("div", { class: "track-row", dataset: { trackId: t.track_id } },
    el("div", { class: "track-row__lead" },
      el("span", { class: "track-row__index" }, index),
      el("button", {
        class: "track-row__play", "aria-label": `Play ${t.title}`,
        onClick: (e) => { e.stopPropagation(); playTrack(t, countEl); },
      }, "▶")),
    el("div", { class: "track-row__main" },
      el("div", { class: "track-row__title", onClick: () => go(`#/tracks/${t.track_id}`) }, t.title),
      el("div", { class: "track-row__artist" }, t.artist + (t.album ? ` · ${t.album}` : ""))),
    t.genre ? el("span", { class: "track-row__genre" }, t.genre) : el("span"),
    countEl,
    el("span", { class: "track-row__dur" }, fmtDuration(t.duration_sec)),
  );
  if (opts.onRemove) {
    row.append(el("button", { class: "track-row__add", title: "Remove from playlist",
      onClick: (e) => { e.stopPropagation(); opts.onRemove(t); } }, "−"));
  } else {
    row.append(el("button", { class: "track-row__add", title: "Add to playlist",
      onClick: (e) => { e.stopPropagation(); openAddToPlaylist(t); } }, "+"));
  }
  return row;
}

/* ---- Browse / Search ---- */
async function renderBrowse() {
  const { tracks } = await API.tracks({ q: State.search, genre: State.genreFilter });
  const head = el("div", { class: "page-head" },
    el("p", { class: "eyebrow" }, State.search ? `results for "${State.search}"` : "browse"),
    el("h1", {}, State.genreFilter ? cap(State.genreFilter) : "All tracks"),
    el("p", {}, `${tracks.length} track${tracks.length === 1 ? "" : "s"}`));

  if (!tracks.length) {
    return el("div", {}, head, el("div", { class: "empty" },
      el("strong", {}, "No tracks match"), "Try a different search or genre."));
  }
  const list = el("div", { class: "tracklist" });
  tracks.forEach((t, i) => list.append(trackRow(t, i + 1)));
  return el("div", {}, head, list);
}

/* ---- Track detail ---- */
async function renderTrackDetail(params) {
  const { track: t } = await API.track(params[0]);
  const countVal = el("span", { class: "fact__v", dataset: { count: "1" } }, fmtCount(t.play_count));

  const detail = el("div", { class: "detail" },
    el("div", { class: "detail__cover" }, "♪"),
    el("div", {},
      el("p", { class: "eyebrow" }, t.genre || "track"),
      el("h1", { class: "detail__title" }, t.title),
      el("p", { class: "detail__sub" }, `${t.artist} · ${t.album}`),
      el("div", { class: "detail__facts" },
        fact("duration", fmtDuration(t.duration_sec)),
        el("div", { class: "fact" },
          el("span", { class: "fact__k" }, "play_count"), countVal),
        fact("track_id", `#${t.track_id}`)),
      el("div", { class: "detail__actions" },
        el("button", { class: "btn btn--primary", onClick: () => playTrack(t, countVal) }, "▶  Play"),
        el("button", { class: "btn btn--ghost", onClick: () => openAddToPlaylist(t) }, "+  Add to playlist"))));

  return el("div", {},
    el("button", { class: "btn btn--ghost btn--sm", style: "margin-bottom:20px", onClick: () => history.back() }, "← Back"),
    detail);
}
const fact = (k, v) => el("div", { class: "fact" }, el("span", { class: "fact__k" }, k), el("span", { class: "fact__v" }, v));

/* ---- Playlists (list) and Playlist detail ---- */
async function renderPlaylists(params) {
  if (params[0]) return renderPlaylistDetail(params[0]);

  const { playlists } = await API.playlists();
  const head = el("div", { class: "page-head" },
    el("p", { class: "eyebrow" }, "library"),
    el("h1", {}, "My Playlists"),
    el("p", {}, `${playlists.length} playlist${playlists.length === 1 ? "" : "s"}`));

  const grid = el("div", { class: "pl-grid" });
  grid.append(el("div", { class: "pl-card pl-card--new", onClick: openCreatePlaylist },
    el("div", { style: "font-size:1.6rem" }, "+"), el("div", {}, "New playlist")));
  playlists.forEach((p) => {
    grid.append(el("div", { class: "pl-card", onClick: () => go(`#/playlists/${p.playlist_id}`) },
      el("div", { class: "pl-card__name" }, p.name),
      el("div", { class: "pl-card__vis" }, p.is_public ? "Public" : "Private"),
      el("div", { class: "pl-card__meta" }, `${p.track_count} track${p.track_count === 1 ? "" : "s"}`)));
  });
  return el("div", {}, head, grid);
}

async function renderPlaylistDetail(id) {
  const { playlist: p } = await API.playlist(id);
  const head = el("div", { class: "page-head", style: "display:flex;justify-content:space-between;align-items:flex-end;gap:16px;flex-wrap:wrap" },
    el("div", {},
      el("p", { class: "eyebrow" }, p.is_public ? "public playlist" : "private playlist"),
      el("h1", {}, p.name),
      el("p", {}, `${p.tracks.length} track${p.tracks.length === 1 ? "" : "s"}`)),
    el("div", { style: "display:flex;gap:10px" },
      el("button", { class: "btn btn--ghost btn--sm", onClick: () => openRenamePlaylist(p) }, "Rename"),
      el("button", { class: "btn btn--danger btn--sm", onClick: () => confirmDeletePlaylist(p) }, "Delete")));

  const back = el("button", { class: "btn btn--ghost btn--sm", style: "margin-bottom:18px", onClick: () => go("#/playlists") }, "← All playlists");

  if (!p.tracks.length) {
    return el("div", {}, back, head, el("div", { class: "empty" },
      el("strong", {}, "This playlist is empty"), "Add tracks from Browse using the + button."));
  }
  const list = el("div", { class: "tracklist" });
  p.tracks.forEach((t, i) => list.append(trackRow(t, i + 1, {
    onRemove: async (track) => {
      await API.removeFromPlaylist(p.playlist_id, track.track_id);
      toast(`Removed "${track.title}"`, "ok");
      router();
    },
  })));
  return el("div", {}, back, head, list);
}

/* ---- Recommendations ---- */
async function renderRecommend() {
  const { recommendations } = await API.recommend();
  const head = el("div", { class: "page-head" },
    el("p", { class: "eyebrow" }, "from your listening graph · neo4j"),
    el("h1", {}, "For You"),
    el("p", {}, "Listeners with similar history played these."));

  if (!recommendations.length) {
    return el("div", {}, head, el("div", { class: "empty" },
      el("strong", {}, "Nothing yet"), "Play a few tracks and recommendations will appear."));
  }
  const grid = el("div", { class: "card-grid" });
  recommendations.forEach((r) => {
    grid.append(el("div", { class: "rec-card", onClick: () => go(`#/tracks/${r.track_id}`) },
      el("div", { class: "rec-card__cover" }, "♪"),
      el("div", { class: "rec-card__title" }, r.title),
      el("div", { class: "rec-card__artist" }, r.artist),
      el("span", { class: "rec-card__score" }, "✶ ", `${r.score} matches`)));
  });
  return el("div", {}, head, grid);
}

/* ---- Charts / Stats ---- */
async function renderStats() {
  const { top_tracks, top_genres } = await API.stats();
  const head = el("div", { class: "page-head" },
    el("p", { class: "eyebrow" }, "aggregated from play_history" ),
    el("h1", {}, "Charts"),
    el("p", {}, "Most-played tracks and genres across all users."));

  const maxTrack = Math.max(...top_tracks.map((t) => t.play_count), 1);
  const trackPanel = el("div", { class: "panel" }, el("h2", {}, "Top tracks"));
  top_tracks.forEach((t, i) => {
    trackPanel.append(el("div", { class: "bar-row" },
      el("div", {},
        el("div", { class: "bar-row__label", onClick: () => go(`#/tracks/${t.track_id}`), style: "cursor:pointer" },
          `${i + 1}. ${t.title}  `, el("small", {}, "· " + t.artist)),
        el("div", { class: "bar-track" }, el("div", { class: "bar-fill", style: `width:${(t.play_count / maxTrack) * 100}%` }))),
      el("div", { class: "bar-row__val" }, fmtCount(t.play_count))));
  });

  const maxGenre = Math.max(...top_genres.map((g) => g.play_count), 1);
  const genrePanel = el("div", { class: "panel" }, el("h2", {}, "Top genres"));
  top_genres.forEach((g) => {
    genrePanel.append(el("div", { class: "bar-row" },
      el("div", {},
        el("div", { class: "bar-row__label" }, cap(g.name)),
        el("div", { class: "bar-track" }, el("div", { class: "bar-fill", style: `width:${(g.play_count / maxGenre) * 100}%` }))),
      el("div", { class: "bar-row__val" }, fmtCount(g.play_count))));
  });

  return el("div", {}, head, el("div", { class: "stat-grid" }, trackPanel, genrePanel));
}

const cap = (s) => (s || "").replace(/(^|[-\s])\w/g, (m) => m.toUpperCase());

/* ============================================================
   7. PLAYER  +  play logging (the DB-trigger moment)
   ============================================================ */
async function playTrack(track, countNode) {
  State.nowPlaying = track;
  const player = $("#player");
  player.dataset.empty = "false";
  player.classList.add("is-playing");
  $("#player-title").textContent = track.title;
  $("#player-artist").textContent = track.artist;
  $("#player-cover").textContent = "♪";
  $("#player-toggle").disabled = false;
  $("#player-toggle").textContent = "⏸";

  try {
    // POST /play -> server inserts play_history; SQL trigger bumps
    // tracks.play_count; we get the fresh count back and show it tick up.
    const { play_count } = await API.play(track.track_id);
    track.play_count = play_count;

    const pcNode = $("#player-playcount");
    pcNode.textContent = fmtCount(play_count);
    bump(pcNode);
    if (countNode) { countNode.textContent = fmtCount(play_count); bump(countNode); }
  } catch (err) {
    toast(err.message, "err");
  }
}
function bump(node) { node.classList.remove("bump"); void node.offsetWidth; node.classList.add("bump"); }

function setupPlayer() {
  $("#player-toggle").addEventListener("click", () => {
    const player = $("#player");
    const playing = player.classList.toggle("is-playing");
    $("#player-toggle").textContent = playing ? "⏸" : "▶";
  });
}

/* ============================================================
   MODALS
   ============================================================ */
function modal(node) {
  const backdrop = el("div", { class: "modal-backdrop", onClick: (e) => { if (e.target === backdrop) backdrop.remove(); } }, node);
  document.body.append(backdrop);
  const close = () => backdrop.remove();
  return { close, backdrop };
}

function openCreatePlaylist() {
  const input = el("input", { type: "text", placeholder: "Playlist name", required: "" });
  const pub = el("input", { type: "checkbox", checked: "" });
  const box = el("div", { class: "modal" },
    el("h2", {}, "New playlist"),
    el("div", { class: "modal__form" },
      el("label", { class: "field" }, el("span", { class: "field__label" }, "Name"), input),
      el("label", { class: "checkbox" }, pub, "Make public"),
      el("div", { class: "modal__actions" },
        el("button", { class: "btn btn--ghost", onClick: () => m.close() }, "Cancel"),
        el("button", { class: "btn btn--primary", onClick: create }, "Create"))));
  const m = modal(box);
  input.focus();
  async function create() {
    if (!input.value.trim()) return input.focus();
    await API.createPlaylist({ name: input.value.trim(), is_public: pub.checked });
    m.close(); toast("Playlist created", "ok"); router();
  }
  input.addEventListener("keydown", (e) => { if (e.key === "Enter") create(); });
}

function openRenamePlaylist(p) {
  const input = el("input", { type: "text", value: p.name });
  const box = el("div", { class: "modal" },
    el("h2", {}, "Rename playlist"),
    el("div", { class: "modal__form" },
      el("label", { class: "field" }, el("span", { class: "field__label" }, "Name"), input),
      el("div", { class: "modal__actions" },
        el("button", { class: "btn btn--ghost", onClick: () => m.close() }, "Cancel"),
        el("button", { class: "btn btn--primary", onClick: save }, "Save"))));
  const m = modal(box); input.focus(); input.select();
  async function save() {
    await API.updatePlaylist(p.playlist_id, { name: input.value.trim() || p.name });
    m.close(); toast("Renamed", "ok"); router();
  }
}

function confirmDeletePlaylist(p) {
  const box = el("div", { class: "modal" },
    el("h2", {}, "Delete playlist?"),
    el("p", { style: "color:var(--text-dim);margin:0 0 18px" }, `"${p.name}" will be removed. This can't be undone.`),
    el("div", { class: "modal__actions" },
      el("button", { class: "btn btn--ghost", onClick: () => m.close() }, "Cancel"),
      el("button", { class: "btn btn--danger", onClick: async () => {
        await API.deletePlaylist(p.playlist_id); m.close(); toast("Playlist deleted", "ok"); go("#/playlists");
      } }, "Delete")));
  const m = modal(box);
}

async function openAddToPlaylist(track) {
  const { playlists } = await API.playlists();
  const list = el("div", { class: "modal__list" });
  if (!playlists.length) {
    list.append(el("p", { style: "color:var(--text-faint)" }, "No playlists yet — create one first."));
  }
  playlists.forEach((p) => {
    list.append(el("button", { onClick: async () => {
      await API.addToPlaylist(p.playlist_id, track.track_id);
      m.close(); toast(`Added to "${p.name}"`, "ok");
    } }, p.name, el("span", { style: "float:right;color:var(--text-faint);font-family:var(--font-mono);font-size:.78rem" }, `${p.track_count}`)));
  });
  const box = el("div", { class: "modal" },
    el("h2", {}, `Add "${track.title}"`),
    list,
    el("div", { class: "modal__actions" },
      el("button", { class: "btn btn--ghost", onClick: () => m.close() }, "Close")));
  const m = modal(box);
}

/* ============================================================
   8. AUTH + BOOT
   ============================================================ */
function showAuth() {
  $("#auth-view").hidden = false;
  $("#app-shell").hidden = true;
}
function showApp() {
  $("#auth-view").hidden = true;
  $("#app-shell").hidden = false;
  const u = State.user;
  $("#user-name").textContent = u.username;
  $("#user-avatar").textContent = (u.username || "?")[0];
  $("#user-plan").textContent = "Free plan";
}

async function enter(user) {
  State.user = user;
  showApp();
  // load genre chips once
  try {
    const { genres } = await API.genres();
    State.genres = genres;
    renderGenreChips();
  } catch (_) {}
  if (!location.hash) go("#/browse"); else router();
}

function renderGenreChips() {
  const wrap = $("#genre-chips");
  wrap.innerHTML = "";
  const all = el("button", { class: "chip" + (State.genreFilter ? "" : " is-active") }, "All");
  all.addEventListener("click", () => { State.genreFilter = ""; renderGenreChips(); router(); });
  wrap.append(all);
  State.genres.forEach((g) => {
    const chip = el("button", { class: "chip" + (State.genreFilter === g.name ? " is-active" : "") }, cap(g.name));
    chip.addEventListener("click", () => {
      State.genreFilter = State.genreFilter === g.name ? "" : g.name;
      renderGenreChips(); router();
    });
    wrap.append(chip);
  });
}

function setupAuthForms() {
  // tab switching
  $$(".auth__tab").forEach((tab) => tab.addEventListener("click", () => {
    $$(".auth__tab").forEach((t) => t.classList.remove("is-active"));
    tab.classList.add("is-active");
    const isLogin = tab.dataset.authTab === "login";
    $("#login-form").hidden = !isLogin;
    $("#register-form").hidden = isLogin;
  }));

  $("#login-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const f = new FormData(e.target);
    try {
      const { user } = await API.login({ email: f.get("email"), password: f.get("password") });
      enter(user);
    } catch (err) { toast(err.message, "err"); }
  });

  $("#register-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const f = new FormData(e.target);
    try {
      const { user } = await API.register({
        email: f.get("email"), username: f.get("username"),
        password: f.get("password"), country: (f.get("country") || "").toUpperCase(),
      });
      enter(user);
    } catch (err) { toast(err.message, "err"); }
  });

  $("#logout-btn").addEventListener("click", async () => {
    try { await API.logout(); } catch (_) {}
    State.user = null;
    location.hash = "";
    showAuth();
  });
}

// search input (debounced)
let searchTimer;
function setupSearch() {
  $("#search-input").addEventListener("input", (e) => {
    State.search = e.target.value.trim();
    clearTimeout(searchTimer);
    searchTimer = setTimeout(() => {
      if (parseHash().name !== "browse") go("#/browse"); else router();
    }, 250);
  });
}

async function boot() {
  setupAuthForms();
  setupSearch();
  setupPlayer();
  window.addEventListener("hashchange", router);

  // Check for an existing session (mock returns null until login)
  try {
    const { user } = await API.me();
    if (user) return enter(user);
  } catch (_) {}
  showAuth();
}

document.addEventListener("DOMContentLoaded", boot);