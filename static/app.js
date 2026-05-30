/* ia-wiki-lms — Student UI
 * Vanilla JS, zero build step. Richiede marked.js e d3.js caricati prima.
 */

(function () {
  "use strict";

  const COURSE_ID  = document.body.dataset.course  || "";
  const STUDENT_ID = document.body.dataset.student || "";
  const ROLE       = document.body.dataset.role    || "student";
  const IS_DEV     = document.body.dataset.dev === "true";

  const CAT_COLORS = {
    concepts:  "#4f6ef7",
    entities:  "#10b981",
    synthesis: "#f59e0b",
  };

  const state = {
    pages: [],
    filter: "",
    activePath: null,
    loading: false,
    view: "list",
    graphData: { nodes: [], edges: [] },
    bookmarkedPaths: new Set(),
    simulation: null,
  };

  async function api(method, path, body) {
    const opts = { method, headers: { "Content-Type": "application/json" } };
    if (body) opts.body = JSON.stringify(body);
    const r = await fetch(path, opts);
    if (!r.ok) throw new Error(`${method} ${path} → ${r.status}`);
    return r.json();
  }
  const get  = (path)       => api("GET",  path);
  const post = (path, body) => api("POST", path, body);

  function el(id) { return document.getElementById(id); }
  function esc(s) {
    return String(s).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;");
  }

  // ---------------------------------------------------------------------------
  // DOM skeleton
  // ---------------------------------------------------------------------------
  function buildSkeleton() {
    document.body.innerHTML = `
      <div id="header">
        <h1>ia-wiki-lms</h1>
        <span class="badge">${IS_DEV ? "dev" : "lti"}</span>
        <div class="spacer"></div>
        <span class="role-tag">${ROLE}</span>
      </div>
      <div id="app">
        <nav id="sidebar">
          <div id="sidebar-header"><span>Wiki</span></div>
          <div id="view-toggle">
            <button class="view-btn active" id="btn-list" onclick="switchView('list')">Lista</button>
            <button class="view-btn" id="btn-graph" onclick="switchView('graph')">Mappa</button>
          </div>
          <div style="padding:8px 10px;">
            <input id="sidebar-search" type="search" placeholder="Cerca pagina…">
          </div>
          <div id="pages-list"><div id="no-pages">Nessuna pagina ancora.</div></div>
        </nav>

        <section id="wiki-reader">
          <div id="reader-toolbar">
            <span class="page-name" id="reader-page-name">—</span>
          </div>
          <div id="reader-content" class="empty">
            Seleziona una pagina dalla sidebar o un nodo dalla mappa.
          </div>
          <div id="graph-pane">
            <svg id="graph-svg"></svg>
            <div id="graph-legend">
              <div class="legend-row"><span class="legend-dot" style="background:#4f6ef7"></span>Concetti</div>
              <div class="legend-row"><span class="legend-dot" style="background:#10b981"></span>Entità</div>
              <div class="legend-row"><span class="legend-dot" style="background:#f59e0b"></span>Sintesi</div>
            </div>
          </div>
        </section>

        <aside id="chat-panel">
          <div id="chat-header">Chat</div>
          <div id="chat-messages"></div>
          <div id="chat-footer">
            <textarea id="chat-input" placeholder="Fai una domanda sul corso…"></textarea>
            <button id="send-btn">Invia</button>
          </div>
        </aside>
      </div>
    `;

    el("sidebar-search").addEventListener("input", e => {
      state.filter = e.target.value.toLowerCase();
      renderSidebar();
    });
    el("send-btn").addEventListener("click", sendMessage);
    el("chat-input").addEventListener("keydown", e => {
      if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendMessage(); }
    });
  }

  // ---------------------------------------------------------------------------
  // View toggle
  // ---------------------------------------------------------------------------
  function switchView(view) {
    state.view = view;
    el("btn-list").classList.toggle("active", view === "list");
    el("btn-graph").classList.toggle("active", view === "graph");
    const reader = el("reader-content");
    const graphPane = el("graph-pane");
    if (view === "graph") {
      reader.style.display = "none";
      graphPane.classList.add("visible");
      renderGraph();
    } else {
      reader.style.display = "";
      graphPane.classList.remove("visible");
    }
  }

  // ---------------------------------------------------------------------------
  // Sidebar
  // ---------------------------------------------------------------------------
  const CATEGORIES = [
    { key: "concepts",  label: "Concetti" },
    { key: "entities",  label: "Entità" },
    { key: "synthesis", label: "Sintesi" },
  ];

  function renderSidebar() {
    const list = el("pages-list");
    const filtered = state.pages.filter(p =>
      !state.filter || p.title.toLowerCase().includes(state.filter)
    );
    if (!filtered.length) {
      list.innerHTML = '<div id="no-pages">Nessuna pagina trovata.</div>';
      return;
    }
    list.innerHTML = CATEGORIES.map(cat => {
      const items = filtered.filter(p => p.category === cat.key);
      if (!items.length) return "";
      return `
        <div class="category-group">
          <div class="category-label ${cat.key}">${cat.label}</div>
          ${items.map(p => pageItemHTML(p)).join("")}
        </div>`;
    }).join("");

    list.querySelectorAll(".page-item").forEach(node => {
      node.addEventListener("click", e => {
        if (e.target.classList.contains("bm-btn")) return;
        openPage(node.dataset.path);
      });
      const bm = node.querySelector(".bm-btn");
      if (bm) bm.addEventListener("click", () => toggleBookmark(node.dataset.path));
    });
  }

  function pageItemHTML(p) {
    const active = p.path === state.activePath ? " active" : "";
    const bmActive = p.bookmarked ? " active" : "";
    return `
      <div class="page-item${active}" data-path="${esc(p.path)}">
        <span class="page-title">${esc(p.title)}</span>
        ${ROLE === "student" ? `<button class="bm-btn${bmActive}" title="Preferito">★</button>` : ""}
      </div>`;
  }

  // ---------------------------------------------------------------------------
  // Wiki reader
  // ---------------------------------------------------------------------------
  async function openPage(path) {
    state.activePath = path;
    if (state.view === "graph") switchView("list");
    renderSidebar();

    el("reader-page-name").textContent = "Caricamento…";
    const content = el("reader-content");
    content.classList.remove("empty");
    content.innerHTML = '<div class="typing"><span></span><span></span><span></span></div>';

    try {
      const detail = await get(
        `/wiki/${COURSE_ID}/pages/${path}${STUDENT_ID ? "?student_id=" + STUDENT_ID : ""}`
      );
      el("reader-page-name").textContent = detail.title;
      content.innerHTML = marked.parse(detail.content);
      const found = state.pages.find(p => p.path === path);
      if (found) found.bookmarked = detail.bookmarked;
      renderSidebar();
    } catch (err) {
      content.innerHTML = `<p style="color:red">Errore: ${err.message}</p>`;
    }
  }

  // ---------------------------------------------------------------------------
  // Bookmarks
  // ---------------------------------------------------------------------------
  async function toggleBookmark(path) {
    if (ROLE !== "student" || !STUDENT_ID) return;
    try {
      const res = await post(`/rag/${COURSE_ID}/bookmark`, {
        student_id: STUDENT_ID,
        page_path: path,
      });
      const found = state.pages.find(p => p.path === path);
      if (found) found.bookmarked = res.action === "added";
      if (res.action === "added") state.bookmarkedPaths.add(path);
      else state.bookmarkedPaths.delete(path);
      renderSidebar();
      if (state.view === "graph") renderGraph();
    } catch (err) {
      console.error("Bookmark error:", err);
    }
  }

  // ---------------------------------------------------------------------------
  // D3 Graph
  // ---------------------------------------------------------------------------
  function renderGraph() {
    if (state.simulation) { state.simulation.stop(); state.simulation = null; }
    const { nodes, edges } = state.graphData;
    const svg = d3.select("#graph-svg");
    svg.selectAll("*").remove();

    const pane = el("graph-pane");
    const W = pane.clientWidth || 800;
    const H = pane.clientHeight || 600;

    const root = svg.append("g");
    const zoom = d3.zoom().scaleExtent([0.1, 4]).on("zoom", e => root.attr("transform", e.transform));
    svg.call(zoom);

    svg.append("defs").append("marker")
      .attr("id", "arrow").attr("viewBox", "0 -4 8 8")
      .attr("refX", 18).attr("refY", 0)
      .attr("markerWidth", 5).attr("markerHeight", 5).attr("orient", "auto")
      .append("path").attr("d", "M0,-4L8,0L0,4").attr("fill", "#c8d0dc");

    // Deep copy nodes/edges so D3 can mutate them freely
    const simNodes = nodes.map(n => ({ ...n }));
    const nodeById = new Map(simNodes.map(n => [n.id, n]));
    const simEdges = edges
      .filter(e => nodeById.has(e.source) && nodeById.has(e.target))
      .map(e => ({ ...e }));

    const linkSel = root.append("g").selectAll("line")
      .data(simEdges)
      .join("line")
      .attr("class", d => "g-link" + (d.type === "semantic" ? " semantic" : ""))
      .attr("stroke-width", d => Math.max(0.5, d.weight * 2))
      .attr("marker-end", "url(#arrow)");

    const deg = {};
    simNodes.forEach(n => { deg[n.id] = 0; });
    simEdges.forEach(e => {
      const s = typeof e.source === "object" ? e.source.id : e.source;
      const t = typeof e.target === "object" ? e.target.id : e.target;
      if (deg[s] !== undefined) deg[s]++;
      if (deg[t] !== undefined) deg[t]++;
    });

    const nodeSel = root.append("g").selectAll("g.g-node")
      .data(simNodes, d => d.id)
      .join("g")
      .attr("class", d => "g-node" + (state.bookmarkedPaths.has(d.id) ? " bookmarked" : ""))
      .call(d3.drag()
        .on("start", (ev, d) => { if (!ev.active) sim.alphaTarget(0.3).restart(); d.fx = d.x; d.fy = d.y; })
        .on("drag",  (ev, d) => { d.fx = ev.x; d.fy = ev.y; })
        .on("end",   (ev, d) => { if (!ev.active) sim.alphaTarget(0); d.fx = null; d.fy = null; }))
      .on("click", (ev, d) => { ev.stopPropagation(); openPage(d.id); });

    nodeSel.append("circle")
      .attr("r", d => 12 + (deg[d.id] || 0) * 2)
      .attr("fill", d => (CAT_COLORS[d.category] || "#888") + "28")
      .attr("stroke", d => CAT_COLORS[d.category] || "#888");

    nodeSel.append("circle")
      .attr("r", d => 6 + (deg[d.id] || 0) * 1.5)
      .attr("fill", d => CAT_COLORS[d.category] || "#888")
      .attr("stroke", "#fff").attr("stroke-width", 1.5);

    nodeSel.append("text")
      .attr("dy", "0.35em")
      .attr("x", d => 14 + (deg[d.id] || 0) * 1.5)
      .text(d => d.title);

    const sim = d3.forceSimulation(simNodes)
      .force("link", d3.forceLink(simEdges).id(d => d.id).distance(120).strength(0.4))
      .force("charge", d3.forceManyBody().strength(-400).distanceMax(500))
      .force("center", d3.forceCenter(W / 2, H / 2).strength(0.05))
      .force("collision", d3.forceCollide(d => 28 + (deg[d.id] || 0) * 2.5))
      .alphaDecay(0.025);

    state.simulation = sim;

    sim.on("tick", () => {
      linkSel
        .attr("x1", d => d.source.x).attr("y1", d => d.source.y)
        .attr("x2", d => d.target.x).attr("y2", d => d.target.y);
      nodeSel.attr("transform", d => `translate(${d.x || 0},${d.y || 0})`);
    });

    svg.on("click", () => nodeSel.classed("selected", false));
  }

  // ---------------------------------------------------------------------------
  // Chat
  // ---------------------------------------------------------------------------
  async function sendMessage() {
    const input = el("chat-input");
    const question = input.value.trim();
    if (!question || state.loading) return;

    input.value = "";
    state.loading = true;
    el("send-btn").disabled = true;

    appendMessage({ role: "user", text: question });
    const typingId = appendTyping();

    try {
      const res = await post(`/rag/${COURSE_ID}/query`, {
        student_id: STUDENT_ID,
        question,
        top_k: 5,
      });
      removeTyping(typingId);
      appendMessage({
        role: "assistant",
        text: res.answer,
        sources: res.sources || [],
        synthCreated: res.synthesis_created,
      });
      if (res.synthesis_created) await loadPages();
    } catch (err) {
      removeTyping(typingId);
      appendMessage({ role: "assistant", text: `⚠️ Errore: ${err.message}` });
    } finally {
      state.loading = false;
      el("send-btn").disabled = false;
      input.focus();
    }
  }

  function appendMessage(msg) {
    const msgs = el("chat-messages");
    const div = document.createElement("div");
    div.className = `msg ${msg.role}`;
    const bubble = document.createElement("div");
    bubble.className = "msg-bubble";
    bubble.innerHTML = typeof marked !== "undefined"
      ? marked.parse(msg.text)
      : esc(msg.text).replace(/\n/g, "<br>");
    div.appendChild(bubble);

    if (msg.sources && msg.sources.length) {
      const chips = document.createElement("div");
      chips.className = "msg-sources";
      msg.sources.forEach(s => {
        const chip = document.createElement("span");
        chip.className = "source-chip" + (s.bookmarked ? " bookmarked" : "");
        chip.textContent = s.title;
        chip.title = s.path;
        chip.addEventListener("click", () => openPage(s.path));
        chips.appendChild(chip);
      });
      div.appendChild(chips);
    }

    if (msg.synthCreated) {
      const note = document.createElement("div");
      note.className = "synthesis-note";
      note.textContent = "✦ Nuova pagina di sintesi aggiunta al wiki";
      div.appendChild(note);
    }

    msgs.appendChild(div);
    msgs.scrollTop = msgs.scrollHeight;
  }

  let _tc = 0;
  function appendTyping() {
    const id = "typing-" + (++_tc);
    const msgs = el("chat-messages");
    const div = document.createElement("div");
    div.id = id;
    div.className = "msg assistant";
    div.innerHTML = '<div class="msg-bubble"><div class="typing"><span></span><span></span><span></span></div></div>';
    msgs.appendChild(div);
    msgs.scrollTop = msgs.scrollHeight;
    return id;
  }

  function removeTyping(id) {
    const node = document.getElementById(id);
    if (node) node.remove();
  }

  // ---------------------------------------------------------------------------
  // Data loading
  // ---------------------------------------------------------------------------
  async function loadPages() {
    try {
      const qs = STUDENT_ID ? `?student_id=${STUDENT_ID}` : "";
      state.pages = await get(`/wiki/${COURSE_ID}/pages${qs}`);
      state.bookmarkedPaths = new Set(state.pages.filter(p => p.bookmarked).map(p => p.path));
      renderSidebar();
    } catch (err) {
      console.error("loadPages error:", err);
    }
  }

  async function loadGraph() {
    try {
      state.graphData = await get(`/wiki/${COURSE_ID}/graph`);
    } catch (err) {
      console.error("loadGraph error:", err);
    }
  }

  // Expose globally for onclick attributes
  window.switchView = switchView;

  // ---------------------------------------------------------------------------
  // Init
  // ---------------------------------------------------------------------------
  buildSkeleton();
  Promise.all([loadPages(), loadGraph()]);

})();
