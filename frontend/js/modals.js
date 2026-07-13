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

async function openArtistModal(artistId) {
  const data = await API.artist(artistId);
  if (!data) { toast("Could not load artist", "error"); return; }

  const allTracks = (data.albums || []).flatMap((al) =>
    (al.tracks || []).map((t) => ({ ...t, album: al.album_title }))
  );

  const BATCH = 5;
  let shown = 0;

  const trackList = el("div", { class: "modal__list", style: "max-height:300px" });
  const loadMoreBtn = el("button", {
    class: "btn btn--ghost btn--sm",
    style: "margin-top:10px;width:100%",
  }, "Load more");

  function renderTracks() {
    const next = allTracks.slice(shown, shown + BATCH);
    next.forEach((t) => {
      const countEl = el("span", { style: "float:right;color:var(--text-faint);font-family:var(--font-mono);font-size:.78rem" },
        fmtCount(t.play_count ?? 0));
      trackList.append(el("button", {
        onClick: () => {
          playTrack({ ...t, artist: data.name, artist_id: artistId }, countEl);
          m.close();
        },
      },
        el("span", {}, t.title),
        el("span", { style: "color:var(--text-faint);font-size:.8rem;margin-left:6px" },
          `· ${t.album || ""} · ${fmtDuration(t.duration_sec)}`),
        countEl));
    });
    shown += next.length;
    loadMoreBtn.style.display = shown >= allTracks.length ? "none" : "block";
  }

  renderTracks();
  loadMoreBtn.addEventListener("click", renderTracks);

  const { following: initFollowing } = await API.followStatus(artistId);
  const followBtn = el("button", {
    class: `btn btn--ghost btn--sm${initFollowing ? " btn--active" : ""}`,
  }, initFollowing ? "✓ Following" : "Follow");

  followBtn.addEventListener("click", async () => {
    followBtn.disabled = true;
    try {
      const { following } = followBtn.classList.contains("btn--active")
        ? await API.unfollowArtist(artistId)
        : await API.followArtist(artistId);
      followBtn.textContent = following ? "✓ Following" : "Follow";
      followBtn.classList.toggle("btn--active", following);
      toast(following ? `Following ${data.name}` : `Unfollowed ${data.name}`);
    } catch (e) { toast(e.message, "error"); }
    finally { followBtn.disabled = false; }
  });

  const box = el("div", { class: "modal", style: "width:min(500px,92vw)" },
    el("div", { style: "display:flex;align-items:center;gap:14px;margin-bottom:18px" },
      el("div", { class: "artist-card__avatar", style: "width:52px;height:52px;font-size:1.3rem;flex-shrink:0" },
        (data.name || "?")[0].toUpperCase()),
      el("div", {},
        el("h2", { style: "margin:0 0 4px" }, data.name),
        data.bio ? el("p", { style: "margin:0;color:var(--text-dim);font-size:.85rem" }, data.bio) : null)),
    el("p", { style: "font-family:var(--font-mono);font-size:.7rem;color:var(--lav);margin:0 0 10px;text-transform:uppercase;letter-spacing:.08em" },
      `${allTracks.length} track${allTracks.length !== 1 ? "s" : ""}`),
    trackList,
    allTracks.length > BATCH ? loadMoreBtn : null,
    el("div", { class: "modal__actions", style: "margin-top:16px" },
      followBtn,
      el("button", { class: "btn btn--ghost", onClick: () => m.close() }, "Close")));

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
