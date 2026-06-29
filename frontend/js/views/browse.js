/* ============================================================
   Resonate — Browse view: track list, search, track detail
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
      "Is the backend running? Check CONFIG.API_BASE in js/config.js."));
}

/* ---- Track row (reused by Browse / Playlist / Charts) ---- */
function trackRow(t, index, opts = {}) {
  const row = el("div", { class: "track-row", dataset: { trackId: t.track_id } },
    el("div", { class: "track-row__lead" },
      el("span", { class: "track-row__index" }, index),
      el("button", {
        class: "track-row__play", "aria-label": `Play ${t.title}`,
        onClick: (e) => { e.stopPropagation(); playTrack(t, null); },
      }, "▶")),
    el("div", { class: "track-row__main" },
      el("div", { class: "track-row__title", onClick: () => go(`#/tracks/${t.track_id}`) }, t.title),
      el("div", { class: "track-row__artist" }, t.artist + (t.album ? ` · ${t.album}` : ""))),
    t.genre ? el("span", { class: "track-row__genre" }, t.genre) : el("span"),
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
async function renderBrowse(_, append = false) {
  // Reset pagination when search/filter changes (not when appending)
  if (!append) {
    State.browseOffset = 0;
    State.browseTracks = [];
    State.browseHasMore = true;
  }

  const { tracks: newTracks } = await API.tracks({
    q: State.search,
    genre: State.genreFilter,
    limit: BROWSE_PAGE_SIZE,
    offset: State.browseOffset,
  });

  State.browseTracks = append ? [...State.browseTracks, ...newTracks] : newTracks;
  State.browseHasMore = newTracks.length === BROWSE_PAGE_SIZE;
  State.browseOffset += newTracks.length;

  const total = State.browseOffset;
  const head = el("div", { class: "page-head" },
    el("p", { class: "eyebrow" }, State.search ? `results for "${State.search}"` : "browse"),
    el("h1", {}, State.genreFilter ? cap(State.genreFilter) : "All tracks"),
    el("p", { id: "browse-count" }, `${total} track${total === 1 ? "" : "s"} loaded`));

  if (!State.browseTracks.length) {
    return el("div", {}, head, el("div", { class: "empty" },
      el("strong", {}, "No tracks match"), "Try a different search or genre."));
  }

  const list = el("div", { class: "tracklist" });
  State.browseTracks.forEach((t, i) => list.append(trackRow(t, i + 1)));

  // Load more button
  const loadMoreBtn = el("button", {
    class: "btn btn--ghost load-more-btn",
    style: State.browseHasMore ? "" : "display:none",
    onClick: async () => {
      loadMoreBtn.textContent = "Loading…";
      loadMoreBtn.disabled = true;
      const { tracks: more } = await API.tracks({
        q: State.search,
        genre: State.genreFilter,
        limit: BROWSE_PAGE_SIZE,
        offset: State.browseOffset,
      });
      State.browseTracks = [...State.browseTracks, ...more];
      State.browseHasMore = more.length === BROWSE_PAGE_SIZE;
      State.browseOffset += more.length;

      // Append new rows to existing list
      more.forEach((t, i) => list.append(trackRow(t, State.browseOffset - more.length + i + 1)));

      // Update count
      const countEl = document.getElementById("browse-count");
      if (countEl) countEl.textContent = `${State.browseOffset} tracks loaded`;

      if (!State.browseHasMore) {
        loadMoreBtn.style.display = "none";
      } else {
        loadMoreBtn.textContent = "Load more";
        loadMoreBtn.disabled = false;
      }
    },
  }, "Load more");

  return el("div", {}, head, list, el("div", { class: "load-more-wrap" }, loadMoreBtn));
}

/* ---- Track detail ---- */
async function renderTrackDetail(params) {
  const { track: t } = await API.track(params[0]);
  const countVal = el("span", { class: "fact__v", dataset: { count: "1" } }, fmtCount(t.user_plays ?? 0));

  // Follow button (only rendered when we have an artist_id)
  let followBtn = null;
  if (t.artist_id) {
    followBtn = el("button", { class: "btn btn--ghost" }, "Follow Artist");
    // Check current status then wire up toggle
    API.followStatus(t.artist_id).then(({ following }) => {
      followBtn.textContent = following ? "✓ Following" : "Follow Artist";
      followBtn.classList.toggle("btn--active", following);
    });
    followBtn.addEventListener("click", async () => {
      followBtn.disabled = true;
      try {
        const { following } = followBtn.classList.contains("btn--active")
          ? await API.unfollowArtist(t.artist_id)
          : await API.followArtist(t.artist_id);
        followBtn.textContent = following ? "✓ Following" : "Follow Artist";
        followBtn.classList.toggle("btn--active", following);
        toast(following ? `Following ${t.artist}` : `Unfollowed ${t.artist}`);
      } catch (e) {
        toast(e.message, "error");
      } finally {
        followBtn.disabled = false;
      }
    });
  }

  const detail = el("div", { class: "detail" },
    el("div", { class: "detail__cover" }, "♪"),
    el("div", {},
      el("p", { class: "eyebrow" }, t.genre || "track"),
      el("h1", { class: "detail__title" }, t.title),
      el("p", { class: "detail__sub" }, `${t.artist} · ${t.album}`),
      el("div", { class: "detail__facts" },
        fact("duration", fmtDuration(t.duration_sec)),
        el("div", { class: "fact" },
          el("span", { class: "fact__k" }, "your plays"), countVal),
        fact("global plays", fmtCount(t.play_count ?? 0)),
        fact("track_id", `#${t.track_id}`)),
      el("div", { class: "detail__actions" },
        el("button", { class: "btn btn--primary", onClick: () => playTrack(t, countVal) }, "▶  Play"),
        el("button", { class: "btn btn--ghost", onClick: () => openAddToPlaylist(t) }, "+  Add to playlist"),
        followBtn)));

  return el("div", {},
    el("button", { class: "btn btn--ghost btn--sm", style: "margin-bottom:20px", onClick: () => history.back() }, "← Back"),
    detail);
}

const fact = (k, v) => el("div", { class: "fact" }, el("span", { class: "fact__k" }, k), el("span", { class: "fact__v" }, v));
