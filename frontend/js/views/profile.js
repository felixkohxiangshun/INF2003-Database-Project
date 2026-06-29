/* ============================================================
   Resonate — Profile view
   Displays user info and listening stats pulled from PostgreSQL.
   ============================================================ */

async function renderProfile() {
  const data = await API.profile();

  const wrap = el("div", {});

  if (!data) {
    wrap.append(el("div", { class: "empty" },
      el("strong", {}, "Could not load profile"),
      "Please try again."));
    return wrap;
  }

  // Format member since date
  const joined = data.created_at
    ? new Date(data.created_at).toLocaleDateString("en-GB", { year: "numeric", month: "long", day: "numeric" })
    : "—";

  // ── Header ────────────────────────────────────────────────────────────
  const header = el("div", { class: "profile-header" },
    el("div", { class: "profile-avatar" }, (data.username || "?")[0].toUpperCase()),
    el("div", { class: "profile-header__meta" },
      el("h1", { class: "profile-header__name" }, data.username),
      el("p",  { class: "profile-header__email" }, data.email),
      el("p",  { class: "profile-header__joined" }, `Member since ${joined}`)));

  // ── Stats grid ────────────────────────────────────────────────────────
  const statsData = [
    { label: "Total plays",      value: fmtCount(data.total_plays    ?? 0), sub: "play_history rows" },
    { label: "Unique tracks",    value: fmtCount(data.unique_tracks  ?? 0), sub: "distinct tracks"   },
    { label: "Artists followed", value: data.artists_followed ?? 0,         sub: "user_follows_artist" },
    { label: "Playlists",        value: data.playlist_count   ?? 0,         sub: "created by you"   },
  ];

  const stats = el("div", { class: "profile-stats" },
    ...statsData.map(({ label, value, sub }) =>
      el("div", { class: "profile-stat" },
        el("div", { class: "profile-stat__value" }, String(value)),
        el("div", { class: "profile-stat__label" }, label),
        el("div", { class: "profile-stat__sub" }, sub))));

  // ── Top genre pill ────────────────────────────────────────────────────
  const genreRow = data.top_genre
    ? el("div", { class: "profile-genre" },
        el("span", { class: "profile-genre__label" }, "Top genre"),
        el("span", { class: "track-row__genre" }, data.top_genre))
    : null;

  // ── Account info panel ────────────────────────────────────────────────
  const infoPanel = el("div", { class: "panel", style: "margin-top:22px" },
    el("h2", {}, "Account"),
    el("div", { class: "profile-info" },
      infoRow("user_id",   `#${data.user_id}`),
      infoRow("username",  data.username),
      infoRow("email",     data.email),
      infoRow("joined",    joined)));

  wrap.append(header, stats, genreRow, infoPanel);
  return wrap;
}

function infoRow(key, val) {
  return el("div", { class: "profile-info__row" },
    el("span", { class: "profile-info__key" }, key),
    el("span", { class: "profile-info__val" }, val));
}
