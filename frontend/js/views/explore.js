/* ============================================================
   Resonate — Explore view: Artist connection path finder
   Uses Neo4j shortestPath() to find how two artists are
   connected via SIMILAR_TO edges. Demonstrates a graph query
   with no practical SQL equivalent.
   ============================================================ */

async function renderExplore() {
  const head = el("div", { class: "page-head" },
    el("p", { class: "eyebrow" }, "graph traversal · neo4j shortestpath()"),
    el("h1", {}, "Artist Connections"),
    el("p", {}, "Discover how any two artists are linked through shared genre similarity."));

  // Load artist list from PostgreSQL for the dropdowns
  const { artists } = await API.artists();

  const fromSelect = el("select");
  const toSelect   = el("select");

  const placeholder = el("option", { value: "", disabled: "", selected: "" }, "Select an artist…");
  const placeholder2 = placeholder.cloneNode(true);
  fromSelect.append(placeholder);
  toSelect.append(placeholder2);

  artists.forEach((a) => {
    fromSelect.append(el("option", { value: a.artist_id }, a.name));
    toSelect.append(el("option",   { value: a.artist_id }, a.name));
  });

  const resultArea = el("div", {});

  const finder = el("div", { class: "explore-finder" },
    el("div", { class: "explore-finder__row" },
      el("div", { class: "field" },
        el("span", { class: "field__label" }, "From artist"),
        fromSelect),
      el("div", { class: "explore-finder__arrow" }, "→"),
      el("div", { class: "field" },
        el("span", { class: "field__label" }, "To artist"),
        toSelect)),
    el("button", {
      class: "btn btn--primary",
      onClick: async () => {
        const fromId = fromSelect.value;
        const toId   = toSelect.value;
        if (!fromId || !toId) { toast("Select both artists first", "err"); return; }
        if (fromId === toId)  { toast("Choose two different artists", "err"); return; }
        resultArea.innerHTML = "";
        resultArea.append(skeleton());
        try {
          const data = await API.artistPath(fromId, toId);
          resultArea.innerHTML = "";
          resultArea.append(renderPath(data));
        } catch (err) {
          resultArea.innerHTML = "";
          resultArea.append(errorState(err.message));
        }
      },
    }, "Find Connection"),
  );

  return el("div", {}, head, finder, resultArea);
}

function renderPath({ path, hops, message }) {
  if (!path) {
    return el("div", { class: "path-no-result" },
      el("strong", { style: "display:block;margin-bottom:6px;color:var(--text-dim)" },
        "No connection found"),
      message || "These artists share no genre links in the graph.");
  }

  const chain = el("div", { class: "path-chain" });
  path.forEach((node, i) => {
    const isFirst = i === 0;
    const isLast  = i === path.length - 1;
    const cls = "path-node" +
      (isFirst ? " path-node--start" : isLast ? " path-node--end" : "");
    chain.append(el("div", { class: cls }, node.name));
    if (i < path.length - 1) {
      chain.append(
        el("div", { class: "path-edge" },
          el("span", { class: "path-edge__line" }, "───"),
          el("span", {}, "SIMILAR_TO"))
      );
    }
  });

  return el("div", { class: "path-result" },
    el("p", { class: "path-result__hops" },
      `Connected in ${hops} hop${hops === 1 ? "" : "s"} via shared genre similarity`),
    chain);
}
