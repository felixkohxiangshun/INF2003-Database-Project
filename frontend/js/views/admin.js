/* ============================================================
   Resonate — Admin view
   Full CRUD for Tracks, Artists, Albums, Genres.
   Also shows the audit log (populated by trg_audit_users).
   ============================================================ */

async function renderAdmin() {
  const wrap = el("div", {});

  wrap.append(
    el("div", { class: "page-head" },
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
      if (!panel.dataset.loaded || label === "Albums") {
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
    const genres = await API._req("GET", "/admin/genres").catch(() => []);
    panel.innerHTML = "";

    // ── Create form ──
    const titleWrap  = labelledInput("Title",        { type: "text",   placeholder: "Track title", required: "" });
    const durWrap    = labelledInput("Duration (s)", { type: "number", placeholder: "e.g. 214",    min: "1", required: "" });
    const albumWrap  = labelledInput("Album ID",     { type: "number", placeholder: "Album ID",    required: "" });
    const genreOpts  = [{ value: "", text: "— No genre —" }, ...genres.map(g => ({ value: g.genre_id, text: g.name }))];
    const genreWrap  = labelledSelect("Genre", genreOpts, "");
    const titleInput = titleWrap.querySelector("input");
    const durInput   = durWrap.querySelector("input");
    const albumInput = albumWrap.querySelector("input");
    const genreSelect= genreWrap.querySelector("select");

    const tbody = el("tbody", {});
    const countEl = el("p", { style: "font-size:.82rem;color:var(--text-faint);margin:0 0 8px" }, "");

    function addTrackRow(t, prepend = false) {
      const row = el("tr", {},
        el("td", {}, String(t.track_id)),
        el("td", { style: "color:var(--text)" }, t.track_title || t.title || ""),
        el("td", {}, t.artist_name || t.artist || "—"),
        el("td", {}, t.genre_name  || t.genre  || "—"),
        el("td", { style: "font-family:var(--font-mono);font-size:.8rem" }, fmtDuration(t.duration_sec)),
        el("td", {},
          el("button", { class: "btn btn--ghost btn--sm",  onClick: () => openEditTrack(t, genres, () => row.remove()) }, "Edit"),
          el("button", { class: "btn btn--danger btn--sm", onClick: async () => {
            if (!confirm(`Delete track #${t.track_id}? This cannot be undone.`)) return;
            try {
              await API._req("DELETE", `/admin/tracks/${t.track_id}`);
              toast("Track deleted");
              row.remove();
            } catch (err) { toast(err.message, "error"); }
          }}, "Delete")));
      if (prepend) tbody.prepend(row); else tbody.append(row);
    }

    const createForm = el("form", { class: "admin-form" },
      titleWrap, durWrap, albumWrap, genreWrap,
      el("button", { type: "submit", class: "btn btn--primary btn--sm", style: "align-self:flex-end" }, "+ Add track"));
    createForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      try {
        const track = await API._req("POST", "/admin/tracks", {
          title: titleInput.value.trim(),
          duration_sec: Number(durInput.value),
          album_id: Number(albumInput.value),
          genre_id: genreSelect.value ? Number(genreSelect.value) : null,
        });
        toast("Track created", "success");
        titleInput.value = "";
        durInput.value   = "";
        albumInput.value = "";
        genreSelect.value = "";
        addTrackRow(track, true);
      } catch (err) { toast(err.message, "error"); }
    });

    panel.append(el("div", { class: "admin-section" }, el("h3", {}, "Add Track"), createForm));

    // ── Search + table ──
    let searchTimer = null;
    const searchInput = el("input", {
      type: "text", placeholder: "Search tracks by title, artist or album…",
      class: "admin-search", style: "margin-bottom:12px",
    });

    async function fetchTracks(q) {
      tbody.innerHTML = "<tr><td colspan='6' style='color:var(--text-faint);font-size:.85rem'>Loading…</td></tr>";
      const url = q ? `/tracks?q=${encodeURIComponent(q)}&limit=50` : "/tracks?limit=50";
      const { tracks: list } = await API.tracks(q ? { q, limit: 50 } : { limit: 50 });
      tbody.innerHTML = "";
      list.forEach(t => addTrackRow(t));
      countEl.textContent = `Tracks${q ? ` matching "${q}"` : " (top 50 by plays)"}: ${list.length}`;
    }

    searchInput.addEventListener("input", () => {
      clearTimeout(searchTimer);
      searchTimer = setTimeout(() => fetchTracks(searchInput.value.trim()), 250);
    });

    const tableSection = el("div", { class: "admin-section" });
    tableSection.append(
      el("h3", {}, "Tracks"),
      searchInput,
      countEl,
      el("table", { class: "admin-table" },
        el("thead", {}, el("tr", {},
          el("th", {}, "ID"), el("th", {}, "Title"), el("th", {}, "Artist"),
          el("th", {}, "Genre"), el("th", {}, "Duration"), el("th", {}, "Actions"))),
        tbody));
    panel.append(tableSection);

    await fetchTracks("");

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

async function openEditTrack(track, genres, onSave) {
  const overlay = el("div", { class: "admin-modal-overlay" });
  const { fields, getValues } = buildTrackFormFields(genres, track);

  const form = el("form", { class: "admin-form" }, ...fields);
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    try {
      await API._req("PUT", `/admin/tracks/${track.track_id}`, getValues());
      toast("Track updated", "success");
      overlay.remove();
      if (onSave) onSave();
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

// ---------------------------------------------------------------------------
// Artists panel
// ---------------------------------------------------------------------------

async function loadArtists(panel) {
  adminLoading(panel);
  try {
    panel.innerHTML = "";

    const nameWrap = labelledInput("Name", { type: "text", placeholder: "Artist name", required: "" });
    const bioDiv   = el("div", { class: "field", style: "flex:2; min-width:220px" },
      el("span", { class: "field__label" }, "Bio"),
      el("textarea", { rows: "2", placeholder: "Optional bio…", style: "background:var(--ink);border:1px solid var(--line-2);border-radius:var(--r-sm);color:var(--text);font-family:inherit;font-size:.88rem;padding:9px 12px;resize:vertical;width:100%;outline:none" }));
    const nameInput = nameWrap.querySelector("input");
    const bioInput  = bioDiv.querySelector("textarea");

    const tbody = el("tbody", {});
    const tableSection = el("div", { class: "admin-section" });

    function addArtistRow(a, prepend = false) {
      const row = el("tr", {},
        el("td", {}, String(a.artist_id)),
        el("td", { style: "color:var(--text)" }, a.name),
        el("td", {},
          el("button", { class: "btn btn--danger btn--sm", onClick: async () => {
            if (!confirm(`Delete "${a.name}"? All their albums and tracks will also be deleted.`)) return;
            try {
              await API._req("DELETE", `/admin/artists/${a.artist_id}`);
              toast("Artist deleted");
              row.remove();
            } catch (err) { toast(err.message, "error"); }
          }}, "Delete")));
      if (prepend) tbody.prepend(row); else tbody.append(row);
    }

    const createForm = el("form", { class: "admin-form" },
      nameWrap, bioDiv,
      el("button", { type: "submit", class: "btn btn--primary btn--sm", style: "align-self:flex-end" }, "+ Add artist"));
    createForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      const name = nameInput.value.trim();
      if (!name) return;
      try {
        const artist = await API._req("POST", "/admin/artists", { name, bio: bioInput.value.trim() });
        toast("Artist created", "success");
        nameInput.value = "";
        bioInput.value  = "";
        addArtistRow(artist, true);
      } catch (err) { toast(err.message, "error"); }
    });

    panel.append(
      el("div", { class: "admin-section" }, el("h3", {}, "Add Artist"), createForm));

    // Search box for artist list
    let searchTimer = null;
    const searchInput = el("input", {
      type: "text", placeholder: "Search artists…",
      class: "admin-search", style: "margin-bottom:12px",
    });

    async function fetchArtists(q) {
      tbody.innerHTML = "<tr><td colspan='3' style='color:var(--text-faint);font-size:.85rem'>Loading…</td></tr>";
      const url = q ? `/artists?q=${encodeURIComponent(q)}&limit=50` : "/artists?limit=50";
      const results = await API._req("GET", url);
      const list = Array.isArray(results) ? results : (results.artists ?? []);
      tbody.innerHTML = "";
      list.forEach(a => addArtistRow(a));
      countEl.textContent = `Artists${q ? ` matching "${q}"` : " (top 50 by plays)"}: ${list.length}`;
    }

    searchInput.addEventListener("input", () => {
      clearTimeout(searchTimer);
      searchTimer = setTimeout(() => fetchArtists(searchInput.value.trim()), 250);
    });

    const countEl = el("p", { style: "font-size:.82rem;color:var(--text-faint);margin:0 0 8px" }, "");
    tableSection.append(
      el("h3", {}, "Artists"),
      searchInput,
      countEl,
      el("table", { class: "admin-table" },
        el("thead", {}, el("tr", {},
          el("th", {}, "ID"), el("th", {}, "Name"), el("th", {}, "Actions"))),
        tbody));
    panel.append(tableSection);

    await fetchArtists("");

  } catch (err) { adminError(panel, err.message); }
}

// ---------------------------------------------------------------------------
// Albums panel
// ---------------------------------------------------------------------------

async function loadAlbums(panel) {
  adminLoading(panel);
  try {
    panel.innerHTML = "";

    const titleWrap   = labelledInput("Title",        { type: "text", placeholder: "Album title", required: "" });
    const dateWrap    = labelledInput("Release Date", { type: "date" });
    const titleInput  = titleWrap.querySelector("input");
    const dateInput   = dateWrap.querySelector("input");

    // Artist search widget — queries server on each keystroke
    let selectedArtistId = null;
    let searchTimer = null;
    const artistWrap = el("div", { class: "field", style: "position:relative" });
    const artistLabel = el("label", { class: "field__label" }, "Artist");
    const artistSearch = el("input", {
      type: "text", placeholder: "Type to search artist…", autocomplete: "off",
      class: "admin-search",
    });
    const artistDropdown = el("ul", {
      style: "position:absolute;top:100%;left:0;right:0;z-index:50;background:var(--ink-2);border:1px solid var(--line);border-radius:var(--r);max-height:180px;overflow-y:auto;margin:2px 0 0;padding:0;list-style:none;display:none",
    });
    artistWrap.append(artistLabel, artistSearch, artistDropdown);

    async function fetchAndRenderDropdown(q) {
      artistDropdown.innerHTML = "";
      if (!q) { artistDropdown.style.display = "none"; return; }
      try {
        const results = await API._req("GET", `/artists?q=${encodeURIComponent(q)}&limit=30`);
        const matches = Array.isArray(results) ? results : (results.artists ?? []);
        if (!matches.length) { artistDropdown.style.display = "none"; return; }
        matches.forEach(a => {
          const item = el("li", {
            style: "padding:7px 12px;cursor:pointer;font-size:13px;color:var(--fg)",
          }, a.name);
          item.addEventListener("mousedown", (e) => {
            e.preventDefault();
            selectedArtistId = a.artist_id;
            artistSearch.value = a.name;
            artistDropdown.style.display = "none";
          });
          item.addEventListener("mouseenter", () => item.style.background = "var(--line)");
          item.addEventListener("mouseleave", () => item.style.background = "");
          artistDropdown.append(item);
        });
        artistDropdown.style.display = "block";
      } catch (_) { artistDropdown.style.display = "none"; }
    }

    artistSearch.addEventListener("input", () => {
      selectedArtistId = null;
      clearTimeout(searchTimer);
      searchTimer = setTimeout(() => fetchAndRenderDropdown(artistSearch.value.trim()), 200);
    });
    artistSearch.addEventListener("blur", () => setTimeout(() => { artistDropdown.style.display = "none"; }, 150));

    const createForm = el("form", { class: "admin-form" },
      artistWrap, titleWrap, dateWrap,
      el("button", { type: "submit", class: "btn btn--primary btn--sm", style: "align-self:flex-end" }, "+ Add album"));
    createForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      if (!selectedArtistId) { toast("Please select an artist from the list", "error"); return; }
      try {
        await API._req("POST", "/admin/albums", {
          artist_id: Number(selectedArtistId),
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

    // Albums lookup — search an artist to see their albums
    const albumResults = el("div", {});
    let lookupTimer = null;
    const lookupInput = el("input", {
      type: "text", placeholder: "Search artist to view their albums…",
      class: "admin-search", style: "margin-bottom:12px",
    });
    lookupInput.addEventListener("input", () => {
      clearTimeout(lookupTimer);
      const q = lookupInput.value.trim();
      if (!q) { albumResults.innerHTML = ""; return; }
      lookupTimer = setTimeout(async () => {
        albumResults.innerHTML = "<p style='color:var(--text-faint);font-size:.85rem'>Searching…</p>";
        try {
          const results = await API._req("GET", `/artists?q=${encodeURIComponent(q)}&limit=10`);
          const matches = Array.isArray(results) ? results : (results.artists ?? []);
          albumResults.innerHTML = "";
          for (const a of matches) {
            const data = await API.artist(a.artist_id);
            if (!data?.albums?.length) continue;
            const block = el("div", { class: "admin-artist-block" }, el("h4", {}, a.name));
            data.albums.forEach((al) => {
              block.append(el("div", { class: "admin-album-row" },
                el("span", {}, `${al.album_id} — ${al.album_title}`),
                el("button", { class: "btn btn--danger btn--sm", onClick: async () => {
                  if (!confirm(`Delete "${al.album_title}"? All its tracks will also be deleted.`)) return;
                  try {
                    await API._req("DELETE", `/admin/albums/${al.album_id}`);
                    toast("Album deleted");
                    lookupInput.dispatchEvent(new Event("input"));
                  } catch (err) { toast(err.message, "error"); }
                }}, "Delete")));
            });
            albumResults.append(block);
          }
          if (!albumResults.children.length) {
            albumResults.innerHTML = "<p style='color:var(--text-faint);font-size:.85rem'>No albums found for that artist.</p>";
          }
        } catch (_) { albumResults.innerHTML = ""; }
      }, 300);
    });

    panel.append(
      el("div", { class: "admin-section" },
        el("h3", {}, "Existing Albums"),
        lookupInput,
        albumResults));

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

    const list = el("ul", { class: "admin-genre-list" });
    const countEl = el("p", { style: "font-size:.82rem;color:var(--text-faint);margin:0 0 8px" }, `${genres.length} genres`);

    function addGenreRow(g, prepend = false) {
      const item = el("li", {},
        el("span", {}, String(g.genre_id)),
        g.name);
      if (prepend) list.prepend(item); else list.append(item);
    }
    genres.forEach(g => addGenreRow(g));

    const createForm = el("form", { class: "admin-form" },
      nameWrap,
      el("button", { type: "submit", class: "btn btn--primary btn--sm", style: "align-self:flex-end" }, "+ Add genre"));
    createForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      try {
        const genre = await API._req("POST", "/admin/genres", { name: nameInput.value.trim() });
        toast("Genre created", "success");
        nameInput.value = "";
        addGenreRow(genre, true);
        countEl.textContent = `${list.children.length} genres`;
      } catch (err) { toast(err.message, "error"); }
    });

    panel.append(el("div", { class: "admin-section" }, el("h3", {}, "Add Genre"), createForm));

    // Client-side search (113 genres — no need for server round-trip)
    let filterTimer = null;
    const searchInput = el("input", {
      type: "text", placeholder: "Filter genres…",
      class: "admin-search", style: "margin-bottom:12px",
    });
    searchInput.addEventListener("input", () => {
      clearTimeout(filterTimer);
      filterTimer = setTimeout(() => {
        const q = searchInput.value.trim().toLowerCase();
        let visible = 0;
        list.querySelectorAll("li").forEach(item => {
          const match = !q || item.textContent.toLowerCase().includes(q);
          item.style.display = match ? "" : "none";
          if (match) visible++;
        });
        countEl.textContent = q ? `${visible} of ${list.children.length} genres` : `${list.children.length} genres`;
      }, 150);
    });

    panel.append(
      el("div", { class: "admin-section" },
        el("h3", {}, "Genres"),
        searchInput,
        countEl,
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
      const isCreate = r.field_name === "created";
      const isDelete = r.field_name === "deleted";
      tbody.append(el("tr", {},
        el("td", {}, String(r.log_id)),
        el("td", {}, el("code", {}, r.table_name || "users")),
        el("td", {}, String(r.record_id)),
        el("td", { style: "color:var(--text-dim)" }, r.changed_by || "—"),
        el("td", {},
          el("span", {
            style: isCreate
              ? "color:var(--mint);font-family:var(--font-mono);font-size:.8rem"
              : isDelete
                ? "color:var(--coral);font-family:var(--font-mono);font-size:.8rem"
                : "font-family:var(--font-mono);font-size:.8rem",
          }, r.field_name)),
        el("td", { style: "color:var(--text-faint)" }, r.old_value || "—"),
        el("td", { style: "color:var(--text)" }, r.new_value || "—"),
        el("td", { style: "font-family:var(--font-mono);font-size:.78rem;color:var(--text-faint)" },
          r.changed_at ? r.changed_at.slice(0, 19).replace("T", " ") : "—")));
    });

    panel.append(
      el("div", { class: "admin-section" },
        el("h3", {}, `Audit Log (${rows.length})`),
        el("table", { class: "admin-table" },
          el("thead", {}, el("tr", {},
            el("th", {}, "Log"), el("th", {}, "Table"), el("th", {}, "Record"),
            el("th", {}, "Changed By"), el("th", {}, "Field"),
            el("th", {}, "Old"), el("th", {}, "New"), el("th", {}, "When"))),
          tbody)));

  } catch (err) { adminError(panel, err.message); }
}
