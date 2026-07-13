async function renderGraph() {
  const head = el("div", { class: "page-head" },
    el("p", { class: "eyebrow" }, "live neo4j subgraph · d3 force layout"),
    el("h1", {}, "My Listening Graph"),
    el("p", {}, "Your listening history visualised as a graph. Drag nodes, scroll to zoom."));

  const wrap = el("div", {});
  wrap.append(head);

  const nodeCard = el("div", { class: "graph-legend__card" },
    el("p", { class: "graph-legend__heading" }, "Nodes"),
    ...["User", "Track", "Artist"].map((label, i) => {
      const c = ["#FF6B4A", "#B79CFF", "#5BD6A8"][i];
      return el("div", { class: "graph-legend__item" },
        el("span", { class: "graph-legend__dot", style: `background:${c}` }),
        label);
    }));

  const edgeCard = el("div", { class: "graph-legend__card" },
    el("p", { class: "graph-legend__heading" }, "Edges"),
    ...["LISTENED_TO", "PERFORMED_BY", "SIMILAR_TO"].map((label, i) => {
      const c = ["#B79CFF", "#5BD6A8", "#FF6B4A"][i];
      const isDashed = label === "SIMILAR_TO";
      return el("div", { class: "graph-legend__item" },
        el("span", {
          class: `graph-legend__line${isDashed ? " graph-legend__line--dashed" : ""}`,
          style: isDashed ? `border-color:${c}` : `background:${c}`,
        }),
        label);
    }));

  const legend = el("div", { class: "graph-legend" }, nodeCard, edgeCard);

  const svgContainer = el("div", { class: "graph-container" });
  wrap.append(legend, svgContainer);

  if (!window.d3) {
    await new Promise((resolve, reject) => {
      const s = document.createElement("script");
      s.src = "https://cdnjs.cloudflare.com/ajax/libs/d3/7.8.5/d3.min.js";
      s.onload = resolve; s.onerror = reject;
      document.head.append(s);
    });
  }

  const { nodes, links, message } = await API.userGraph();

  if (!nodes.length) {
    svgContainer.append(el("div", { class: "empty" },
      el("strong", {}, "No graph data yet"),
      message || "Play some tracks to build your listening graph."));
    return wrap;
  }

  // container needs to be in the DOM before D3 can measure it, hence the timeout
  setTimeout(() => initD3Graph(svgContainer, nodes, links), 50);

  return wrap;
}

function initD3Graph(container, rawNodes, rawLinks) {
  const W = container.clientWidth || 800;
  const H = 500;

  const nodeColor = { User: "#FF6B4A", Track: "#B79CFF", Artist: "#5BD6A8" };
  const nodeRadius = { User: 18, Track: 9, Artist: 14 };
  const linkColor  = { LISTENED_TO: "#B79CFF", PERFORMED_BY: "#5BD6A8", SIMILAR_TO: "#FF6B4A" };
  const linkWidth  = { LISTENED_TO: 1.2, PERFORMED_BY: 1, SIMILAR_TO: 2 };

  // copy so D3's simulation can mutate x/y in place without touching the original API response
  const nodes = rawNodes.map(n => ({ ...n }));
  const links = rawLinks.map(l => ({ ...l }));

  const svg = d3.select(container).append("svg")
    .attr("width", "100%").attr("height", H)
    .style("display", "block");

  const defs = svg.append("defs");
  ["LISTENED_TO","PERFORMED_BY","SIMILAR_TO"].forEach(type => {
    defs.append("marker")
      .attr("id", `arrow-${type}`)
      .attr("viewBox", "0 -4 8 8")
      .attr("refX", 22).attr("refY", 0)
      .attr("markerWidth", 5).attr("markerHeight", 5)
      .attr("orient", "auto")
      .append("path").attr("d", "M0,-4L8,0L0,4")
      .attr("fill", linkColor[type]).attr("opacity", 0.7);
  });

  const g = svg.append("g");

  svg.call(d3.zoom().scaleExtent([0.3, 3])
    .on("zoom", e => g.attr("transform", e.transform)));

  const sim = d3.forceSimulation(nodes)
    .force("link", d3.forceLink(links).id(d => d.id)
      .distance(d => d.type === "SIMILAR_TO" ? 120 : d.type === "LISTENED_TO" ? 100 : 70)
      .strength(0.5))
    .force("charge", d3.forceManyBody().strength(-250))
    .force("center", d3.forceCenter(W / 2, H / 2))
    .force("collision", d3.forceCollide().radius(d => nodeRadius[d.type] + 18));

  const link = g.append("g").selectAll("line")
    .data(links).enter().append("line")
    .attr("stroke", d => linkColor[d.type] || "#666")
    .attr("stroke-width", d => linkWidth[d.type] || 1)
    .attr("stroke-opacity", 0.4)
    .attr("stroke-dasharray", d => d.type === "SIMILAR_TO" ? "5,3" : null)
    .attr("marker-end", d => `url(#arrow-${d.type})`);

  const node = g.append("g").selectAll("g")
    .data(nodes).enter().append("g")
    .attr("cursor", "grab")
    .call(d3.drag()
      .on("start", (e, d) => { if (!e.active) sim.alphaTarget(0.3).restart(); d.fx = d.x; d.fy = d.y; e.sourceEvent.target.style.cursor = "grabbing"; })
      .on("drag",  (e, d) => { d.fx = e.x; d.fy = e.y; })
      .on("end",   (e, d) => { if (!e.active) sim.alphaTarget(0); d.fx = null; d.fy = null; e.sourceEvent.target.style.cursor = "grab"; }));

  node.append("circle")
    .attr("r", d => nodeRadius[d.type])
    .attr("fill", d => nodeColor[d.type])
    .attr("fill-opacity", 0.85)
    .attr("stroke", d => nodeColor[d.type])
    .attr("stroke-width", 1.5)
    .attr("stroke-opacity", 0.4);

  const tooltip = d3.select(container).append("div").attr("class", "graph-tooltip");

  node
    .on("mouseover", (e, d) => {
      tooltip.style("display", "block")
        .html(`<div class="graph-tooltip__type">${d.type}</div>
               <div class="graph-tooltip__name">${d.label}</div>
               <div class="graph-tooltip__meta">${d.meta || ""}</div>`);
    })
    .on("mousemove", (e) => {
      const rect = container.getBoundingClientRect();
      tooltip.style("left", (e.clientX - rect.left + 12) + "px")
             .style("top",  (e.clientY - rect.top  - 10) + "px");
    })
    .on("mouseout", () => tooltip.style("display", "none"));

  node.append("text")
    .attr("text-anchor", "middle")
    .attr("dy", d => nodeRadius[d.type] + 11)
    .attr("font-size", d => d.type === "User" ? 11 : 9)
    .attr("font-weight", d => d.type === "User" ? 700 : 400)
    .attr("fill", d => nodeColor[d.type])
    .attr("fill-opacity", 0.9)
    .attr("pointer-events", "none")
    .text(d => d.label.length > 16 ? d.label.slice(0, 15) + "…" : d.label);

  sim.on("tick", () => {
    link
      .attr("x1", d => d.source.x).attr("y1", d => d.source.y)
      .attr("x2", d => d.target.x).attr("y2", d => d.target.y);
    node.attr("transform", d => `translate(${d.x},${d.y})`);
  });
}
