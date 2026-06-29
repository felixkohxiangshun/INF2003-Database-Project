/* ============================================================
   Resonate — Admin view
   Full CRUD for Tracks, Artists, Albums, Genres.
   Also shows the audit log (populated by trg_audit_users).
   ============================================================ */

async function renderAdmin() {
  const wrap = el("div", {});

  wrap.append(
    el("div", { class: "page-head" },
      el("p",  { class: "eyebrow" }, "database skills demo — full crud"),
      el("h1", {}, "Admin"),
      el("p",  {}, "Create, edit, and delete catalogue entries. Changes sync to Neo4j automatically.")));

  // Tab bar
  const tabs   = ["Tracks", "Artists", "Albums", "Genres", "Audit Log"];
  const tabBar = el("div", { class: "admin-tabs" });
  const panels = {};

  const loaders = {
    "Tracks":    (p) => loadTracks(p),
    "Artists":   (p) => loadArtists(p),
    "Albums":    (p) => loadAlbums(p),
    "Genres":    (p) => loadGenres(p),
    "Audit Log": (p) => loadAuditLog(p),
  };

  tabs.forEach((label, i) => {
    const panel = el("div", { class: "admin-panel", style: i === 0 ? "" : "display:none" });
    panels[label] = panel;

    const btn = el("button", { class: `admin-tab${i === 0 ? " is-active" : ""}` }, label);
    btn.addEventListener("click", () => {
      $$(".admin-tab").forEach(b   => b.classList.remove("is-active"));
      $$(".admin-panel").forEach(p => (p.style.display = "none"));
      btn.classList.add("is-active");
      panel.style.display = "";
      if (!panel.dataset.loaded) {
        loaders[label](panel);
        panel.dataset.loaded = "1";
      }
    });

    tabBar.append(btn);
    wrap.append(panel);
  });

  wrap.insertBefore(tabBar, panels["Tracks"]);
  loaders["Tracks"](panels["Tracks"]);
  panels["Tracks"].dataset.loaded = "1";

  return wrap;
}

// ---------------------------------------------------------------------------
// Shared helpers
// ---------------------------------------------------------------------------

function adminLoading(panel) {
  panel.innerHTML = "";
  panel.append(el("p", { class: "admin-loading" }, "Loading…"));
}

function adminError(panel, msg) {
  panel.innerHTML = "";
  panel.append(el("p", { class: "admin-error" }, msg));
}

function labelledInput(labelText, inputProps) {
  return el("div", { class: "field", style: "min-width:150px; flex:1" },
    el("span", { class: "field__label" }, labelText),
    el("input", inputProps));
}

function labelledSelect(labelText, options, currentVal) {
  const sel = el("select");
  options.forEach(({ value, text }) => {
    const opt = el("option", { value }, text);
    if (String(value) === String(currentVal)) opt.selected = true;
    sel.append(opt);
  });
  return el("div", { class: "field", style: "min-width:150px; flex:1" },
    el("span", { class: "field__label" }, labelText),
    sel);
}

// ---------------------------------------------------------------------------
// Tracks panel
// ---------------------------------------------------------------------------

async function loadTracks(panel) {
  adminLoading(panel);
  try {
    const [{ tracks }, genres] = await Promise.all([
      API.tracks({ limit: 100 }),
      API._req("GET", "/admin/genres").catch(() => []),
    ]);
    panel.innerHTML = "";

    // ── Create form ──
    const titleWrap  = labelledInput("Title",        { type: "text",   placeholder: "Track title",   required: "" });
    const durWrap    = labelledInput("Duration (s)", { type: "number", placeholder: "e.g. 214",      min: "1", required: "" });
    const albumWrap  = labelledInput("Album ID",     { type: "number", placeholder: "Album ID",      required: "" });
    const genreOpts  = [{ value: "", text: "— No genre —" }, ...genres.map(g => ({ value: g.genre_id, text: g.name }))];
    const genreWrap  = labelledSelect("Genre", genreOpts, "");
    const titleInput = titleWrap.querySelector("input");
    const durInput   = durWrap.querySelector("input");
    const albumInput = albumWrap.querySelector("input");
    const genreSelect= genreWrap.querySelector("select");

    const createForm = el("form", { class: "admin-form" },
      titleWrap, durWrap, albumWrap, genreWrap,
      el("button", { type: "submit", class: "btn btn--primary btn--sm", style: "align-self:flex-end" }, "+ Add track"));

    createForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      try {
        await API._req("POST", "/admin/tracks", {
          title: titleInput.value.trim(),
          duration_sec: Number(durInput.value),
          album_id: Number(albumInput.value),
          genre_id: genreSelect.value ? Number(genreSelect.value) : null,
        });
        toast("Track created", "success");
        panel.dataset.loaded = "";
        loadTracks(panel);
      } catch (err) { toast(err.message, "error"); }
    });

    panel.append(
      el("div", { class: "admin-section" },
        el("h3", {}, "Add Track"),
        createForm));

    // ── Table ──
    const tbody = el("tbody", {});
    tracks.forEach((t) => {
      tbody.append(el("tr", {},
        el("td", {}, String(t.track_id)),
        el("td", { style: "color:var(--text)" }, t.title),
        el("td", {}, t.artist),
        el("td", {}, t.genre || "—"),
        el("td", { style: "font-family:var(--font-mono);font-size:.8rem" }, fmtDuration(t.duration_sec)),
        el("td", {},
          el("button", { class: "btn btn--ghost btn--sm",   onClick: () => openEditTrack(t, genres, panel) }, "Edit"),
          el("button", { class: "btn btn--danger btn--sm",  onClick: () => deleteTrack(t.track_id, panel)  }, "Delete"))));
    });

    const table = el("table", { class: "admin-table" },
      el("thead", {}, el("tr", {},
        el("th", {}, "ID"), el("th", {}, "Title"), el("th", {}, "Artist"),
        el("th", {}, "Genre"), el("th", {}, "Duration"), el("th", {}, "Actions"))),
      tbody);

    panel.append(
      el("div", { class: "admin-section" },
        el("h3", {}, `Tracks (${tracks.length})`),
        table));

  } catch (err) { adminError(panel, err.message); }
}

function buildTrackFormFields(genres, defaults = {}) {
  const titleWrap   = labelledInput("Title",        { type: "text",   value: defaults.title || "", required: "" });
  const durWrap     = labelledInput("Duration (s)", { type: "number", value: defaults.duration_sec || "", min: "1", required: "" });
  const albumWrap   = labelledInput("Album ID",     { type: "number", value: defaults.album_id || "", required: "" });
  const genreOpts   = [{ value: "", text: "— No genre —" }, ...(genres || []).map(g => ({ value: g.genre_id, text: g.name }))];
  const genreWrap   = labelledSelect("Genre", genreOpts, defaults.genre_id ?? "");
  return {
    fields:      [titleWrap, durWrap, albumWrap, genreWrap],
    getValues:   () => ({
      title:        titleWrap.querySelector("input").value.trim(),
      duration_sec: Number(durWrap.querySelector("input").value),
      album_id:     Number(albumWrap.querySelector("input").value),
      genre_id:     genreWrap.querySelector("select").value ? Number(genreWrap.querySelector("select").value) : null,
    }),
  };
}

async function openEditTrack(track, genres, panel) {
  const overlay = el("div", { class: "admin-modal-overlay" });
  const { fields, getValues } = buildTrackFormFields(genres, track);

  const form = el("form", { class: "admin-form" }, ...fields);
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    try {
      await API._req("PUT", `/admin/tracks/${track.track_id}`, getValues());
      toast("Track updated", "success");
      overlay.remove();
      panel.dataset.loaded = "";
      loadTracks(panel);
    } catch (err) { toast(err.message, "error"); }
  });

  overlay.append(
    el("div", { class: "admin-modal" },
      el("h3", {}, `Edit Track #${track.track_id}`),
      form,
      el("div", { class: "admin-modal-actions" },
        el("button", { class: "btn btn--ghost btn--sm", onClick: () => overlay.remove() }, "Cancel"),
        el("button", { class: "btn btn--primary btn--sm", onClick: () => form.requestSubmit() }, "Save"))));
  document.body.append(overlay);
}

async function deleteTrack(track_id, panel) {
  if (!confirm(`Delete track #${track_id}? This cannot be undone.`)) return;
  try {
    await API._req("DELETE", `/admin/tracks/${track_id}`);
    toast("Track deleted");
    panel.dataset.loaded = "";
    loadTracks(panel);
  } catch (err) { toast(err.message, "error"); }
}

// ---------------------------------------------------------------------------
// Artists panel
// ---------------------------------------------------------------------------

async function loadArtists(panel) {
  adminLoading(panel);
  try {
    const { artists } = await API.artists();
    panel.innerHTML = "";

    const nameWrap = labelledInput("Name", { type: "text", placeholder: "Artist name", required: "" });
    const bioDiv   = el("div", { class: "field", style: "flex:2; min-width:220px" },
      el("span", { class: "field__label" }, "Bio"),
      el("textarea", { rows: "2", placeholder: "Optional bio…", style: "background:var(--ink);border:1px solid var(--line-2);border-radius:var(--r-sm);color:var(--text);font-family:inherit;font-size:.88rem;padding:9px 12px;resize:vertical;width:100%;outline:none" }));
    const nameInput = nameWrap.querySelector("input");
    const bioInput  = bioDiv.querySelector("textarea");

    const createForm = el("form", { class: "admin-form" },
      nameWrap, bioDiv,
      el("button", { type: "submit", class: "btn btn--primary btn--sm", style: "align-self:flex-end" }, "+ Add artist"));
    createForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      try {
        await API._req("POST", "/admin/artists", { name: nameInput.value.trim(), bio: bioInput.value.trim() });
        toast("Artist created", "success");
        panel.dataset.loaded = "";
        loadArtists(panel);
      } catch (err) { toast(err.message, "error"); }
    });

    panel.append(
      el("div", { class: "admin-section" }, el("h3", {}, "Add Artist"), createForm));

    const tbody = el("tbody", {});
    artists.forEach((a) => {
      tbody.append(el("tr", {},
        el("td", {}, String(a.artist_id)),
        el("td", { style: "color:var(--text)" }, a.name),
        el("td", {},
          el("button", { class: "btn btn--danger btn--sm", onClick: async () => {
            if (!confirm(`Delete "${a.name}"? All their albums and tracks will also be deleted.`)) return;
            try {
              await API._req("DELETE", `/admin/artists/${a.artist_id}`);
              toast("Artist deleted");
              panel.dataset.loaded = "";
              loadArtists(panel);
            } catch (err) { toast(err.message, "error"); }
          }}, "Delete"))));
    });

    panel.append(
      el("div", { class: "admin-section" },
        el("h3", {}, `Artists (${artists.length})`),
        el("table", { class: "admin-table" },
          el("thead", {}, el("tr", {},
            el("th", {}, "ID"), el("th", {}, "Name"), el("th", {}, "Actions"))),
          tbody)));

  } catch (err) { adminError(panel, err.message); }
}

// ---------------------------------------------------------------------------
// Albums panel
// ---------------------------------------------------------------------------

async function loadAlbums(panel) {
  adminLoading(panel);
  try {
    const { artists } = await API.artists();
    panel.innerHTML = "";

    const artistOpts  = [{ value: "", text: "— Select artist —" }, ...artists.map(a => ({ value: a.artist_id, text: a.name }))];
    const artistWrap  = labelledSelect("Artist", artistOpts, "");
    const titleWrap   = labelledInput("Title",        { type: "text", placeholder: "Album title", required: "" });
    const dateWrap    = labelledInput("Release Date", { type: "date" });
    const artistSelect = artistWrap.querySelector("select");
    const titleInput   = titleWrap.querySelector("input");
    const dateInput    = dateWrap.querySelector("input");

    const createForm = el("form", { class: "admin-form" },
      artistWrap, titleWrap, dateWrap,
      el("button", { type: "submit", class: "btn btn--primary btn--sm", style: "align-self:flex-end" }, "+ Add album"));
    createForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      try {
        await API._req("POST", "/admin/albums", {
          artist_id: Number(artistSelect.value),
          title: titleInput.value.trim(),
          release_date: dateInput.value || null,
        });
        toast("Album created", "success");
        panel.dataset.loaded = "";
        loadAlbums(panel);
      } catch (err) { toast(err.message, "error"); }
    });

    panel.append(
      el("div", { class: "admin-section" }, el("h3", {}, "Add Album"), createForm));

    // Albums grouped by artist
    const listSection = el("div", { class: "admin-section" }, el("h3", {}, "Existing Albums"));
    for (const a of artists.slice(0, 20)) {
      const data = await API.artist(a.artist_id);
      if (!data?.albums?.length) continue;

      const block = el("div", { class: "admin-artist-block" },
        el("h4", {}, a.name));
      data.albums.forEach((al) => {
        block.append(el("div", { class: "admin-album-row" },
          el("span", {}, `${al.album_id} — ${al.album_title}`),
          el("button", { class: "btn btn--danger btn--sm", onClick: async () => {
            if (!confirm(`Delete "${al.album_title}"? All its tracks will also be deleted.`)) return;
            try {
              await API._req("DELETE", `/admin/albums/${al.album_id}`);
              toast("Album deleted");
              panel.dataset.loaded = "";
              loadAlbums(panel);
            } catch (err) { toast(err.message, "error"); }
          }}, "Delete")));
      });
      listSection.append(block);
    }
    panel.append(listSection);

  } catch (err) { adminError(panel, err.message); }
}

// ---------------------------------------------------------------------------
// Genres panel
// ---------------------------------------------------------------------------

async function loadGenres(panel) {
  adminLoading(panel);
  try {
    const genres = await API._req("GET", "/admin/genres");
    panel.innerHTML = "";

    const nameWrap  = labelledInput("Name", { type: "text", placeholder: "e.g. jazz", required: "" });
    const nameInput = nameWrap.querySelector("input");

    const createForm = el("form", { class: "admin-form" },
      nameWrap,
      el("button", { type: "submit", class: "btn btn--primary btn--sm", style: "align-self:flex-end" }, "+ Add genre"));
    createForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      try {
        await API._req("POST", "/admin/genres", { name: nameInput.value.trim() });
        toast("Genre created", "success");
        nameInput.value = "";
        panel.dataset.loaded = "";
        loadGenres(panel);
      } catch (err) { toast(err.message, "error"); }
    });

    panel.append(
      el("div", { class: "admin-section" }, el("h3", {}, "Add Genre"), createForm));

    const list = el("ul", { class: "admin-genre-list" });
    genres.forEach((g) => list.append(
      el("li", {},
        el("span", {}, String(g.genre_id)),
        g.name)));

    panel.append(
      el("div", { class: "admin-section" },
        el("h3", {}, `Genres (${genres.length})`),
        list));

  } catch (err) { adminError(panel, err.message); }
}

// ---------------------------------------------------------------------------
// Audit log panel  (populated by trg_audit_users)
// ---------------------------------------------------------------------------

async function loadAuditLog(panel) {
  adminLoading(panel);
  try {
    const rows = await API._req("GET", "/admin/audit-log");
    panel.innerHTML = "";

    panel.append(
      el("div", { class: "admin-note" },
        "Every change to a user's email, username, or password is recorded here by ",
        el("code", {}, "trg_audit_users"),
        ". Update your profile to generate a new entry."));

    if (!rows.length) {
      panel.append(el("div", { class: "empty" },
        el("strong", {}, "No audit entries yet"),
        "Edit your profile to see the trigger fire."));
      return;
    }

    const tbody = el("tbody", {});
    rows.forEach((r) => {
      tbody.append(el("tr", {},
        el("td", {}, String(r.log_id)),
        el("td", {}, String(r.record_id)),
        el("td", { style: "color:var(--text)" }, r.changed_by || "—"),
        el("td", {}, el("code", {}, r.field_name)),
        el("td", {}, r.old_value || "—"),
        el("td", { style: "color:var(--text)" }, r.new_value || "—"),
        el("td", { style: "font-family:var(--font-mono);font-size:.78rem" },
          r.changed_at ? r.changed_at.slice(0, 19).replace("T", " ") : "—")));
    });

    panel.append(
      el("div", { class: "admin-section" },
        el("h3", {}, `Audit Log (${rows.length})`),
        el("table", { class: "admin-table" },
          el("thead", {}, el("tr", {},
            el("th", {}, "Log"), el("th", {}, "User"), el("th", {}, "Changed By"),
            el("th", {}, "Field"), el("th", {}, "Old"), el("th", {}, "New"),
            el("th", {}, "When"))),
          tbody)));

  } catch (err) { adminError(panel, err.message); }
}
