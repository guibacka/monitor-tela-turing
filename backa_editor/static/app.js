// Editor visual de presets da tela Turing 3,5" (Backa)
// O servidor desenha a prévia com a mesma biblioteca de imagens da tela; aqui ficam a seleção, o arraste e as propriedades.
"use strict";

const TOKEN = document.body.dataset.token;
const $ = (id) => document.getElementById(id);

const S = {
  catalog: null,
  presets: [],
  active: "",
  name: "",
  layout: null,
  selected: null,
  boxes: {},
  history: [],
  future: [],
  dirty: false,
  zoom: 2,
};

// ---------------------------------------------------------------------------
// API
// ---------------------------------------------------------------------------
async function api(path, body) {
  const res = await fetch(path, {
    method: body ? "POST" : "GET",
    headers: { "X-Backa-Token": TOKEN, "Content-Type": "application/json" },
    body: body ? JSON.stringify(body) : undefined,
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.error || `Erro ${res.status}`);
  return data;
}

function toast(msg, kind = "") {
  const t = $("toast");
  t.textContent = msg;
  t.className = `toast ${kind}`;
  clearTimeout(toast._t);
  toast._t = setTimeout(() => t.classList.add("hidden"), kind === "error" ? 6000 : 3000);
}

// ---------------------------------------------------------------------------
// Utilidades
// ---------------------------------------------------------------------------
const clone = (o) => JSON.parse(JSON.stringify(o));
const hex = (c) => "#" + (c || [0, 0, 0]).slice(0, 3).map((v) => Number(v).toString(16).padStart(2, "0")).join("");
const rgb = (h) => [1, 3, 5].map((i) => parseInt(h.slice(i, i + 2), 16));
const byId = (id) => S.layout.items.find((i) => i.id === id);
const snap = (v) => ($("snapCheck").checked ? Math.round(v / 4) * 4 : Math.round(v));

function newId() {
  let n = S.layout.items.length + 1;
  while (byId(`i${n}`)) n++;
  return `i${n}`;
}

function widgetOf(item) {
  return item.kind === "data" ? item.widget : item.kind;
}

function itemLabel(item) {
  if (item.name) return item.name;
  if (item.kind === "data") {
    const src = S.catalog.sources[item.source];
    return `${src.group} · ${src.label} — ${S.catalog.widgets[item.widget]}`;
  }
  const base = S.catalog.static[item.kind];
  if (item.kind === "label") return `${base}: "${item.text}"`;
  if (item.kind === "symbol") return `${base}: ${item.icon || "?"}`;
  return base;
}

function itemColor(item) {
  return hex(item.color || item.fill || item.outline || [120, 120, 120]);
}

function used(source, widget) {
  return S.layout.items.some((i) => i.kind === "data" && i.source === source && i.widget === widget);
}

function setDirty(v) {
  S.dirty = v;
  const st = $("statusText");
  st.textContent = v ? "Alterações não salvas" : S.name === S.active ? "Salvo · é o preset da tela" : "Salvo";
  st.className = `status${v ? " dirty" : ""}`;
}

// ---------------------------------------------------------------------------
// Histórico (desfazer / refazer)
// ---------------------------------------------------------------------------
function snapshot() {
  S.history.push(JSON.stringify(S.layout));
  if (S.history.length > 200) S.history.shift();
  S.future = [];
}

function commit(mutate, { skipSnapshot = false } = {}) {
  if (!skipSnapshot) snapshot();
  mutate();
  setDirty(true);
  refresh();
}

function undo() {
  if (!S.history.length) return;
  S.future.push(JSON.stringify(S.layout));
  S.layout = JSON.parse(S.history.pop());
  if (S.selected && !byId(S.selected)) S.selected = null;
  setDirty(true);
  refresh();
}

function redo() {
  if (!S.future.length) return;
  S.history.push(JSON.stringify(S.layout));
  S.layout = JSON.parse(S.future.pop());
  setDirty(true);
  refresh();
}

// ---------------------------------------------------------------------------
// Prévia (desenhada pelo servidor)
// ---------------------------------------------------------------------------
let renderTimer = null;
let renderSeq = 0;

function scheduleRender(delay = 80) {
  clearTimeout(renderTimer);
  renderTimer = setTimeout(renderNow, delay);
}

async function renderNow() {
  const seq = ++renderSeq;
  try {
    const res = await api("/api/render", { layout: S.layout });
    if (seq !== renderSeq) return;
    $("stageImg").src = res.image;
    S.boxes = res.boxes;
    const p = $("problems");
    p.classList.toggle("hidden", !res.problems.length);
    p.innerHTML = res.problems.map((x) => `⚠ ${x}`).join("<br>");
    renderOverlay();
  } catch (e) {
    toast(`Não foi possível desenhar a prévia: ${e.message}`, "error");
  }
}

function refresh() {
  renderPalette();
  renderLayers();
  renderProps();
  renderOverlay();
  scheduleRender();
  $("btnUndo").disabled = !S.history.length;
  $("btnRedo").disabled = !S.future.length;
}

// ---------------------------------------------------------------------------
// Palco: caixas de seleção, arrastar e redimensionar
// ---------------------------------------------------------------------------
function setZoom(z) {
  S.zoom = z;
  const st = $("stage");
  st.style.width = `${S.layout.width * z}px`;
  st.style.height = `${S.layout.height * z}px`;
  renderOverlay();
}

// Ordem de clique igual à de desenho: dados sempre acima do fundo; dentro de cada grupo, quem vem depois fica por cima
function zOrder(item, idx) {
  return (item.kind === "data" ? 10000 : 0) + idx + 1;
}

// Itens que mudam de tamanho pela fonte (os cantos ajustam o tamanho do texto/ícone)
const SCALED = new Set(["text", "label", "weather", "icon", "symbol"]);

function renderOverlay() {
  const ov = $("overlay");
  ov.innerHTML = "";
  const z = S.zoom;
  S.layout.items.forEach((item, idx) => {
    const b = S.boxes[item.id];
    // A borda de status ocupa a tela toda: selecione pela lista de camadas
    if (!b || item.hidden || widgetOf(item) === "border") return;
    const el = document.createElement("div");
    el.className = `box${item.kind !== "data" ? " static" : ""}${item.id === S.selected ? " selected" : ""}`;
    el.style.left = `${b[0] * z}px`;
    el.style.top = `${b[1] * z}px`;
    el.style.width = `${Math.max(b[2], 2) * z}px`;
    el.style.height = `${Math.max(b[3], 2) * z}px`;
    el.style.zIndex = item.id === S.selected ? "99999" : String(zOrder(item, idx));
    el.title = `${itemLabel(item)}\n(Alt+clique: selecionar o item de baixo)`;
    el.dataset.id = item.id;
    el.addEventListener("mousedown", (ev) => {
      if (ev.altKey) return selectUnderneath(ev);
      startDrag(ev, item.id, null);
    });
    if (item.kind === "label") el.addEventListener("dblclick", () => focusProp("text"));
    if (item.id === S.selected && item.kind !== "line") {
      for (const h of ["nw", "ne", "sw", "se"]) {
        const hd = document.createElement("div");
        hd.className = `handle ${h}`;
        hd.addEventListener("mousedown", (ev) => startDrag(ev, item.id, h));
        el.appendChild(hd);
      }
    }
    ov.appendChild(el);
    // Linhas: uma alça em cada ponta
    if (item.id === S.selected && item.kind === "line") {
      for (const [key, px, py] of [["p1", item.x, item.y], ["p2", item.x2, item.y2]]) {
        const hd = document.createElement("div");
        hd.className = "handle";
        hd.style.cssText = `left:${px * z - 6}px;top:${py * z - 6}px;z-index:100000;cursor:crosshair`;
        hd.addEventListener("mousedown", (ev) => startDrag(ev, item.id, key));
        ov.appendChild(hd);
      }
    }
  });
  // Guias de alinhamento (só durante o arraste)
  if (drag && S.guides) {
    for (const [axis, v] of [["x", S.guides.x], ["y", S.guides.y]]) {
      if (v === null || v === undefined) continue;
      const g = document.createElement("div");
      g.className = `guide guide-${axis}`;
      g.style[axis === "x" ? "left" : "top"] = `${v * z}px`;
      ov.appendChild(g);
    }
  }
}

function alignSnap(box, excludeId) {
  // Procura bordas/centros de outros itens (e da tela) a até 4 px das bordas/centro do item arrastado
  const T = 4;
  const W = S.layout.width;
  const H = S.layout.height;
  const tx = [0, W / 2, W];
  const ty = [0, H / 2, H];
  for (const it of S.layout.items) {
    if (it.id === excludeId || it.hidden || widgetOf(it) === "border") continue;
    const b = S.boxes[it.id];
    if (!b) continue;
    tx.push(b[0], b[0] + b[2] / 2, b[0] + b[2]);
    ty.push(b[1], b[1] + b[3] / 2, b[1] + b[3]);
  }
  const best = (mine, targets) => {
    let r = { d: T + 1 };
    for (const m of mine) for (const t of targets) {
      const d = Math.abs(t - m);
      if (d < r.d) r = { d, shift: t - m, at: t };
    }
    return r.d <= T ? r : null;
  };
  const bx = best([box[0], box[0] + box[2] / 2, box[0] + box[2]], tx);
  const by = best([box[1], box[1] + box[3] / 2, box[1] + box[3]], ty);
  return { sx: bx ? bx.shift : null, gx: bx ? bx.at : null, sy: by ? by.shift : null, gy: by ? by.at : null };
}

function selectUnderneath(ev) {
  // Alt+clique: percorre os itens empilhados sob o cursor, de cima para baixo
  ev.preventDefault();
  ev.stopPropagation();
  const rect = $("overlay").getBoundingClientRect();
  const x = (ev.clientX - rect.left) / S.zoom;
  const y = (ev.clientY - rect.top) / S.zoom;
  const under = S.layout.items
    .map((item, idx) => ({ item, idx, b: S.boxes[item.id] }))
    .filter(({ item, b }) => b && !item.hidden && widgetOf(item) !== "border" && x >= b[0] && x <= b[0] + b[2] && y >= b[1] && y <= b[1] + b[3])
    .sort((a, b) => zOrder(b.item, b.idx) - zOrder(a.item, a.idx))
    .map(({ item }) => item.id);
  if (!under.length) return;
  const pos = under.indexOf(S.selected);
  select(under[(pos + 1) % under.length]);
}

function focusProp(key) {
  const inp = document.querySelector(`#props [data-key="${key}"]`);
  if (inp) { inp.focus(); inp.select && inp.select(); }
}

let drag = null;

function startDrag(ev, id, handle) {
  ev.preventDefault();
  ev.stopPropagation();
  if (S.selected !== id) {
    S.selected = id;
    renderLayers();
    renderProps();
    renderOverlay();
  }
  const item = byId(id);
  drag = { id, handle, sx: ev.clientX, sy: ev.clientY, orig: clone(item), box: clone(S.boxes[id] || [0, 0, 1, 1]),
           moved: false, before: JSON.stringify(S.layout) };
  window.addEventListener("mousemove", onDrag);
  window.addEventListener("mouseup", endDrag, { once: true });
}

function onDrag(ev) {
  if (!drag) return;
  const dx = (ev.clientX - drag.sx) / S.zoom;
  const dy = (ev.clientY - drag.sy) / S.zoom;
  if (!drag.moved && Math.abs(dx) < 1 && Math.abs(dy) < 1) return;
  drag.moved = true;
  const item = byId(drag.id);
  const o = drag.orig;
  const ob = drag.box;
  const kind = widgetOf(item);
  if (!drag.handle) {
    // Mover: primeiro tenta alinhar com outros itens (guias); sem alinhamento, usa a grade. Shift desliga as guias
    const a = ev.shiftKey ? { sx: null, sy: null } : alignSnap([ob[0] + dx, ob[1] + dy, ob[2], ob[3]], item.id);
    const mx = a.sx !== null ? Math.round(dx + a.sx) : snap(o.x + dx) - o.x;
    const my = a.sy !== null ? Math.round(dy + a.sy) : snap(o.y + dy) - o.y;
    S.guides = { x: a.gx ?? null, y: a.gy ?? null };
    item.x = o.x + mx;
    item.y = o.y + my;
    if (item.kind === "line") {
      item.x2 = o.x2 + mx;
      item.y2 = o.y2 + my;
    }
    S.boxes[item.id] = [ob[0] + mx, ob[1] + my, ob[2], ob[3]];
  } else if (drag.handle === "p1" || drag.handle === "p2") {
    // Ponta da linha
    if (drag.handle === "p1") { item.x = snap(o.x + dx); item.y = snap(o.y + dy); }
    else { item.x2 = snap(o.x2 + dx); item.y2 = snap(o.y2 + dy); }
  } else if (SCALED.has(kind)) {
    // Textos e ícones: os cantos mudam o tamanho (fonte/ícone), mantendo o ponto de ancoragem
    const grow = drag.handle.includes("s") ? dy : -dy;
    const ratio = Math.max(0.2, (ob[3] + grow) / Math.max(ob[3], 1));
    if (kind === "icon") item.size = Math.max(8, Math.round((o.size || 22) * ratio));
    else if (kind === "symbol") item.size = Math.max(8, Math.round((o.size || 32) * ratio));
    else item.size = Math.max(6, Math.round((o.size || 14) * ratio));
    if (kind === "weather") item.icon_size = Math.max(8, Math.round((o.icon_size || 22) * ratio));
    S.boxes[item.id] = [ob[0], ob[1], ob[2] * ratio, ob[3] * ratio];
  } else {
    // Caixas (painel, imagem, barra, gráfico, medidor)
    let { x, y, w, h } = o;
    if (drag.handle.includes("e")) w = snap(o.w + dx);
    if (drag.handle.includes("s")) h = snap(o.h + dy);
    if (drag.handle.includes("w")) { x = snap(o.x + dx); w = o.w + (o.x - x); }
    if (drag.handle.includes("n")) { y = snap(o.y + dy); h = o.h + (o.y - y); }
    w = Math.max(w, 2);
    h = Math.max(h, 2);
    if (item.widget === "radial") w = h = Math.max(w, h);
    Object.assign(item, { x, y, w, h });
    S.boxes[item.id] = [x, y, w, h];
  }
  renderOverlay();
  scheduleRender(60);
}

function endDrag() {
  window.removeEventListener("mousemove", onDrag);
  S.guides = null;
  if (drag && drag.moved) {
    S.history.push(drag.before);
    S.future = [];
    setDirty(true);
    refresh();
  }
  drag = null;
}

// ---------------------------------------------------------------------------
// Paleta: adicionar itens
// ---------------------------------------------------------------------------
const STATIC_DEFAULTS = {
  panel: { x: 40, y: 40, w: 160, h: 100, radius: 10, fill: [17, 20, 27], outline: [80, 86, 100], outline_width: 1 },
  label: { x: 40, y: 40, text: "Texto", font: "roboto/Roboto-Bold.ttf", size: 14, color: [240, 240, 245], anchor: "la" },
  image: { x: 40, y: 40, w: 80, h: 80, src: "" },
  symbol: { x: 40, y: 40, size: 32, icon: "cpu", style: "outline", color: [240, 240, 245] },
  line: { x: 40, y: 60, x2: 200, y2: 60, color: [80, 86, 100], width: 1 },
};

function dataDefaults(source, widget) {
  const src = S.catalog.sources[source];
  const base = { kind: "data", source, widget, x: 40, y: 40 };
  const mono = "roboto-mono/RobotoMono-Bold.ttf";
  switch (widget) {
    case "text":
      Object.assign(base, { font: mono, size: 16, color: [240, 240, 245], anchor: "lt" });
      if (src.format) base.format = src.format;
      if (src.temp_levels) Object.assign(base, { temp_levels: clone(src.temp_levels), color: [90, 220, 120] });
      if (!src.custom && !src.format && source !== "UPTIME") base.show_unit = true;
      break;
    case "bar": Object.assign(base, { w: 160, h: 8, color: [90, 160, 255], track: [34, 38, 48] }); break;
    case "line_graph": Object.assign(base, { w: 160, h: 30, color: [90, 160, 255], line_width: 1 }); break;
    case "radial": Object.assign(base, { w: 80, h: 80, thickness: 10, color: [90, 160, 255], show_text: true, size: 16, text_color: [240, 240, 245], angle_start: 135, angle_end: 45 }); break;
    case "weather": Object.assign(base, { x: 172, y: 8, icon_size: 22, font: mono, size: 12, color: [220, 220, 228] }); break;
    case "icon": Object.assign(base, { x: 364, y: 8, size: 22 }); break;
    case "border": Object.assign(base, { x: 0, y: 0, thickness: 4 }); break;
  }
  return base;
}

function addItem(item) {
  commit(() => {
    item.id = newId();
    S.layout.items.push(item);
    S.selected = item.id;
  });
  if (item.kind === "image") pickImage((src) => updateSelected({ src }));
}

function renderPalette() {
  const pal = $("palette");
  pal.innerHTML = "";
  const stat = document.createElement("div");
  stat.className = "pal-group";
  stat.innerHTML = "<h3>Estáticos (fundo)</h3>";
  const sb = document.createElement("div");
  sb.className = "pal-btns";
  for (const [kind, label] of Object.entries(S.catalog.static)) {
    const b = document.createElement("button");
    b.textContent = `+ ${label}`;
    b.onclick = kind === "symbol"
      ? () => pickSymbol((icon, style) => addItem({ kind, ...clone(STATIC_DEFAULTS[kind]), icon, style }))
      : () => addItem({ kind, ...clone(STATIC_DEFAULTS[kind]) });
    sb.appendChild(b);
  }
  stat.appendChild(sb);
  pal.appendChild(stat);

  const groups = {};
  for (const [key, src] of Object.entries(S.catalog.sources)) (groups[src.group] ||= []).push([key, src]);
  for (const [group, list] of Object.entries(groups)) {
    const g = document.createElement("div");
    g.className = "pal-group";
    g.innerHTML = `<h3>${group}</h3>`;
    for (const [key, src] of list) {
      const row = document.createElement("div");
      row.className = "pal-item";
      row.innerHTML = `<div class="src">${src.label}</div>`;
      const btns = document.createElement("div");
      btns.className = "pal-btns";
      for (const w of src.widgets) {
        const b = document.createElement("button");
        b.textContent = `+ ${S.catalog.widgets[w]}`;
        b.disabled = used(key, w);
        b.title = b.disabled ? "Já está na tela (cada dado só pode aparecer uma vez por tipo)" : "";
        b.onclick = () => addItem(dataDefaults(key, w));
        btns.appendChild(b);
      }
      row.appendChild(btns);
      g.appendChild(row);
    }
    pal.appendChild(g);
  }
}

// ---------------------------------------------------------------------------
// Camadas
// ---------------------------------------------------------------------------
function renderLayers() {
  // Dois grupos: dados (sempre desenhados por cima) e itens de fundo (estáticos)
  const box = $("layers");
  box.innerHTML = "";
  const items = S.layout.items;
  for (const [isData, title] of [[true, "Dados — sempre por cima"], [false, "Fundo — itens estáticos"]]) {
    box.insertAdjacentHTML("beforeend", `<div class="muted small" style="margin:8px 0 4px">${title}</div>`);
    for (let idx = items.length - 1; idx >= 0; idx--) {
      if ((items[idx].kind === "data") === isData) box.appendChild(layerRow(items[idx], idx));
    }
  }
}

function layerRow(item, idx) {
  {
    const row = document.createElement("div");
    row.className = `layer${item.id === S.selected ? " selected" : ""}${item.hidden ? " hidden-item" : ""}`;
    row.innerHTML = `<span class="dot" style="background:${itemColor(item)}"></span><span class="name">${escapeHtml(itemLabel(item))}</span>`;
    row.onclick = () => select(item.id);
    const mk = (txt, title, fn, cls = "") => {
      const b = document.createElement("button");
      b.textContent = txt;
      b.title = title;
      b.className = cls;
      b.onclick = (e) => { e.stopPropagation(); fn(); };
      row.appendChild(b);
    };
    mk(item.hidden ? "◌" : "●", item.hidden ? "Mostrar" : "Ocultar", () => commit(() => (item.hidden = !item.hidden)));
    mk("▲", "Trazer para frente", () => moveLayer(idx, +1));
    mk("▼", "Enviar para trás", () => moveLayer(idx, -1));
    mk("✕", "Remover", () => removeItem(item.id), "danger");
    return row;
  }
}

function moveLayer(idx, dir) {
  // Troca com o vizinho do mesmo grupo (dados com dados, fundo com fundo)
  const it = S.layout.items;
  const isData = it[idx].kind === "data";
  let j = idx + dir;
  while (j >= 0 && j < it.length && (it[j].kind === "data") !== isData) j += dir;
  if (j < 0 || j >= it.length) return;
  commit(() => {
    [it[idx], it[j]] = [it[j], it[idx]];
  });
}

function removeItem(id) {
  commit(() => {
    S.layout.items = S.layout.items.filter((i) => i.id !== id);
    if (S.selected === id) S.selected = null;
  });
}

function select(id) {
  S.selected = id;
  renderLayers();
  renderProps();
  renderOverlay();
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
}

// ---------------------------------------------------------------------------
// Propriedades
// ---------------------------------------------------------------------------
const ANCHORS_TEXT = [["lt", "Esquerda"], ["mt", "Centro"], ["rt", "Direita"]];
const ANCHORS_LABEL = [["la", "Esquerda"], ["ma", "Centro"], ["ra", "Direita"]];

function fieldsFor(item) {
  const F = [];
  const pos = [{ key: "x", label: "X", type: "int" }, { key: "y", label: "Y", type: "int" }];
  const size = [{ key: "w", label: "Largura", type: "int" }, { key: "h", label: "Altura", type: "int" }];
  const font = [{ key: "font", label: "Fonte", type: "font" }, { key: "size", label: "Tamanho", type: "int" }];
  switch (widgetOf(item)) {
    case "panel":
      F.push(...pos, ...size, { key: "radius", label: "Cantos", type: "int" }, { key: "fill", label: "Preenchimento", type: "color?" },
        { key: "outline", label: "Contorno", type: "color?" }, { key: "outline_width", label: "Esp. contorno", type: "int" });
      break;
    case "label":
      F.push({ key: "text", label: "Texto", type: "text" }, ...pos, ...font, { key: "color", label: "Cor", type: "color" },
        { key: "anchor", label: "Alinhamento", type: "select", options: ANCHORS_LABEL });
      break;
    case "image":
      F.push({ key: "src", label: "Imagem", type: "image" }, ...pos, ...size);
      break;
    case "symbol":
      F.push({ key: "icon", label: "Ícone", type: "symbol" }, ...pos, { key: "size", label: "Tamanho", type: "int", placeholder: "32" },
        { key: "color", label: "Cor", type: "color" },
        { key: "style", label: "Estilo", type: "select", options: [["outline", "Contorno"], ["filled", "Preenchido"]] });
      break;
    case "line":
      F.push({ key: "x", label: "X inicial", type: "int" }, { key: "y", label: "Y inicial", type: "int" },
        { key: "x2", label: "X final", type: "int" }, { key: "y2", label: "Y final", type: "int" },
        { key: "color", label: "Cor", type: "color" }, { key: "width", label: "Espessura", type: "int" });
      break;
    case "text": {
      const src = S.catalog.sources[item.source];
      F.push(...pos, ...font);
      if (!src.temp_levels) F.push({ key: "color", label: "Cor", type: "color" });
      F.push({ key: "anchor", label: "Alinhamento", type: "select", options: ANCHORS_TEXT });
      if ("show_unit" in item) F.push({ key: "show_unit", label: "Mostrar unidade", type: "bool" });
      if (src.format) F.push({ key: "format", label: "Formato", type: "text", help: "Ex.: dd/MM/yyyy, EEE, HH:mm:ss" });
      if (src.temp_levels) F.push({ key: "temp_levels", label: "Níveis de cor", type: "levels" });
      if (!src.custom || src.fast_refresh) F.push({ key: "interval", label: "Atualizar a cada (s)", type: "int", placeholder: String(src.fast_refresh || src.interval || 2) });
      break;
    }
    case "bar":
      F.push(...pos, ...size, { key: "color", label: "Cor", type: "color" }, { key: "track", label: "Trilho", type: "color?" }, maxField(item));
      break;
    case "line_graph":
      F.push(...pos, ...size, { key: "color", label: "Cor", type: "color" }, { key: "line_width", label: "Espessura", type: "int" }, maxField(item));
      break;
    case "radial":
      F.push(...pos, { key: "w", label: "Tamanho", type: "int" }, { key: "thickness", label: "Espessura", type: "int" },
        { key: "color", label: "Cor", type: "color" }, { key: "angle_start", label: "Ângulo inicial", type: "int" },
        { key: "angle_end", label: "Ângulo final", type: "int" }, { key: "show_text", label: "Mostrar valor", type: "bool" },
        { key: "size", label: "Tamanho do texto", type: "int" }, { key: "text_color", label: "Cor do texto", type: "color" }, maxField(item));
      break;
    case "weather":
      F.push(...pos, { key: "icon_size", label: "Tamanho do ícone", type: "int", placeholder: "22" }, ...font,
        { key: "color", label: "Cor", type: "color" });
      break;
    case "icon":
      F.push(...pos, { key: "size", label: "Tamanho", type: "int", placeholder: "22" });
      break;
    case "border":
      F.push({ key: "thickness", label: "Espessura", type: "int", placeholder: "4" }, { key: "colors", label: "Cores", type: "colors3" });
      break;
  }
  F.push({ key: "name", label: "Nome na lista", type: "text", placeholder: itemLabel({ ...item, name: "" }) });
  return F;
}

function maxField(item) {
  // Valor que corresponde à barra/gráfico "cheio" (ex.: 150 W para a potência da CPU)
  const src = S.catalog.sources[item.source] || {};
  return { key: "max", label: "Valor máximo", type: "int", placeholder: String(src.max || 100) };
}

function updateSelected(patch) {
  const item = byId(S.selected);
  if (!item) return;
  commit(() => {
    Object.assign(item, patch);
    if (item.widget === "radial" && "w" in patch) item.h = item.w;
  });
}

function renderProps() {
  const box = $("props");
  box.innerHTML = "";
  const item = S.selected && byId(S.selected);
  if (!item) {
    $("propsTitle").textContent = "Fundo e preset";
    renderBackgroundProps(box);
    return;
  }
  $("propsTitle").textContent = item.kind === "data" ? "Propriedades do dado" : "Propriedades do item";
  const tag = document.createElement("div");
  tag.innerHTML = `<span class="tag">${escapeHtml(itemLabel({ ...item, name: "" }))}</span>`;
  box.appendChild(tag);
  for (const f of fieldsFor(item)) box.appendChild(makeField(f, item));
  const actions = document.createElement("div");
  actions.className = "field";
  actions.innerHTML = "<label></label>";
  const row = document.createElement("div");
  row.className = "row";
  if (item.kind !== "data") {
    const dup = document.createElement("button");
    dup.textContent = "Duplicar";
    dup.onclick = duplicateSelected;
    row.appendChild(dup);
  }
  const del = document.createElement("button");
  del.textContent = "Remover";
  del.className = "danger";
  del.onclick = () => removeItem(item.id);
  row.appendChild(del);
  actions.appendChild(row);
  box.appendChild(actions);
}

function makeField(f, item) {
  const wrap = document.createElement("div");
  wrap.className = "field";
  wrap.innerHTML = `<label>${f.label}</label>`;
  const row = document.createElement("div");
  row.className = "row";
  const val = item[f.key];
  const set = (v) => updateSelected({ [f.key]: v });

  if (f.type === "int" || f.type === "text") {
    // Atualiza a prévia enquanto digita; o "desfazer" registra a edição inteira de uma vez
    const inp = document.createElement("input");
    inp.type = f.type === "int" ? "number" : "text";
    inp.value = val ?? "";
    inp.dataset.key = f.key;
    if (f.placeholder) inp.placeholder = f.placeholder;
    if (f.help) inp.title = f.help;
    const parse = () => {
      if (f.type === "int") return inp.value === "" ? undefined : parseInt(inp.value, 10);
      return inp.value === "" && f.key === "name" ? undefined : inp.value;
    };
    inp.onfocus = () => (inp._before = JSON.stringify(S.layout));
    inp.oninput = () => {
      const v = parse();
      if (f.type === "int" && Number.isNaN(v)) return;
      item[f.key] = v;
      if (item.widget === "radial" && f.key === "w") item.h = v;
      setDirty(true);
      scheduleRender(120);
    };
    inp.onchange = () => {
      if (inp._before && inp._before !== JSON.stringify(S.layout)) {
        S.history.push(inp._before);
        S.future = [];
      }
      inp._before = JSON.stringify(S.layout);
      renderPalette();
      renderLayers();
      renderOverlay();
      $("btnUndo").disabled = !S.history.length;
    };
    row.appendChild(inp);
  } else if (f.type === "color" || f.type === "color?") {
    const inp = document.createElement("input");
    inp.type = "color";
    inp.value = hex(val || [128, 128, 128]);
    inp.disabled = f.type === "color?" && !val;
    inp.onchange = () => set(rgb(inp.value));
    row.appendChild(inp);
    if (f.type === "color?") {
      const lbl = document.createElement("label");
      lbl.className = "check";
      lbl.innerHTML = `<input type="checkbox" ${val ? "checked" : ""}> usar`;
      lbl.querySelector("input").onchange = (e) => set(e.target.checked ? rgb(inp.value) : null);
      row.appendChild(lbl);
    }
  } else if (f.type === "bool") {
    const inp = document.createElement("input");
    inp.type = "checkbox";
    inp.checked = val !== false;
    inp.onchange = () => set(inp.checked);
    row.appendChild(inp);
  } else if (f.type === "select" || f.type === "font") {
    const sel = document.createElement("select");
    const opts = f.type === "font" ? S.catalog.fonts.map((x) => [x, x]) : f.options;
    for (const [v, l] of opts) sel.add(new Option(l, v, false, v === val));
    sel.onchange = () => set(sel.value);
    row.appendChild(sel);
  } else if (f.type === "image") {
    const b = document.createElement("button");
    b.textContent = val ? "Trocar imagem…" : "Escolher imagem…";
    b.onclick = () => pickImage((src) => set(src));
    row.appendChild(b);
    if (val) row.insertAdjacentHTML("beforeend", `<span class="muted small">${escapeHtml(val)}</span>`);
  } else if (f.type === "symbol") {
    row.insertAdjacentHTML("beforeend", symbolGlyph(val, item.style, "glyph big"));
    const b = document.createElement("button");
    b.textContent = "Trocar ícone…";
    b.onclick = () => pickSymbol((icon, style) => updateSelected({ icon, style }), item.style);
    row.appendChild(b);
    row.insertAdjacentHTML("beforeend", `<span class="muted small">${escapeHtml(val || "")}</span>`);
    if (item.style === "filled" && S.icons && !(S.icons.icons[val] || [])[1])
      row.insertAdjacentHTML("beforeend", `<div class="muted small">Este ícone não tem versão preenchida: aparece em contorno.</div>`);
  } else if (f.type === "levels") {
    row.classList.add("levels");
    const lv = { ...(val || {}) };
    for (const [k, l] of [["AMARELO", "🟡 a partir de"], ["VERMELHO", "🔴 a partir de"]]) {
      const r = document.createElement("div");
      r.className = "row";
      r.innerHTML = `<span>${l}</span>`;
      const inp = document.createElement("input");
      inp.type = "number";
      inp.value = lv[k] ?? "";
      inp.onchange = () => set({ ...lv, [k]: parseInt(inp.value, 10) });
      r.appendChild(inp);
      r.insertAdjacentHTML("beforeend", "°C");
      row.appendChild(r);
    }
  } else if (f.type === "colors3") {
    const cur = { VERDE: [90, 220, 120], AMARELO: [255, 200, 0], VERMELHO: [255, 70, 70], ...(val || {}) };
    for (const [k, l] of [["VERDE", "OK"], ["AMARELO", "Atenção"], ["VERMELHO", "Crítico"]]) {
      const inp = document.createElement("input");
      inp.type = "color";
      inp.value = hex(cur[k]);
      inp.title = l;
      inp.onchange = () => set({ ...cur, [k]: rgb(inp.value) });
      row.appendChild(inp);
    }
  }
  wrap.appendChild(row);
  return wrap;
}

function renderBackgroundProps(box) {
  const bg = S.layout.background || { type: "none" };
  const setBg = (patch) => commit(() => (S.layout.background = { ...bg, ...patch }));

  const f1 = document.createElement("div");
  f1.className = "field";
  f1.innerHTML = "<label>Fundo</label>";
  const sel = document.createElement("select");
  for (const [v, l] of [["color", "Cor sólida"], ["image", "Imagem"], ["none", "Nenhum (preto)"]]) sel.add(new Option(l, v, false, v === bg.type));
  sel.onchange = () => {
    if (sel.value === "image" && !bg.src) pickImage((src) => setBg({ type: "image", src }));
    else setBg({ type: sel.value });
  };
  f1.appendChild(sel);
  box.appendChild(f1);

  if (bg.type === "color") {
    const f2 = document.createElement("div");
    f2.className = "field";
    f2.innerHTML = "<label>Cor do fundo</label>";
    const inp = document.createElement("input");
    inp.type = "color";
    inp.value = hex(bg.color || [8, 10, 14]);
    inp.onchange = () => setBg({ color: rgb(inp.value) });
    f2.appendChild(inp);
    box.appendChild(f2);
  } else if (bg.type === "image") {
    const f3 = document.createElement("div");
    f3.className = "field";
    f3.innerHTML = `<label>Imagem</label>`;
    const b = document.createElement("button");
    b.textContent = "Trocar imagem…";
    b.onclick = () => pickImage((src) => setBg({ type: "image", src }));
    f3.appendChild(b);
    box.appendChild(f3);
    box.insertAdjacentHTML("beforeend", `<div class="muted small">A imagem é ajustada para cobrir a tela inteira (480×320), cortando as sobras.</div>`);
  }

  box.insertAdjacentHTML("beforeend", `<div class="sep"></div>`);
  const fa = document.createElement("div");
  fa.className = "field";
  fa.innerHTML = "<label>Autor</label>";
  const ia = document.createElement("input");
  ia.type = "text";
  ia.value = S.layout.author || "";
  ia.onchange = () => commit(() => (S.layout.author = ia.value));
  fa.appendChild(ia);
  box.appendChild(fa);
  box.insertAdjacentHTML("beforeend", `<div class="muted small" style="margin-top:10px">Selecione um item na tela ou na lista de camadas para editar. Itens estáticos (painéis, textos, imagens, linhas) fazem parte do fundo; dados são atualizados em tempo real.</div>`);
}

function duplicateSelected() {
  const item = byId(S.selected);
  if (!item || item.kind === "data") return;
  const copy = clone(item);
  copy.x += 8;
  copy.y += 8;
  if (copy.kind === "line") { copy.x2 += 8; copy.y2 += 8; }
  delete copy.name;
  addItem(copy);
}

// ---------------------------------------------------------------------------
// Imagens (upload para a pasta do preset)
// ---------------------------------------------------------------------------
function pickImage(onDone) {
  const input = $("fileInput");
  input.value = "";
  input.onchange = async () => {
    const file = input.files[0];
    if (!file) return;
    const data = await new Promise((res) => {
      const r = new FileReader();
      r.onload = () => res(r.result);
      r.readAsDataURL(file);
    });
    try {
      const out = await api("/api/upload", { name: S.name, filename: file.name, data });
      onDone(out.src);
      toast("Imagem adicionada", "ok");
    } catch (e) {
      toast(e.message, "error");
    }
  };
  input.click();
}

// ---------------------------------------------------------------------------
// Biblioteca de ícones (Tabler Icons): sugeridos + busca em todos
// ---------------------------------------------------------------------------
const plain = (s) => s.normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase();

async function loadSymbols() {
  if (!S.icons) {
    S.icons = await api("/api/icons");
    // Texto de busca sem acentos, para "ventoinha", "temperatura", "vídeo"... funcionarem de qualquer jeito
    S.iconSearch = Object.entries(S.icons.icons).map(([name, v]) => [name, plain(v[2]).split(/[\s-]+/)]);
  }
  return S.icons;
}

function symbolGlyph(name, style, cls = "glyph") {
  const v = S.icons && S.icons.icons[name];
  if (!v) return `<span class="${cls}">?</span>`;
  const filled = style === "filled" ? v[1] || 0 : 0;
  const code = filled || v[0] || v[1];
  const family = filled || !v[0] ? " filled" : "";
  return `<span class="${cls}${family}">&#${code};</span>`;
}

async function pickSymbol(onDone, style = "outline") {
  try { await loadSymbols(); } catch (e) { toast(`Não foi possível carregar os ícones: ${e.message}`, "error"); return; }
  const modal = $("iconModal");
  const search = $("iconSearch");
  const list = $("iconList");
  let curStyle = style === "filled" ? "filled" : "outline";
  const close = () => { modal.classList.add("hidden"); S.picking = false; };
  const cell = (name) => {
    const b = document.createElement("button");
    b.className = "icon-cell";
    b.title = name;
    b.innerHTML = `${symbolGlyph(name, curStyle)}<span class="nm">${escapeHtml(name)}</span>`;
    b.onclick = () => { close(); onDone(name, curStyle); };
    return b;
  };
  const grid = (names) => {
    const g = document.createElement("div");
    g.className = "icon-grid";
    for (const n of names) g.appendChild(cell(n));
    return g;
  };
  const draw = () => {
    list.innerHTML = "";
    const words = plain(search.value.trim()).split(/\s+/).filter(Boolean);
    if (!words.length) {
      for (const [group, names] of S.icons.suggested) {
        list.insertAdjacentHTML("beforeend", `<h3>${escapeHtml(group)}</h3>`);
        list.appendChild(grid(names.filter((n) => S.icons.icons[n])));
      }
      list.insertAdjacentHTML("beforeend", `<div class="muted small icon-foot">Digite para buscar entre os ${S.iconSearch.length} ícones (em português ou inglês). Ícones: Tabler Icons ${escapeHtml(S.icons.version)}, licença MIT.</div>`);
      return;
    }
    // Cada palavra digitada precisa ser o começo de alguma palavra do nome/tags ("rede" acha rede, não "credentials")
    let found = S.iconSearch.filter(([, tokens]) => words.every((w) => tokens.some((tk) => tk.startsWith(w))));
    if (curStyle === "filled") found = found.filter(([name]) => S.icons.icons[name][1]);
    // Ordem: nome exato > todas as palavras no nome > sugeridos (têm nome em português) > texto no nome > só nas tags; depois os nomes mais curtos
    const q = words.join("-");
    const suggested = new Set(S.icons.suggested.flatMap(([, names]) => names));
    const score = (name) => {
      const parts = name.split("-");
      if (name === q) return 4;
      if (words.every((w) => parts.includes(w))) return 3;
      if (suggested.has(name)) return 2;
      return words.every((w) => name.includes(w)) ? 1 : 0;
    };
    found = found.map(([name, tokens]) => [name, tokens, score(name)]);
    found.sort((a, b) => b[2] - a[2] || a[0].length - b[0].length || a[0].localeCompare(b[0]));
    const LIMIT = 400;
    list.insertAdjacentHTML("beforeend", `<div class="muted small">${found.length} ícone(s)${found.length > LIMIT ? ` — mostrando os ${LIMIT} primeiros, refine a busca` : ""}</div>`);
    if (found.length) list.appendChild(grid(found.slice(0, LIMIT).map(([n]) => n)));
    else list.insertAdjacentHTML("beforeend", `<div class="muted">Nada encontrado. Tente outra palavra (ex.: cpu, temperatura, rede, jogo).</div>`);
  };
  for (const b of modal.querySelectorAll("[data-style]")) {
    b.classList.toggle("on", b.dataset.style === curStyle);
    b.onclick = () => {
      curStyle = b.dataset.style;
      for (const o of modal.querySelectorAll("[data-style]")) o.classList.toggle("on", o === b);
      draw();
    };
  }
  $("iconClose").onclick = close;
  modal.onmousedown = (e) => { if (e.target === modal) close(); };
  search.oninput = () => { clearTimeout(search._t); search._t = setTimeout(draw, 120); };
  search.onkeydown = (e) => {
    if (e.key === "Escape") close();
    if (e.key === "Enter") list.querySelector(".icon-cell")?.click();
  };
  search.value = "";
  draw();
  S.picking = true;
  modal.classList.remove("hidden");
  search.focus();
}

// ---------------------------------------------------------------------------
// Presets: carregar, novo, salvar, aplicar
// ---------------------------------------------------------------------------
async function loadPresets() {
  const res = await api("/api/presets");
  S.presets = res.presets;
  S.active = res.active;
  const sel = $("presetSelect");
  sel.innerHTML = "";
  for (const p of S.presets) sel.add(new Option(p === S.active ? `${p} (na tela)` : p, p, false, p === S.name));
}

async function openPreset(name) {
  S.layout = await api(`/api/preset?name=${encodeURIComponent(name)}`);
  S.name = name;
  S.selected = null;
  S.history = [];
  S.future = [];
  setZoom(S.zoom);
  setDirty(false);
  await loadPresets();
  refresh();
}

function askName(msg, def = "") {
  const name = prompt(msg, def);
  if (name === null) return null;
  if (!/^[A-Za-z0-9 _\-]{1,40}$/.test(name)) {
    toast("Nome inválido: use letras, números, espaço, - ou _ (sem acentos)", "error");
    return null;
  }
  if (S.presets.includes(name) && !confirm(`Já existe um preset "${name}". Substituir?`)) return null;
  return name;
}

async function save(name = S.name, apply = false) {
  try {
    const res = await api(apply ? "/api/apply" : "/api/save", { name, layout: { ...S.layout, name } });
    if (res.problems && res.problems.length) {
      toast(`Não salvo: ${res.problems[0]}`, "error");
      return false;
    }
    S.name = name;
    S.active = res.active;
    setDirty(false);
    await loadPresets();
    if (apply) {
      S.appliedAt = Date.now();
      refreshLive();
    }
    toast(apply ? "Aplicado! A tela atualiza em alguns segundos." : "Preset salvo", "ok");
    return true;
  } catch (e) {
    toast(e.message, "error");
    return false;
  }
}

async function newPreset() {
  if (S.dirty && !confirm("Há alterações não salvas. Descartar e criar um novo preset?")) return;
  const name = askName("Nome do novo preset:");
  if (!name) return;
  const copy = confirm("Começar a partir do preset atual?\n\nOK = copiar o atual · Cancelar = tela em branco");
  const layout = copy ? { ...clone(S.layout), name } :
    { name, author: S.layout.author || "", width: 480, height: 320, orientation: "landscape", background: { type: "color", color: [8, 10, 14] }, custom_interval: 3, items: [] };
  S.layout = layout;
  S.name = name;
  if (await save(name)) await openPreset(name);
}

// ---------------------------------------------------------------------------
// Tela real (espelho do monitor)
// ---------------------------------------------------------------------------
async function refreshLive() {
  const img = $("liveImg");
  const info = $("liveInfo");
  try {
    const res = await fetch("/api/live", { headers: { "X-Backa-Token": TOKEN } });
    if (!res.ok) throw new Error();
    const state = res.headers.get("X-Monitor-State") || "running";
    const age = parseFloat(res.headers.get("X-Live-Age") || "0");
    const url = URL.createObjectURL(await res.blob());
    const old = img.src;
    img.src = url;
    if (old.startsWith("blob:")) URL.revokeObjectURL(old);
    img.classList.remove("hidden");
    $("liveEmpty").classList.add("hidden");
    // Logo depois de "Aplicar", a imagem ainda é a antiga até a tela terminar de redesenhar
    const applying = S.appliedAt && Date.now() - S.appliedAt < 30000 && age * 1000 > Date.now() - S.appliedAt - 1500;
    if (state === "reloading" || applying) {
      info.textContent = "⏳ atualizando a tela…";
      img.style.opacity = "0.55";
    } else if (state === "stopped") {
      info.textContent = "⏹ monitor parado (última imagem)";
      img.style.opacity = "0.4";
    } else {
      info.textContent = `● ao vivo · preset: ${S.active}`;
      img.style.opacity = "1";
      S.appliedAt = 0;
    }
  } catch {
    img.classList.add("hidden");
    $("liveEmpty").classList.remove("hidden");
    info.textContent = "";
  }
}

// ---------------------------------------------------------------------------
// Teclado e eventos
// ---------------------------------------------------------------------------
function onKey(ev) {
  if (S.picking) {
    if (ev.key === "Escape") $("iconClose").click();
    return;
  }
  const typing = ["INPUT", "SELECT", "TEXTAREA"].includes(document.activeElement.tagName);
  if ((ev.ctrlKey || ev.metaKey) && ev.key.toLowerCase() === "s") { ev.preventDefault(); save(); return; }
  if (typing) return;
  if ((ev.ctrlKey || ev.metaKey) && ev.key.toLowerCase() === "z") { ev.preventDefault(); undo(); return; }
  if ((ev.ctrlKey || ev.metaKey) && ev.key.toLowerCase() === "y") { ev.preventDefault(); redo(); return; }
  if ((ev.ctrlKey || ev.metaKey) && ev.key.toLowerCase() === "d") { ev.preventDefault(); duplicateSelected(); return; }
  const item = S.selected && byId(S.selected);
  if (!item) return;
  if (ev.key === "Delete" || ev.key === "Backspace") { ev.preventDefault(); removeItem(item.id); return; }
  if (ev.key === "Escape") { select(null); return; }
  const step = ev.shiftKey ? 10 : 1;
  const mv = { ArrowLeft: [-step, 0], ArrowRight: [step, 0], ArrowUp: [0, -step], ArrowDown: [0, step] }[ev.key];
  if (mv) {
    ev.preventDefault();
    commit(() => {
      item.x += mv[0];
      item.y += mv[1];
      if (item.kind === "line") { item.x2 += mv[0]; item.y2 += mv[1]; }
    });
  }
}

async function closeEditor() {
  // Encerra o servidor do editor (libera a porta). O monitor da tela continua rodando.
  if (S.dirty && !confirm("Há alterações não salvas. Fechar o editor mesmo assim?")) return;
  try { await api("/api/shutdown", {}); } catch { /* o servidor já pode ter fechado */ }
  S.dirty = false;
  document.body.innerHTML =
    '<div style="margin:auto;text-align:center;padding:40px"><h2 style="color:#e6e8ee;text-transform:none;font-size:18px">Editor fechado</h2>' +
    '<p class="muted">Pode fechar esta aba. A tela continua funcionando normalmente.<br>' +
    'Para abrir de novo: ícone da bandeja → <b>Editor de tela</b>.</p></div>';
}

function fitZoom() {
  // Maior zoom que cabe na área central (sem cortar a prévia)
  const avail = document.querySelector(".center").clientWidth - 60;
  const sel = $("zoomSelect");
  const options = [...sel.options].map((o) => parseFloat(o.value));
  const best = options.filter((z) => z * 480 <= avail).pop() || options[0];
  sel.value = String(best);
  S.zoom = best;
}

async function init() {
  S.catalog = await api("/api/catalog");
  loadSymbols().then(() => S.selected && renderProps()).catch(() => {});
  const { presets, active } = await api("/api/presets");
  S.presets = presets;
  fitZoom();
  await openPreset(presets.includes(active) ? active : presets[0]);

  $("presetSelect").onchange = async (e) => {
    if (S.dirty && !confirm("Há alterações não salvas. Trocar de preset mesmo assim?")) { e.target.value = S.name; return; }
    await openPreset(e.target.value);
  };
  $("btnNew").onclick = newPreset;
  $("btnSave").onclick = () => save();
  $("btnSaveAs").onclick = async () => { const n = askName("Salvar como (nome do preset):", `${S.name} 2`); if (n && await save(n)) await openPreset(n); };
  $("btnApply").onclick = () => save(S.name, true);
  $("btnUndo").onclick = undo;
  $("btnRedo").onclick = redo;
  $("btnClose").onclick = closeEditor;
  $("zoomSelect").onchange = (e) => setZoom(parseFloat(e.target.value));
  $("stage").addEventListener("mousedown", (e) => { if (e.target.id === "overlay" || e.target.id === "stageImg") select(null); });
  window.addEventListener("keydown", onKey);
  window.addEventListener("beforeunload", (e) => { if (S.dirty) { e.preventDefault(); e.returnValue = ""; } });
  refreshLive();
  setInterval(refreshLive, 1500);
}

init().catch((e) => toast(`Erro ao abrir o editor: ${e.message}`, "error"));
