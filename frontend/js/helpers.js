const State = {
  user: null,
  genres: [],
  search: "",
  genreFilter: "",
  nowPlaying: null,
  browseOffset: 0,
  browseTracks: [],
  browseHasMore: true,
};

const BROWSE_PAGE_SIZE = 20;

const $  = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];

// Builds DOM from a tag + props + children instead of innerHTML, so track titles etc. can't break out as HTML
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

const cap = (s) => (s || "").replace(/(^|[-\s])\w/g, (m) => m.toUpperCase());

function toast(message, kind = "") {
  const t = el("div", { class: `toast ${kind ? "toast--" + kind : ""}` }, message);
  $("#toast-stack").append(t);
  setTimeout(() => { t.style.opacity = "0"; setTimeout(() => t.remove(), 250); }, 2800);
}
