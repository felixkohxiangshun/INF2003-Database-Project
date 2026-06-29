/* ============================================================
   Resonate — Playlists view (list + detail)
   ============================================================ */

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
