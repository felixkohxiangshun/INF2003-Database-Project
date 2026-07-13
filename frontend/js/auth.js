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
  $("#user-plan").textContent = "";
}

async function enter(user) {
  State.user = user;
  showApp();
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
        password: f.get("password"),
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

  try {
    const { user } = await API.me();
    if (user) return enter(user);
  } catch (_) {}
  showAuth();
}

document.addEventListener("DOMContentLoaded", boot);
