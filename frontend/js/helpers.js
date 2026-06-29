/* ============================================================
   Resonate — State, DOM helpers, formatters, utilities
   ============================================================ */

/* ---------- App state ---------- */
const State = {
  user: null,
  genres: [],
  search: "",
  genreFilter: "",
  nowPlaying: null,    // Track currently in the player
  browseOffset: 0,     // current pagination offset for Browse
  browseTracks: [],    // accumulated tracks across pages
  browseHasMore: true, // whether more tracks are available
};

const BROWSE_PAGE_SIZE = 20;

/* ---------- DOM selectors ---------- */
const $  = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];

/* ---------- Element builder ---------- */
// Build DOM safely from a tag + props + children (avoids innerHTML for data)
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

/* ---------- Formatters ---------- */
const fmtDuration = (sec) => {
  const m = Math.floor(sec / 60);
  const s = sec % 60;
  return `${m}:${String(s).padStart(2, "0")}`;
};
const fmtCount = (n) => n.toLocaleString("en-US");

// Capitalise first letter of each word (handles hyphenated genre names)
const cap = (s) => (s || "").replace(/(^|[-\s])\w/g, (m) => m.toUpperCase());

/* ---------- Toast notifications ---------- */
function toast(message, kind = "") {
  const t = el("div", { class: `toast ${kind ? "toast--" + kind : ""}` }, message);
  $("#toast-stack").append(t);
  setTimeout(() => { t.style.opacity = "0"; setTimeout(() => t.remove(), 250); }, 2800);
}
