const routes = {
  browse:    renderBrowse,
  tracks:    renderTrackDetail,   // #/tracks/:id
  playlists: renderPlaylists,     // #/playlists  and  #/playlists/:id
  recommend: renderRecommend,
  stats:     renderStats,
  graph:     renderGraph,
  profile:   renderProfile,
  admin:     renderAdmin,
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

  $$(".nav__link").forEach((a) => a.classList.toggle("is-active", a.dataset.route === name));
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
