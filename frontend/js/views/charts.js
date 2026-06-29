/* ============================================================
   Resonate — Charts / Stats view

   Three sections:
     1. Top tracks overall (GET /stats)
     2. Top genres overall (GET /stats)
     3. Top 5 per genre this month — CTE + ROW_NUMBER() window
        function (GET /insights/top-by-genre, nested_queries.sql #1)
   ============================================================ */

async function renderStats() {
  const [statsData, topByGenreData] = await Promise.all([
    API.stats(),
    API.topByGenre(),
  ]);

  const { top_tracks, top_genres } = statsData;

  const head = el("div", { class: "page-head" },
    el("p", { class: "eyebrow" }, "aggregated from play_history"),
    el("h1", {}, "Charts"),
    el("p", {}, "Most-played tracks and genres across all users."));

  // ── Top tracks ─────────────────────────────────────────────
  const maxTrack = Math.max(...top_tracks.map((t) => t.play_count), 1);
  const trackPanel = el("div", { class: "panel" }, el("h2", {}, "Top Tracks"));
  top_tracks.forEach((t, i) => {
    trackPanel.append(el("div", { class: "bar-row" },
      el("div", {},
        el("div", { class: "bar-row__label", onClick: () => go(`#/tracks/${t.track_id}`), style: "cursor:pointer" },
          `${i + 1}. ${t.title}  `, el("small", {}, "· " + t.artist)),
        el("div", { class: "bar-track" }, el("div", { class: "bar-fill", style: `width:${(t.play_count / maxTrack) * 100}%` }))),
      el("div", { class: "bar-row__val" }, fmtCount(t.play_count))));
  });

  // ── Top genres ─────────────────────────────────────────────
  const maxGenre = Math.max(...top_genres.map((g) => g.play_count), 1);
  const genrePanel = el("div", { class: "panel" }, el("h2", {}, "Top Genres"));
  top_genres.forEach((g) => {
    genrePanel.append(el("div", { class: "bar-row" },
      el("div", {},
        el("div", { class: "bar-row__label" }, cap(g.name)),
        el("div", { class: "bar-track" }, el("div", { class: "bar-fill", style: `width:${(g.play_count / maxGenre) * 100}%` }))),
      el("div", { class: "bar-row__val" }, fmtCount(g.play_count))));
  });

  // ── Top 5 per genre this month — window function ────────────
  const genreBreakdown = buildTopByGenrePanel(topByGenreData);

  return el("div", {},
    head,
    el("div", { class: "stat-grid" }, trackPanel, genrePanel),
    genreBreakdown);
}

function buildTopByGenrePanel({ genres }) {
  const section = el("div", { class: "panel" });
  section.append(
    el("h2", {}, "Top 5 Tracks Per Genre — This Month"),
    el("p", { class: "panel__sub" },
      el("code", {}, "ROW_NUMBER() OVER (PARTITION BY genre_id ORDER BY plays DESC)"),
      " — nested_queries.sql #1"),
  );

  const genreNames = Object.keys(genres || {});

  if (!genreNames.length) {
    section.append(el("div", { class: "empty" },
      el("strong", {}, "No plays this month yet"),
      "Play some tracks to see per-genre charts."));
    return section;
  }

  const grid = el("div", { class: "genre-breakdown-grid" });

  genreNames.forEach((genreName) => {
    const tracks = genres[genreName];
    const box = el("div", { class: "genre-breakdown-box" });

    box.append(el("p", { class: "genre-breakdown-label" }, cap(genreName)));

    const list = el("div", { class: "genre-breakdown-list" });
    tracks.forEach((t) => {
      list.append(el("div", { class: "genre-breakdown-row" },
        el("span", { class: "genre-breakdown-rank" }, `#${t.rank}`),
        el("div", { class: "genre-breakdown-meta" },
          el("div", { class: "genre-breakdown-title", onClick: () => go(`#/tracks/${t.track_id}`), style: "cursor:pointer" }, t.title),
          el("div", { class: "genre-breakdown-artist" }, t.artist)),
        el("span", { class: "genre-breakdown-plays" }, fmtCount(t.plays))));
    });
    box.append(list);
    grid.append(box);
  });

  section.append(grid);
  return section;
}
