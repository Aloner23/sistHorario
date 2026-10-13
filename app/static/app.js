// Horarios API v2 — cliente mínimo sin dependencias.
const $ = (s) => document.querySelector(s);
const DIAS = { lun: "Lunes", mar: "Martes", mie: "Miércoles", jue: "Jueves", vie: "Viernes", sab: "Sábado" };
const PALETA = ["#3b5bdb", "#e8590c", "#2b8a3e", "#ae3ec9", "#1098ad", "#f08c00", "#c2255c", "#5c940d",
  "#7048e8", "#0b7285", "#d6336c", "#495057"];

const state = { input: null, result: null, view: "grupo", selected: null };

function setStatus(msg, cls = "") {
  const el = $("#status");
  el.textContent = msg;
  el.className = "status " + cls;
}

async function loadDemo() {
  const r = await fetch("/v1/examples/demo");
  state.input = await r.json();
  $("#input").value = JSON.stringify(state.input, null, 2);
  setStatus(`Demo cargada: ${state.input.asignaciones.length} asignaciones, ${state.input.grupos.length} grupos`);
}

async function solve() {
  let body;
  try {
    body = JSON.parse($("#input").value);
  } catch (e) {
    setStatus("JSON inválido: " + e.message, "err");
    return;
  }
  body.configuracion = { ...(body.configuracion || {}), motor: $("#motor").value };
  const btn = $("#btn-solve");
  btn.disabled = true;
  setStatus("Resolviendo…");
  try {
    const r = await fetch("/v1/schedules/solve", {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
    });
    const data = await r.json();
    if (!r.ok) {
      const det = Array.isArray(data.detail) ? data.detail.map((d) => d.msg).join("; ") : data.detail;
      setStatus(`Error ${r.status}: ${det}`, "err");
      return;
    }
    state.input = body;
    state.result = data;
    render();
    const ok = data.estado === "optimo" || data.estado === "factible";
    setStatus(`${data.estado} · ${data.motor} · ${data.tiempo_ms} ms`, ok ? "ok" : "err");
  } catch (e) {
    setStatus("Error de red: " + e.message, "err");
  } finally {
    btn.disabled = false;
  }
}

function render() {
  const { result } = state;
  const diags = $("#diags");
  if (result.diagnosticos.length) {
    diags.hidden = false;
    diags.innerHTML = `<h2>No se pudo generar el horario</h2><ul>${result.diagnosticos
      .map((d) => `<li>${esc(d.mensaje)} <code>${esc(d.codigo)}</code></li>`).join("")}</ul>`;
  } else diags.hidden = true;

  const m = result.metricas;
  const met = $("#metrics");
  if (m) {
    met.hidden = false;
    const v = result.verificacion;
    met.innerHTML = [
      ["Restricciones duras", v.valido ? "✓ válido" : `${v.violaciones.length} fallas`, v.valido ? "ok" : ""],
      ["Horas asignadas", m.horas_asignadas],
      ["Huecos de grupos", m.huecos_grupos],
      ["Huecos de profesores", m.huecos_profesores],
      ["Horas fuera de turno", m.horas_fuera_de_turno],
      ["Costo objetivo", m.objetivo],
    ].map(([k, val, cls = ""]) => `<div class="metric"><div class="k">${k}</div><div class="v ${cls}">${val}</div></div>`).join("");
  } else met.hidden = true;

  $("#result").hidden = !result.horario.length;
  if (result.horario.length) renderView();
}

function entidades(view) {
  const inp = state.input;
  if (view === "grupo") return inp.grupos.map((g) => [g.id, `${g.id}`]);
  if (view === "profesor") return inp.profesores.map((p) => [p.id, p.nombre]);
  return inp.salones.map((s) => [s.id, s.id]);
}

function renderView() {
  document.querySelectorAll(".tab").forEach((t) => t.classList.toggle("active", t.dataset.view === state.view));
  const ents = entidades(state.view);
  if (!ents.some(([id]) => id === state.selected)) state.selected = ents[0]?.[0];
  $("#chips").innerHTML = ents.map(([id, label]) =>
    `<button class="chip ${id === state.selected ? "active" : ""}" data-id="${esc(id)}">${esc(label)}</button>`).join("");
  renderGrid();
}

function renderGrid() {
  const inp = state.input;
  const cfg = { dias: ["lun", "mar", "mie", "jue", "vie"], hora_inicio: 7, hora_fin: 21, ...(inp.configuracion || {}) };
  const materias = Object.fromEntries(inp.materias.map((m, i) => [m.clave, { ...m, color: PALETA[i % PALETA.length] }]));
  const profes = Object.fromEntries(inp.profesores.map((p) => [p.id, p]));
  const sesiones = state.result.horario.filter((s) => s[state.view] === state.selected);
  const horas = [];
  for (let h = cfg.hora_inicio; h < cfg.hora_fin; h++) horas.push(h);

  const grid = document.createElement("div");
  grid.className = "grid";
  grid.style.gridTemplateColumns = `64px repeat(${cfg.dias.length}, 1fr)`;
  grid.style.gridTemplateRows = `auto repeat(${horas.length}, minmax(34px, auto))`;
  grid.innerHTML = `<div class="h"></div>` + cfg.dias.map((d) => `<div class="h">${DIAS[d] || d}</div>`).join("");
  horas.forEach((h, i) => {
    const t = document.createElement("div");
    t.className = "t";
    t.style.gridRow = i + 2;
    t.style.gridColumn = 1;
    t.textContent = `${h}:00`;
    grid.appendChild(t);
    cfg.dias.forEach((_, j) => {
      const c = document.createElement("div");
      c.className = "c";
      c.style.gridRow = i + 2;
      c.style.gridColumn = j + 2;
      grid.appendChild(c);
    });
  });
  for (const s of sesiones) {
    const m = materias[s.materia];
    const b = document.createElement("div");
    b.className = "blk";
    b.style.setProperty("--c", m.color);
    b.style.gridColumn = cfg.dias.indexOf(s.dia) + 2;
    b.style.gridRow = `${s.inicio - cfg.hora_inicio + 2} / ${s.fin - cfg.hora_inicio + 2}`;
    const detalle = state.view === "grupo"
      ? [profes[s.profesor].nombre, s.salon]
      : state.view === "profesor" ? [s.grupo, s.salon] : [s.grupo, profes[s.profesor].nombre];
    b.innerHTML = `<b>${esc(m.nombre)}</b><span>${s.inicio}:00–${s.fin}:00 · ${esc(detalle[1])}</span><span>${esc(detalle[0])}</span>`;
    b.title = `${m.clave} · ${m.nombre}\n${s.grupo} · ${profes[s.profesor].nombre} · ${s.salon}`;
    grid.appendChild(b);
  }
  $("#grid").replaceChildren(grid);

  const usadas = [...new Set(sesiones.map((s) => s.materia))];
  $("#legend").innerHTML = usadas.map((c) =>
    `<span style="--c:${materias[c].color}"><i></i>${esc(c)} · ${esc(materias[c].nombre)}</span>`).join("");
}

function esc(s) {
  return String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
}

$("#btn-demo").addEventListener("click", loadDemo);
$("#btn-solve").addEventListener("click", solve);
$("#btn-toggle").addEventListener("click", () => { $("#input").hidden = !$("#input").hidden; });
document.querySelectorAll(".tab").forEach((t) => t.addEventListener("click", () => { state.view = t.dataset.view; renderView(); }));
$("#chips").addEventListener("click", (e) => {
  const id = e.target.closest(".chip")?.dataset.id;
  if (id) { state.selected = id; renderView(); }
});

loadDemo().then(solve);
