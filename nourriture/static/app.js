/* Nourriture — interface locale (JavaScript sans dépendance). */
"use strict";

const view = document.getElementById("view");
const DAYS = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"];
const UNITS = ["", "g", "kg", "ml", "cl", "l", "c. à soupe", "c. à café", "pincée", "gousse", "tranche", "boîte", "sachet", "botte", "poignée", "feuille", "brin", "verre"];
const TAG_SUGGESTIONS = ["végétarien", "vegan", "sans gluten", "sans lactose", "rapide", "healthy", "batch cooking", "économique", "gourmand", "apéro", "comfort food", "enfants", "été", "hiver", "sucré", "salé", "one pot", "four", "sans cuisson", "protéiné"];

const state = {
  health: null, settings: null, facets: { tags: [], categories: {}, total: 0 },
  lib: { q: "", category: "", tags: [], maxTime: "", favorites: false, sort: "recent" },
  recipes: [], job: null, jobTimer: null, draft: null, draftAnalysis: null,
  edit: null, servings: null,
  menuForm: { count: 7, moments: "soir", categories: [], tags: [], maxTime: "", servings: "", week_start: "" },
  menu: null, menuRecipes: {}, shopping: [], menuWarnings: [], savedMenus: [], menuDirty: false,
  importMode: "url", importFile: null,
};

/* ----------------------------------------------------------------------- utilitaires */
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const $ = (sel, root = view) => root.querySelector(sel);
const $$ = (sel, root = view) => Array.from(root.querySelectorAll(sel));

async function api(path, { method = "GET", body, form } = {}) {
  const opts = { method, headers: {} };
  if (form) opts.body = form;
  else if (body !== undefined) { opts.headers["Content-Type"] = "application/json"; opts.body = JSON.stringify(body); }
  const r = await fetch(path, opts);
  if (!r.ok) {
    let msg = r.statusText;
    try { const j = await r.json(); msg = typeof j.detail === "string" ? j.detail : JSON.stringify(j.detail || j); } catch (_) { /* ignore */ }
    throw new Error(msg);
  }
  const ct = r.headers.get("content-type") || "";
  return ct.includes("json") ? r.json() : r.text();
}

function toast(msg, kind = "") {
  const root = document.getElementById("toast-root");
  const el = document.createElement("div");
  el.className = "toast " + kind;
  el.textContent = msg;
  root.appendChild(el);
  setTimeout(() => { el.style.opacity = "0"; el.style.transition = "opacity .3s"; setTimeout(() => el.remove(), 320); }, kind === "error" ? 6000 : 3000);
}

function confirmDialog({ title, text, ok = "Confirmer", danger = false }) {
  return new Promise((resolve) => {
    const root = document.getElementById("modal-root");
    root.innerHTML = `<div class="modal-backdrop"><div class="modal"><h2>${esc(title)}</h2><p class="muted">${esc(text)}</p>
      <div class="actions"><button class="btn" data-x="cancel">Annuler</button><button class="btn ${danger ? "danger" : "primary"}" data-x="ok">${esc(ok)}</button></div></div></div>`;
    const close = (v) => { root.innerHTML = ""; resolve(v); };
    root.querySelector('[data-x="cancel"]').onclick = () => close(false);
    root.querySelector('[data-x="ok"]').onclick = () => close(true);
    root.querySelector(".modal-backdrop").onclick = (e) => { if (e.target.classList.contains("modal-backdrop")) close(false); };
  });
}

function openExternal(url) { if (url) api("/api/system/open-url", { method: "POST", body: { url } }).catch(() => window.open(url, "_blank")); }

function fmtQty(q) {
  if (q === null || q === undefined || q === "") return "";
  const n = Number(q); if (Number.isNaN(n)) return String(q);
  const whole = Math.floor(n), frac = Math.round((n - whole) * 100) / 100;
  const fr = { 0.25: "¼", 0.5: "½", 0.75: "¾", 0.33: "⅓", 0.34: "⅓", 0.66: "⅔", 0.67: "⅔", 0.13: "⅛", 0.12: "⅛" };
  if (fr[frac]) return (whole ? whole : "") + fr[frac];
  if (Math.abs(n - Math.round(n)) < 0.01) return String(Math.round(n));
  return String(Math.round(n * 10) / 10).replace(".", ",");
}
const PLURAL_UNITS = ["gousse", "tranche", "boîte", "sachet", "botte", "poignée", "feuille", "brin", "verre", "tasse", "pincée"];
function fmtUnit(unit, qty) { if (!unit) return ""; return PLURAL_UNITS.includes(unit) && qty != null && Number(qty) >= 2 ? unit + "s" : unit; }
function fmtTime(min) {
  if (min === null || min === undefined) return "—";
  min = Number(min); if (min < 60) return `${min} min`;
  const h = Math.floor(min / 60), m = min % 60; return m ? `${h} h ${String(m).padStart(2, "0")}` : `${h} h`;
}
function fmtDate(iso) { try { return new Date(iso).toLocaleDateString("fr-FR", { day: "numeric", month: "short", year: "numeric" }); } catch (_) { return iso || ""; } }
function fmtDay(iso) { try { const [y, m, d] = iso.split("-"); return `${d}/${m}/${y}`; } catch (_) { return iso; } }
function thumbUrl(r) { return r && r.thumbnail ? `/images/${encodeURIComponent(r.thumbnail)}` : null; }
function thumbStyle(r) { const u = thumbUrl(r); return u ? `style="background-image:url('${u}')"` : ""; }
function catEmoji(c) { return { "entrée": "🥗", "plat": "🍽️", "dessert": "🍰", "petit-déjeuner": "🥐", "snack": "🥨", "boisson": "🥤", "accompagnement": "🥔", "sauce": "🫙", "autre": "🍴" }[c] || "🍴"; }
function debounce(fn, ms) { let t; return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), ms); }; }
function nextMonday() { const d = new Date(); const day = d.getDay() || 7; d.setDate(d.getDate() + (8 - day) % 7 || 7); if (day === 1) d.setDate(d.getDate() - 7); return d.toISOString().slice(0, 10); }
function applyTheme(theme) { if (theme === "light" || theme === "dark") document.documentElement.dataset.theme = theme; else delete document.documentElement.dataset.theme; }

/* ----------------------------------------------------------------------- santé */
async function refreshHealth() {
  try {
    state.health = await api("/api/health");
    const h = state.health, pill = document.getElementById("status-pill");
    const ollamaOk = h.ollama.running && h.ollama.has_model, whisperOk = h.whisper.downloaded;
    pill.className = "status-pill " + (ollamaOk && whisperOk ? "ok" : (h.ollama.running ? "warn" : "bad"));
    pill.querySelector(".label").textContent = !h.ollama.running ? "Ollama arrêté" : !h.ollama.has_model ? "Modèle IA manquant" : !whisperOk ? "Whisper à télécharger" : "IA locale prête";
    document.getElementById("recipe-count").textContent = `${h.counts.recipes} recette${h.counts.recipes > 1 ? "s" : ""}`;
  } catch (e) { /* serveur en cours de démarrage */ }
}
document.getElementById("status-pill").onclick = () => { location.hash = "#/settings"; };

/* ----------------------------------------------------------------------- routage */
function setActiveNav(route) { $$(".nav a", document).forEach((a) => a.classList.toggle("active", a.dataset.route === route)); }

async function router() {
  const hash = location.hash || "#/library";
  const [, route, arg] = hash.match(/^#\/([a-z-]+)\/?(.*)$/) || [null, "library", ""];
  clearInterval(state.jobTimer);
  try {
    if (route === "library") { setActiveNav("library"); await renderLibrary(); }
    else if (route === "recipe") { setActiveNav("library"); await renderRecipe(arg); }
    else if (route === "edit") { setActiveNav("library"); await renderEditorFor(arg); }
    else if (route === "draft") { setActiveNav("import"); renderDraft(); }
    else if (route === "import") { setActiveNav("import"); await renderImport(arg); }
    else if (route === "menus") { setActiveNav("menus"); await renderMenus(arg); }
    else if (route === "settings") { setActiveNav("settings"); await renderSettings(); }
    else { location.hash = "#/library"; }
  } catch (e) { view.innerHTML = `<div class="alert error">Erreur : ${esc(e.message)}</div>`; }
  view.scrollTop = 0;
}
window.addEventListener("hashchange", router);

/* ======================================================================= BIBLIOTHÈQUE */
async function loadRecipes() {
  const l = state.lib;
  const qs = new URLSearchParams({ q: l.q, category: l.category, tags: l.tags.join(","), sort: l.sort });
  if (l.maxTime) qs.set("max_time", l.maxTime);
  if (l.favorites) qs.set("favorites", "true");
  const [r, f] = await Promise.all([api("/api/recipes?" + qs), api("/api/recipes/facets")]);
  state.recipes = r.recipes; state.facets = f;
}

async function renderLibrary() {
  await loadRecipes();
  const l = state.lib, f = state.facets;
  const cats = state.health ? state.health.categories : Object.keys(f.categories);
  const topTags = f.tags.slice(0, 30);
  view.innerHTML = `
  <div class="view-header"><div><h1>Bibliothèque</h1><div class="muted">${f.total} recette${f.total > 1 ? "s" : ""} enregistrée${f.total > 1 ? "s" : ""}</div></div>
    <div class="row"><button class="btn" id="btn-export">⬆️ Exporter</button><button class="btn" id="btn-import-json">⬇️ Importer un fichier</button><a class="btn primary" href="#/import">＋ Importer d'Instagram</a></div></div>
  <div class="toolbar">
    <div class="search"><input type="search" id="q" placeholder="Rechercher un plat, un ingrédient…" value="${esc(l.q)}"></div>
    <select id="sort"><option value="recent" ${l.sort === "recent" ? "selected" : ""}>Plus récentes</option><option value="oldest" ${l.sort === "oldest" ? "selected" : ""}>Plus anciennes</option><option value="title" ${l.sort === "title" ? "selected" : ""}>Titre A→Z</option><option value="time" ${l.sort === "time" ? "selected" : ""}>Plus rapides</option></select>
    <select id="maxtime"><option value="">Tous les temps</option>${[15, 20, 30, 45, 60, 90].map((t) => `<option value="${t}" ${String(l.maxTime) === String(t) ? "selected" : ""}>≤ ${t} min</option>`).join("")}</select>
    <button class="chip ${l.favorites ? "active" : ""}" id="fav">♥ Favoris</button>
  </div>
  <div class="filters">
    <div class="chips" id="cats"><span class="chip ${!l.category ? "active" : ""}" data-cat="">Toutes</span>${cats.map((c) => `<span class="chip ${l.category === c ? "active" : ""}" data-cat="${esc(c)}">${catEmoji(c)} ${esc(c)}${f.categories[c] ? ` <span class="muted">${f.categories[c]}</span>` : ""}</span>`).join("")}</div>
  </div>
  ${topTags.length ? `<div class="chips mb" id="tags">${topTags.map((t) => `<span class="chip ${l.tags.includes(t.tag) ? "active" : ""}" data-tag="${esc(t.tag)}">#${esc(t.tag)} <span class="muted">${t.count}</span></span>`).join("")}</div>` : ""}
  ${state.recipes.length ? `<div class="grid">${state.recipes.map(cardHtml).join("")}</div>` : emptyLibraryHtml()}`;

  $("#q").oninput = debounce((e) => { l.q = e.target.value; renderLibrary(); }, 250);
  $("#sort").onchange = (e) => { l.sort = e.target.value; renderLibrary(); };
  $("#maxtime").onchange = (e) => { l.maxTime = e.target.value; renderLibrary(); };
  $("#fav").onclick = () => { l.favorites = !l.favorites; renderLibrary(); };
  $$("#cats .chip").forEach((c) => { c.onclick = () => { l.category = c.dataset.cat; renderLibrary(); }; });
  $$("#tags .chip").forEach((c) => { c.onclick = () => { const t = c.dataset.tag; l.tags = l.tags.includes(t) ? l.tags.filter((x) => x !== t) : [...l.tags, t]; renderLibrary(); }; });
  bindCards();
  $("#btn-export").onclick = exportAll;
  $("#btn-import-json").onclick = () => importJsonDialog();
}

function emptyLibraryHtml() {
  const filtered = state.lib.q || state.lib.category || state.lib.tags.length || state.lib.maxTime || state.lib.favorites;
  if (filtered) return `<div class="empty"><div class="big">🔎</div><p>Aucune recette ne correspond à ces filtres.</p></div>`;
  return `<div class="empty"><div class="big">🍲</div><p><strong>Votre bibliothèque est vide.</strong></p><p>Collez un lien Instagram pour importer votre première recette.</p><p class="mt"><a class="btn primary" href="#/import">Importer une recette</a></p></div>`;
}

function cardHtml(r) {
  const u = thumbUrl(r);
  return `<div class="recipe-card" data-id="${r.id}">
    <div class="thumb" ${thumbStyle(r)}>${u ? "" : catEmoji(r.category)}</div>
    <button class="fav" data-fav="${r.id}" title="Favori">${r.favorite ? "❤️" : "🤍"}</button>
    <div class="body"><div class="title">${esc(r.title)}</div>
      <div class="meta"><span class="badge cat">${esc(r.category)}</span>${r.total_time_min != null ? `<span>⏱ ${fmtTime(r.total_time_min)}</span>` : ""}${r.servings ? `<span>👥 ${r.servings}</span>` : ""}</div>
      <div class="meta">${r.author ? `<span>${esc(r.author)}</span>` : ""}${r.estimated_count ? `<span class="badge est">${r.estimated_count} estimée${r.estimated_count > 1 ? "s" : ""}</span>` : ""}</div>
      ${r.tags.length ? `<div class="chips">${r.tags.slice(0, 4).map((t) => `<span class="chip static tiny">#${esc(t)}</span>`).join("")}</div>` : ""}</div></div>`;
}

function bindCards(root = view) {
  $$(".recipe-card", root).forEach((c) => { c.onclick = (e) => { if (e.target.closest(".fav")) return; location.hash = `#/recipe/${c.dataset.id}`; }; });
  $$("[data-fav]", root).forEach((b) => { b.onclick = async (e) => { e.stopPropagation(); const { recipe } = await api(`/api/recipes/${b.dataset.fav}/favorite`, { method: "POST" }); b.textContent = recipe.favorite ? "❤️" : "🤍"; }; });
}

async function exportAll(ids) {
  try {
    const res = await api("/api/export/save", { method: "POST", body: { ids: ids || [] } });
    toast(`${res.count} recette${res.count > 1 ? "s" : ""} exportée${res.count > 1 ? "s" : ""} dans Téléchargements.`, "ok");
  } catch (e) { toast("Export impossible : " + e.message, "error"); }
}

function importJsonDialog() {
  const root = document.getElementById("modal-root");
  root.innerHTML = `<div class="modal-backdrop"><div class="modal"><h2>Importer des recettes</h2>
    <p class="muted">Choisissez un fichier JSON exporté depuis Nourriture (le vôtre ou celui d'un ami).</p>
    <label class="field mt">Fichier<input type="file" id="json-file" accept=".json,application/json"></label>
    <label class="field mt">Si une recette existe déjà<select id="json-mode"><option value="skip">L'ignorer</option><option value="replace">La remplacer par la version importée</option></select></label>
    <div class="actions"><button class="btn" data-x="cancel">Annuler</button><button class="btn primary" data-x="ok">Importer</button></div></div></div>`;
  root.querySelector('[data-x="cancel"]').onclick = () => { root.innerHTML = ""; };
  root.querySelector('[data-x="ok"]').onclick = async () => {
    const f = root.querySelector("#json-file").files[0];
    if (!f) { toast("Choisissez un fichier.", "error"); return; }
    const form = new FormData(); form.append("file", f); form.append("mode", root.querySelector("#json-mode").value);
    try {
      const r = await api("/api/import-json", { method: "POST", form });
      root.innerHTML = "";
      toast(`${r.imported} importée(s), ${r.updated} mise(s) à jour, ${r.skipped} ignorée(s)${r.errors ? `, ${r.errors} en erreur` : ""}.`, "ok");
      refreshHealth(); router();
    } catch (e) { toast("Import impossible : " + e.message, "error"); }
  };
}

/* ======================================================================= DÉTAIL */
async function renderRecipe(id) {
  const { recipe: r } = await api(`/api/recipes/${id}`);
  state.servings = r.servings || null;
  const factor = () => (state.servings && r.servings ? state.servings / r.servings : 1);
  const draw = () => {
    const u = thumbUrl(r);
    view.innerHTML = `
    <div class="row between mb"><a class="btn ghost" href="#/library">← Bibliothèque</a>
      <div class="row"><button class="btn" id="fav">${r.favorite ? "❤️ Favori" : "🤍 Favori"}</button><a class="btn" href="#/edit/${r.id}">✏️ Modifier</a><button class="btn" id="export-one">⬆️ Exporter</button><button class="btn danger" id="del">🗑 Supprimer</button></div></div>
    <div class="detail">
      <div>
        <h1>${esc(r.title)}</h1>
        <div class="muted mb">${r.author ? `<a href="#" id="author-link">${esc(r.author)}</a> · ` : ""}${r.source_url ? `<a href="#" id="source-link">Voir sur Instagram ↗</a> · ` : ""}ajoutée le ${fmtDate(r.created_at)}</div>
        <div class="chips mb"><span class="badge cat">${catEmoji(r.category)} ${esc(r.category)}</span>${r.tags.map((t) => `<span class="chip static" data-tag="${esc(t)}">#${esc(t)}</span>`).join("")}</div>
        <div class="row between"><h2 style="margin:10px 0">Ingrédients</h2>
          <div class="servings-ctl"><button id="s-minus">−</button><span>${state.servings || "?"} portion${(state.servings || 0) > 1 ? "s" : ""}</span><button id="s-plus">+</button></div></div>
        <ul class="ingredients">${r.ingredients.map((i) => `<li><span class="qty">${esc(fmtQty(i.quantity != null ? i.quantity * factor() : null))} ${esc(fmtUnit(i.unit, i.quantity != null ? i.quantity * factor() : null))}</span><span>${esc(i.name)}${i.note ? ` <span class="muted">(${esc(i.note)})</span>` : ""}${i.estimated ? ` <span class="badge est">quantité estimée</span>` : ""}</span></li>`).join("") || "<li class='muted'>Aucun ingrédient.</li>"}</ul>
        <h2>Préparation</h2>
        <ol class="steps">${r.steps.map((s) => `<li><div>${esc(s)}</div></li>`).join("") || "<li class='muted'>Aucune étape.</li>"}</ol>
        ${r.notes ? `<h2>Notes</h2><p>${esc(r.notes)}</p>` : ""}
        ${r.sources && (r.sources.caption || r.sources.transcript || r.sources.ocr_text) ? `<details class="sources"><summary class="muted">Sources brutes (description, transcription, texte à l'écran)</summary>
          ${r.sources.caption ? `<h3>Description Instagram</h3><pre>${esc(r.sources.caption)}</pre>` : ""}
          ${r.sources.transcript ? `<h3>Transcription audio</h3><pre>${esc(r.sources.transcript)}</pre>` : ""}
          ${r.sources.ocr_text ? `<h3>Texte à l'écran</h3><pre>${esc(r.sources.ocr_text)}</pre>` : ""}
          <p class="tiny muted">Modèle : ${esc(r.sources.llm_model || "?")}${r.sources.confidence ? ` · confiance ${esc(r.sources.confidence)}` : ""}${r.sources.used_caption_only ? " · générée à partir de la description seule" : ""}</p></details>` : ""}
      </div>
      <div class="side">
        <div class="hero" ${thumbStyle(r)}>${u ? "" : `<div class="empty"><div class="big">${catEmoji(r.category)}</div></div>`}</div>
        <div class="card"><div class="meta-grid">
          <div><span>Préparation</span>${fmtTime(r.prep_time_min)}</div><div><span>Cuisson</span>${fmtTime(r.cook_time_min)}</div>
          <div><span>Portions</span>${r.servings ?? "—"}</div><div><span>Protéine</span>${esc(r.main_protein || "—")}</div>
          <div><span>Cuisine</span>${esc(r.cuisine || "—")}</div><div><span>Catégorie</span>${esc(r.category)}</div></div></div>
      </div></div>`;
    $("#s-minus").onclick = () => { if ((state.servings || 1) > 1) { state.servings = (state.servings || 1) - 1; draw(); } };
    $("#s-plus").onclick = () => { state.servings = (state.servings || 0) + 1; draw(); };
    $("#fav").onclick = async () => { const res = await api(`/api/recipes/${r.id}/favorite`, { method: "POST" }); r.favorite = res.recipe.favorite; draw(); };
    $("#export-one").onclick = () => exportAll([r.id]);
    $("#del").onclick = async () => {
      if (await confirmDialog({ title: "Supprimer cette recette ?", text: `« ${r.title} » sera définitivement supprimée.`, ok: "Supprimer", danger: true })) {
        await api(`/api/recipes/${r.id}`, { method: "DELETE" }); toast("Recette supprimée."); refreshHealth(); location.hash = "#/library";
      }
    };
    if ($("#author-link")) $("#author-link").onclick = (e) => { e.preventDefault(); openExternal(r.author_url || r.source_url); };
    if ($("#source-link")) $("#source-link").onclick = (e) => { e.preventDefault(); openExternal(r.source_url); };
    $$(".chip[data-tag]").forEach((c) => { c.style.cursor = "pointer"; c.onclick = () => { state.lib.tags = [c.dataset.tag]; location.hash = "#/library"; }; });
  };
  draw();
}

/* ======================================================================= ÉDITEUR */
async function renderEditorFor(id) {
  const { recipe } = await api(`/api/recipes/${id}`);
  renderEditor(recipe, { mode: "edit" });
}

function renderDraft() {
  if (!state.draft) { location.hash = "#/import"; return; }
  renderEditor(state.draft, { mode: "draft", analysis: state.draftAnalysis });
}

function renderEditor(recipe, { mode, analysis }) {
  const e = state.edit = JSON.parse(JSON.stringify(recipe));
  e.ingredients = e.ingredients || []; e.steps = e.steps || []; e.tags = e.tags || [];
  const cats = (state.health && state.health.categories) || ["plat"];
  const prots = (state.health && state.health.proteins) || [];

  const draw = () => {
    const u = thumbUrl(e);
    const a = analysis;
    view.innerHTML = `
    <div class="editor">
      <div class="row between mb"><a class="btn ghost" href="${mode === "draft" ? "#/import" : `#/recipe/${e.id}`}">← ${mode === "draft" ? "Retour à l'import" : "Retour à la recette"}</a></div>
      ${mode === "draft" ? `<h1>Vérifiez la recette</h1><p class="muted">L'IA locale a rédigé cette recette. Corrigez ce qui doit l'être, puis enregistrez-la dans votre bibliothèque.</p>
        ${a ? `<div class="alert ${a.is_recipe === false ? "warn" : "info"} mb">
          ${a.is_recipe === false ? "⚠️ Le modèle doute qu'il s'agisse d'une recette. " : ""}
          ${a.caption_had_recipe ? "La description Instagram contenait la recette." : "La description ne contenait pas la recette complète."}
          ${a.media_analyzed ? ` Vidéo analysée : ${a.transcript_chars ? `transcription (${a.transcript_chars} caractères${a.transcript_language ? `, ${a.transcript_language}` : ""})` : "pas de parole exploitable"}${a.ocr_lines ? `, ${a.ocr_lines} ligne(s) de texte à l'écran` : ""}.` : " La vidéo n'a pas été analysée (plus rapide)."}
          ${a.estimated_count ? ` ${a.estimated_count} quantité(s) estimée(s) par l'IA.` : ""}
          ${a.confidence ? ` Confiance : ${esc(a.confidence)}.` : ""}
          ${a.duplicate_of ? `<br>⚠️ Cette publication est déjà dans la bibliothèque : <a href="#/recipe/${a.duplicate_of.id}">${esc(a.duplicate_of.title)}</a>.` : ""}
          ${!a.media_analyzed && e.source_url && (a.media_type === "video" || a.media_type === "carousel") ? `<br><button class="btn small mt" id="reanalyze">🎬 Ré-analyser en incluant la vidéo (audio + texte à l'écran)</button>` : ""}
        </div>` : ""}` : `<h1>Modifier la recette</h1>`}
      <div class="card">
        <div class="row" style="align-items:flex-start;gap:18px">
          <div class="thumb-edit" ${thumbStyle(e)}>${u ? "" : catEmoji(e.category)}</div>
          <div class="grow">
            <label class="field">Titre<input type="text" id="f-title" value="${esc(e.title)}"></label>
            <div class="field-grid mt">
              <label class="field">Catégorie<select id="f-category">${cats.map((c) => `<option ${e.category === c ? "selected" : ""}>${esc(c)}</option>`).join("")}</select></label>
              <label class="field">Protéine principale<select id="f-protein"><option value="">—</option>${prots.map((p) => `<option ${e.main_protein === p ? "selected" : ""}>${esc(p)}</option>`).join("")}</select></label>
              <label class="field">Cuisine<input type="text" id="f-cuisine" value="${esc(e.cuisine || "")}" placeholder="italienne, asiatique…"></label>
              <label class="field">Portions<input type="number" id="f-servings" min="1" max="50" value="${e.servings ?? ""}"></label>
              <label class="field">Préparation (min)<input type="number" id="f-prep" min="0" value="${e.prep_time_min ?? ""}"></label>
              <label class="field">Cuisson (min)<input type="number" id="f-cook" min="0" value="${e.cook_time_min ?? ""}"></label>
            </div>
            <div class="row mt"><label class="btn small">🖼 Changer l'image<input type="file" id="f-thumb" accept="image/*" class="hidden"></label><span class="tiny muted">JPEG ou PNG, recadrée automatiquement.</span></div>
          </div>
        </div>
        <div class="field-grid mt">
          <label class="field">Auteur<input type="text" id="f-author" value="${esc(e.author || "")}" placeholder="@compte"></label>
          <label class="field">Lien source<input type="url" id="f-source" value="${esc(e.source_url || "")}"></label>
        </div>
        <label class="field mt">Étiquettes (séparées par des virgules)<input type="text" id="f-tags" value="${esc(e.tags.join(", "))}"></label>
        <div class="chips mt" id="tag-suggest">${TAG_SUGGESTIONS.map((t) => `<span class="chip ${e.tags.includes(t) ? "active" : ""}" data-t="${esc(t)}">${esc(t)}</span>`).join("")}</div>
      </div>

      <div class="card">
        <div class="row between"><h2 style="margin:0">Ingrédients</h2><button class="btn small" id="add-ing">＋ Ajouter</button></div>
        <table class="ing-table mt"><thead><tr class="muted small"><td class="num">Quantité</td><td class="unit">Unité</td><td>Ingrédient</td><td>Précision</td><td class="est">Estimée</td><td class="del"></td></tr></thead>
        <tbody>${e.ingredients.map((i, idx) => `<tr data-i="${idx}">
          <td class="num"><input type="text" class="i-qty" value="${i.quantity ?? ""}" placeholder="—"></td>
          <td class="unit"><select class="i-unit">${UNITS.map((un) => `<option value="${esc(un)}" ${(i.unit || "") === un ? "selected" : ""}>${un || "(pièce)"}</option>`).join("")}${i.unit && !UNITS.includes(i.unit) ? `<option selected>${esc(i.unit)}</option>` : ""}</select></td>
          <td><input type="text" class="i-name" value="${esc(i.name)}"></td>
          <td><input type="text" class="i-note" value="${esc(i.note || "")}" placeholder="haché, facultatif…"></td>
          <td class="est"><input type="checkbox" class="i-est" ${i.estimated ? "checked" : ""} title="Quantité estimée par l'IA"></td>
          <td class="del"><button class="btn icon ghost i-del" title="Retirer">✕</button></td></tr>`).join("")}</tbody></table>
        ${!e.ingredients.length ? `<p class="muted small">Aucun ingrédient : ajoutez-en.</p>` : ""}
      </div>

      <div class="card">
        <div class="row between"><h2 style="margin:0">Étapes</h2><button class="btn small" id="add-step">＋ Ajouter une étape</button></div>
        <div class="mt" id="steps">${e.steps.map((s, idx) => `<div class="step-row" data-s="${idx}"><div class="n">${idx + 1}</div><textarea class="s-text">${esc(s)}</textarea>
          <div class="ctl"><button class="btn icon ghost s-up" title="Monter" ${idx === 0 ? "disabled" : ""}>↑</button><button class="btn icon ghost s-down" title="Descendre" ${idx === e.steps.length - 1 ? "disabled" : ""}>↓</button><button class="btn icon ghost s-del" title="Supprimer">✕</button></div></div>`).join("")}</div>
        <label class="field mt">Notes / astuces<textarea id="f-notes">${esc(e.notes || "")}</textarea></label>
      </div>
      <div class="sticky-actions"><a class="btn" href="${mode === "draft" ? "#/import" : `#/recipe/${e.id}`}">Annuler</a><button class="btn primary" id="save">${mode === "draft" ? "💾 Enregistrer dans la bibliothèque" : "💾 Enregistrer les modifications"}</button></div>
    </div>`;

    $("#add-ing").onclick = () => { sync(); e.ingredients.push({ name: "", quantity: null, unit: null, estimated: false, note: null }); draw(); setTimeout(() => { const rows = $$("tbody tr"); rows[rows.length - 1].querySelector(".i-name").focus(); }, 0); };
    $$(".i-del").forEach((b) => { b.onclick = () => { sync(); e.ingredients.splice(Number(b.closest("tr").dataset.i), 1); draw(); }; });
    $("#add-step").onclick = () => { sync(); e.steps.push(""); draw(); setTimeout(() => { const t = $$(".s-text"); t[t.length - 1].focus(); }, 0); };
    $$(".s-del").forEach((b) => { b.onclick = () => { sync(); e.steps.splice(Number(b.closest(".step-row").dataset.s), 1); draw(); }; });
    $$(".s-up").forEach((b) => { b.onclick = () => { sync(); const i = Number(b.closest(".step-row").dataset.s); [e.steps[i - 1], e.steps[i]] = [e.steps[i], e.steps[i - 1]]; draw(); }; });
    $$(".s-down").forEach((b) => { b.onclick = () => { sync(); const i = Number(b.closest(".step-row").dataset.s); [e.steps[i + 1], e.steps[i]] = [e.steps[i], e.steps[i + 1]]; draw(); }; });
    $$("#tag-suggest .chip").forEach((c) => { c.onclick = () => { sync(); const t = c.dataset.t; e.tags = e.tags.includes(t) ? e.tags.filter((x) => x !== t) : [...e.tags, t]; draw(); }; });
    $("#f-thumb").onchange = async (ev) => {
      const f = ev.target.files[0]; if (!f) return;
      const form = new FormData(); form.append("file", f);
      try {
        if (mode === "draft") { const r = await api(`/api/drafts/${e.id}/thumbnail`, { method: "POST", form }); e.thumbnail = r.thumbnail; }
        else { const r = await api(`/api/recipes/${e.id}/thumbnail`, { method: "POST", form }); e.thumbnail = r.recipe.thumbnail; }
        sync(); draw(); toast("Image mise à jour.");
      } catch (err) { toast(err.message, "error"); }
    };
    if ($("#reanalyze")) $("#reanalyze").onclick = () => startImport({ url: e.source_url, force_video_analysis: true });
    $("#save").onclick = save;
  };

  const sync = () => {
    e.title = $("#f-title").value; e.category = $("#f-category").value; e.main_protein = $("#f-protein").value || null;
    e.cuisine = $("#f-cuisine").value || null; e.servings = $("#f-servings").value ? Number($("#f-servings").value) : null;
    e.prep_time_min = $("#f-prep").value !== "" ? Number($("#f-prep").value) : null; e.cook_time_min = $("#f-cook").value !== "" ? Number($("#f-cook").value) : null;
    e.author = $("#f-author").value || null; e.source_url = $("#f-source").value || null; e.notes = $("#f-notes").value || null;
    e.tags = $("#f-tags").value.split(",").map((t) => t.trim().toLowerCase()).filter(Boolean).filter((t, i, arr) => arr.indexOf(t) === i);
    e.ingredients = $$("tbody tr").map((tr) => ({
      name: tr.querySelector(".i-name").value.trim(), quantity: tr.querySelector(".i-qty").value.trim() || null,
      unit: tr.querySelector(".i-unit").value || null, note: tr.querySelector(".i-note").value.trim() || null, estimated: tr.querySelector(".i-est").checked,
    }));
    e.steps = $$(".s-text").map((t) => t.value);
  };

  const save = async () => {
    sync();
    const payload = { ...e, ingredients: e.ingredients.filter((i) => i.name), steps: e.steps.map((s) => s.trim()).filter(Boolean) };
    if (!payload.title.trim()) { toast("Donnez un titre à la recette.", "error"); return; }
    try {
      const btn = $("#save"); btn.disabled = true; btn.textContent = "Enregistrement…";
      const res = mode === "draft" ? await api("/api/recipes", { method: "POST", body: payload }) : await api(`/api/recipes/${e.id}`, { method: "PUT", body: payload });
      if (mode === "draft") { state.draft = null; state.draftAnalysis = null; state.job = null; }
      toast("Recette enregistrée.", "ok"); refreshHealth();
      location.hash = `#/recipe/${res.recipe.id}`;
    } catch (err) { toast("Enregistrement impossible : " + err.message, "error"); $("#save").disabled = false; }
  };
  draw();
}

/* ======================================================================= IMPORT */
async function renderImport() {
  await refreshHealth();
  const h = state.health;
  const ready = h && h.ollama.running && h.ollama.has_model;
  view.innerHTML = `
  <div class="import-box">
    <h1>Importer une recette</h1>
    <p class="muted">Collez le lien d'un post ou d'un reel Instagram. Tout est traité sur votre Mac : description, transcription de la voix (Whisper), lecture du texte à l'écran (Vision) puis rédaction de la recette par l'IA locale (Ollama).</p>
    ${!ready ? setupCardHtml(h) : ""}
    <div class="card mt">
      <div class="row mb"><span class="chip ${state.importMode === "url" ? "active" : ""}" data-mode="url">Lien Instagram</span><span class="chip ${state.importMode === "manual" ? "active" : ""}" data-mode="manual">Saisie manuelle / fichier</span></div>
      <div id="mode-url" class="${state.importMode === "url" ? "" : "hidden"}">
        <div class="url-row"><input type="url" id="url" placeholder="https://www.instagram.com/reel/…" autofocus><button class="btn primary" id="go">Importer</button></div>
        <label class="check mt small"><input type="checkbox" id="force"> Analyser la vidéo même si la description contient la recette (plus lent, plus complet)</label>
      </div>
      <div id="mode-manual" class="${state.importMode === "manual" ? "" : "hidden"}">
        <p class="small muted">Si la récupération automatique échoue (publication privée, limitation d'Instagram), collez ici la description de la recette et/ou déposez la vidéo ou l'image que vous avez enregistrée.</p>
        <label class="field">Lien Instagram (facultatif, pour la source)<input type="url" id="m-url" placeholder="https://www.instagram.com/…"></label>
        <label class="field mt">Description / texte de la recette<textarea id="m-caption" rows="6" placeholder="Collez ici la description du post…"></textarea></label>
        <label class="field mt">Auteur (facultatif)<input type="text" id="m-author" placeholder="@compte"></label>
        <div class="dropzone mt" id="drop">${state.importFile ? `📎 ${esc(state.importFile.name)} <button class="btn small ghost" id="clear-file">✕</button>` : `Glissez une vidéo ou une image ici, ou <label class="btn small">choisir un fichier<input type="file" id="m-file" accept="video/*,image/*" class="hidden"></label>`}</div>
        <div class="row mt"><button class="btn primary" id="go-manual">Analyser</button></div>
      </div>
    </div>
    <div id="progress"></div>
  </div>`;
  $$("[data-mode]").forEach((c) => { c.onclick = () => { state.importMode = c.dataset.mode; renderImport(); }; });
  bindSetupCard();
  const go = () => { const url = $("#url").value.trim(); if (!url) { toast("Collez un lien Instagram.", "error"); return; } startImport({ url, force_video_analysis: $("#force").checked }); };
  $("#go").onclick = go;
  $("#url").onkeydown = (ev) => { if (ev.key === "Enter") go(); };
  $("#go-manual").onclick = () => {
    const caption = $("#m-caption").value.trim(), url = $("#m-url").value.trim();
    if (!caption && !state.importFile && !url) { toast("Collez une description, un lien ou déposez un fichier.", "error"); return; }
    startImport({ url: url || null, manual_caption: caption || null, manual_author: $("#m-author").value.trim() || null, force_video_analysis: true }, state.importFile);
  };
  const drop = $("#drop");
  if (drop) {
    drop.ondragover = (ev) => { ev.preventDefault(); drop.classList.add("over"); };
    drop.ondragleave = () => drop.classList.remove("over");
    drop.ondrop = (ev) => { ev.preventDefault(); drop.classList.remove("over"); const f = ev.dataTransfer.files[0]; if (f) { state.importFile = f; renderImport(); } };
    const fi = $("#m-file"); if (fi) fi.onchange = (ev) => { state.importFile = ev.target.files[0] || null; renderImport(); };
    const cf = $("#clear-file"); if (cf) cf.onclick = () => { state.importFile = null; renderImport(); };
  }
  if (state.job && state.job.status !== "done") { renderJob(); if (state.job.status === "running" || state.job.status === "queued") pollJob(); }
}

function setupCardHtml(h) {
  if (!h) return "";
  const items = [];
  if (!h.ollama.app_installed) items.push(`<li>Installez <strong>Ollama</strong> (gratuit) : <button class="btn small" data-open="https://ollama.com/download">Télécharger Ollama ↗</button> puis ouvrez-le une fois.</li>`);
  else if (!h.ollama.running) items.push(`<li>Ollama n'est pas lancé : <button class="btn small" id="start-ollama">Lancer Ollama</button></li>`);
  if (h.ollama.running && !h.ollama.has_model) items.push(`<li>Le modèle d'IA <code>${esc(h.ollama.model)}</code> n'est pas encore téléchargé : <button class="btn small" id="pull-model">Télécharger le modèle</button> <span class="tiny muted">(une seule fois, quelques Go)</span><div id="pull-progress"></div></li>`);
  if (!h.whisper.downloaded) items.push(`<li>Le modèle de transcription Whisper <code>${esc(h.whisper.model)}</code> sera téléchargé automatiquement au premier import (${h.whisper.model === "small" ? "≈ 500 Mo" : "quelques centaines de Mo"}). <button class="btn small" id="dl-whisper">Télécharger maintenant</button><div id="whisper-progress"></div></li>`);
  if (!items.length) return "";
  return `<div class="alert warn mt"><strong>Configuration nécessaire avant le premier import</strong><ul style="margin:8px 0 0 18px;padding:0;line-height:1.9">${items.join("")}</ul></div>`;
}

function bindSetupCard() {
  $$("[data-open]").forEach((b) => { b.onclick = () => openExternal(b.dataset.open); });
  const so = $("#start-ollama"); if (so) so.onclick = async () => { so.disabled = true; so.textContent = "Démarrage…"; const r = await api("/api/ollama/start", { method: "POST" }); toast(r.running ? "Ollama est lancé." : "Impossible de lancer Ollama automatiquement : ouvrez l'application Ollama.", r.running ? "ok" : "error"); router(); };
  const pm = $("#pull-model"); if (pm) pm.onclick = async () => { const name = state.health.ollama.model; const { task } = await api("/api/ollama/pull", { method: "POST", body: { name } }); pm.disabled = true; trackTask(task.id, $("#pull-progress"), () => { toast("Modèle d'IA prêt.", "ok"); router(); }); };
  const dw = $("#dl-whisper"); if (dw) dw.onclick = async () => { const { task } = await api("/api/whisper/download", { method: "POST", body: {} }); dw.disabled = true; trackTask(task.id, $("#whisper-progress"), () => { toast("Modèle Whisper prêt.", "ok"); router(); }); };
}

function trackTask(taskId, el, onDone) {
  const tick = async () => {
    try {
      const t = await api(`/api/tasks/${taskId}`);
      if (el) el.innerHTML = `<div class="progress mt" style="max-width:360px"><div style="width:${t.progress}%"></div></div><div class="tiny muted">${esc(t.message || "")}${t.error ? ` — ${esc(t.error)}` : ""}</div>`;
      if (t.status === "running") setTimeout(tick, 1000);
      else if (t.status === "done") onDone && onDone();
      else toast("Échec : " + (t.error || "inconnu"), "error");
    } catch (e) { toast(e.message, "error"); }
  };
  tick();
}

async function startImport(req, file) {
  try {
    let res;
    if (file) {
      const form = new FormData(); form.append("file", file);
      Object.entries(req).forEach(([k, v]) => { if (v !== null && v !== undefined) form.append(k, String(v)); });
      res = await api("/api/import/upload", { method: "POST", form });
    } else res = await api("/api/import", { method: "POST", body: req });
    state.job = res.job; state.importFile = null;
    if (location.hash !== "#/import") { location.hash = "#/import"; } else { renderJob(); pollJob(); }
  } catch (e) { toast("Import impossible : " + e.message, "error"); }
}

function pollJob() {
  clearInterval(state.jobTimer);
  state.jobTimer = setInterval(async () => {
    if (!state.job) { clearInterval(state.jobTimer); return; }
    try {
      const { job } = await api(`/api/import/${state.job.id}`);
      state.job = job; renderJob();
      if (job.status === "done") {
        clearInterval(state.jobTimer);
        state.draft = job.result.recipe; state.draftAnalysis = job.result.analysis;
        location.hash = "#/draft";
      } else if (job.status === "error") clearInterval(state.jobTimer);
    } catch (e) { clearInterval(state.jobTimer); }
  }, 800);
}

function renderJob() {
  const j = state.job, el = $("#progress"); if (!el || !j) return;
  const steps = [["fetch", "Récupération"], ["analyze", "Analyse locale"], ["llm", "Rédaction par l'IA"], ["finalize", "Finalisation"]];
  const order = steps.map((s) => s[0]); const cur = order.indexOf(j.step);
  el.innerHTML = `<div class="card mt">
    <div class="row between"><strong>${j.status === "error" ? "❌ Import interrompu" : j.status === "done" ? "✅ Terminé" : `<span class="spinner"></span> Import en cours…`}</strong><span class="muted small">${esc(j.url || "saisie manuelle")}</span></div>
    <ul class="steps-list">${steps.map(([k, label], i) => `<li class="${j.status === "done" || i < cur ? "done" : i === cur && j.status === "running" ? "active" : ""}">${i < cur || j.status === "done" ? "✓ " : ""}${label}</li>`).join("")}</ul>
    <div class="progress"><div style="width:${j.progress}%"></div></div>
    ${j.error ? `<div class="alert error mt"><strong>${esc(j.error)}</strong>${j.hint ? `<br>${esc(j.hint)}` : ""}<div class="row mt"><button class="btn small" id="go-manual-mode">Passer en saisie manuelle</button><a class="btn small" href="#/settings">Réglages</a></div></div>` : ""}
    <div class="log mt">${j.logs.map((l) => `${l.time}  ${esc(l.message)}`).join("\n")}</div></div>`;
  const gm = $("#go-manual-mode"); if (gm) gm.onclick = () => { state.importMode = "manual"; renderImport().then(() => { if (j.url && $("#m-url")) $("#m-url").value = j.url; }); };
}

/* ======================================================================= MENUS */
async function renderMenus(menuId) {
  const [facets, saved] = await Promise.all([api("/api/recipes/facets"), api("/api/menus")]);
  state.facets = facets; state.savedMenus = saved.menus;
  if (menuId && (!state.menu || state.menu.id !== menuId)) {
    const p = await api(`/api/menus/${menuId}`); state.menu = p.menu; state.menuRecipes = p.recipes; state.shopping = p.shopping_list; state.menuWarnings = []; state.menuDirty = false;
  }
  const mf = state.menuForm; if (!mf.week_start) mf.week_start = nextMonday();
  const cats = (state.health && state.health.categories) || Object.keys(facets.categories);
  view.innerHTML = `
  <div class="view-header"><div><h1>Menu de la semaine</h1><div class="muted">Tirage aléatoire sans doublon, en variant protéines et cuisines.</div></div></div>
  <div class="card">
    <div class="field-grid">
      <label class="field">Nombre de repas<input type="number" id="mf-count" min="1" max="21" value="${mf.count}"></label>
      <label class="field">Moments<select id="mf-moments"><option value="soir" ${mf.moments === "soir" ? "selected" : ""}>Dîners</option><option value="midi" ${mf.moments === "midi" ? "selected" : ""}>Déjeuners</option><option value="midi_soir" ${mf.moments === "midi_soir" ? "selected" : ""}>Midi et soir</option></select></label>
      <label class="field">Temps total max<select id="mf-time"><option value="">Peu importe</option>${[15, 20, 30, 45, 60, 90].map((t) => `<option value="${t}" ${String(mf.maxTime) === String(t) ? "selected" : ""}>≤ ${t} min</option>`).join("")}</select></label>
      <label class="field">Portions (pour la liste de courses)<input type="number" id="mf-servings" min="1" max="20" value="${mf.servings}" placeholder="celles des recettes"></label>
      <label class="field">Semaine du<input type="date" id="mf-week" value="${mf.week_start}"></label>
    </div>
    <div class="mt"><div class="small muted mb">Catégories (aucune = toutes)</div><div class="chips" id="mf-cats">${cats.map((c) => `<span class="chip ${mf.categories.includes(c) ? "active" : ""}" data-c="${esc(c)}">${catEmoji(c)} ${esc(c)} <span class="muted">${facets.categories[c] || 0}</span></span>`).join("")}</div></div>
    ${facets.tags.length ? `<div class="mt"><div class="small muted mb">Étiquettes exigées</div><div class="chips" id="mf-tags">${facets.tags.slice(0, 30).map((t) => `<span class="chip ${mf.tags.includes(t.tag) ? "active" : ""}" data-t="${esc(t.tag)}">#${esc(t.tag)} <span class="muted">${t.count}</span></span>`).join("")}</div></div>` : ""}
    <div class="row mt"><button class="btn primary" id="gen">🎲 Tirer un menu</button>${facets.total ? "" : `<span class="muted small">Importez d'abord quelques recettes.</span>`}</div>
  </div>
  <div id="menu-result"></div>
  <h2>Menus enregistrés</h2>
  <div class="card" id="saved">${state.savedMenus.length ? state.savedMenus.map((m) => `<div class="menu-list-item"><div><strong><a href="#/menus/${m.menu.id}">${esc(m.menu.name)}</a></strong><div class="small muted">${m.titles.filter(Boolean).slice(0, 5).map(esc).join(" · ")}${m.titles.length > 5 ? " …" : ""}</div></div><div class="row"><a class="btn small" href="#/menus/${m.menu.id}">Ouvrir</a><button class="btn small danger" data-del="${m.menu.id}">Supprimer</button></div></div>`).join("") : `<p class="muted">Aucun menu enregistré pour l'instant.</p>`}</div>`;

  const readForm = () => { mf.count = Number($("#mf-count").value) || 7; mf.moments = $("#mf-moments").value; mf.maxTime = $("#mf-time").value; mf.servings = $("#mf-servings").value; mf.week_start = $("#mf-week").value; };
  $$("#mf-cats .chip").forEach((c) => { c.onclick = () => { readForm(); const v = c.dataset.c; mf.categories = mf.categories.includes(v) ? mf.categories.filter((x) => x !== v) : [...mf.categories, v]; renderMenus(); }; });
  $$("#mf-tags .chip").forEach((c) => { c.onclick = () => { readForm(); const v = c.dataset.t; mf.tags = mf.tags.includes(v) ? mf.tags.filter((x) => x !== v) : [...mf.tags, v]; renderMenus(); }; });
  $("#gen").onclick = async () => {
    readForm();
    const body = { count: mf.count, moments: mf.moments, week_start: mf.week_start || null, servings: mf.servings ? Number(mf.servings) : null,
      filters: { categories: mf.categories, tags: mf.tags, max_total_time: mf.maxTime ? Number(mf.maxTime) : null } };
    try {
      const p = await api("/api/menus/generate", { method: "POST", body });
      state.menu = p.menu; state.menuRecipes = p.recipes; state.shopping = p.shopping_list; state.menuWarnings = p.warnings || []; state.menuDirty = true;
      if (location.hash !== "#/menus") location.hash = "#/menus"; else renderMenuResult();
    } catch (e) { toast(e.message, "error"); }
  };
  $$("[data-del]").forEach((b) => { b.onclick = async () => { if (await confirmDialog({ title: "Supprimer ce menu ?", text: "La liste de courses associée sera perdue.", ok: "Supprimer", danger: true })) { await api(`/api/menus/${b.dataset.del}`, { method: "DELETE" }); if (state.menu && state.menu.id === b.dataset.del) state.menu = null; renderMenus(); } }; });
  renderMenuResult();
}

function renderMenuResult() {
  const el = $("#menu-result"); if (!el) return;
  const m = state.menu; if (!m) { el.innerHTML = ""; return; }
  const isSaved = state.savedMenus.some((s) => s.menu.id === m.id) && !state.menuDirty;
  const depts = {}; state.shopping.forEach((it) => { (depts[it.department] = depts[it.department] || []).push(it); });
  el.innerHTML = `<div class="card mt">
    <div class="row between mb"><div><input type="text" id="menu-name" value="${esc(m.name)}" style="font-weight:700;font-size:18px;border-color:transparent;padding-left:0;max-width:420px"><div class="small muted">${m.week_start ? `Semaine du ${fmtDay(m.week_start)} · ` : ""}${m.slots.filter((s) => s.recipe_id).length} repas${m.servings ? ` · ${m.servings} portions` : ""}</div></div>
      <div class="row"><button class="btn" id="copy">📋 Copier menu + courses</button><button class="btn ${isSaved ? "" : "primary"}" id="save-menu">${isSaved ? "✓ Enregistré" : "💾 Enregistrer"}</button></div></div>
    ${state.menuWarnings.length ? `<div class="alert warn mb">${state.menuWarnings.map(esc).join("<br>")}</div>` : ""}
    <div class="menu-grid">${m.slots.map((s, i) => { const r = state.menuRecipes[s.recipe_id]; return `<div class="slot"><div class="day">${DAYS[s.day % 7]} ${esc(s.moment)}<button class="btn icon ghost small" data-reroll="${i}" title="Tirer une autre recette">🎲</button></div>
      ${r ? `<div class="thumb" ${thumbStyle(r)} data-open="${r.id}">${thumbUrl(r) ? "" : catEmoji(r.category)}</div><div class="body"><div class="title" data-open="${r.id}">${esc(r.title)}</div><div class="small muted">${r.total_time_min != null ? `⏱ ${fmtTime(r.total_time_min)} · ` : ""}${r.main_protein && r.main_protein !== "aucune" ? esc(r.main_protein) : ""}${r.cuisine ? ` · ${esc(r.cuisine)}` : ""}</div></div>` : `<div class="empty-slot">Aucune recette disponible</div>`}</div>`; }).join("")}</div>
    <h2>🛒 Liste de courses</h2>
    ${state.shopping.length ? `<div class="shopping">${Object.entries(depts).map(([d, items]) => `<div class="dept"><h4>${esc(d)}</h4>${items.map((it) => `<label class="${it.checked ? "checked" : ""}"><input type="checkbox" data-key="${esc(it.key)}" ${it.checked ? "checked" : ""}><span>${esc(it.label)}${it.estimated ? ` <span class="badge est">estimé</span>` : ""}<span class="tiny muted"> — ${it.recipes.map(esc).join(", ")}</span></span></label>`).join("")}</div>`).join("")}</div>` : `<p class="muted">Aucun ingrédient.</p>`}
  </div>`;
  $("#menu-name").onchange = (ev) => { m.name = ev.target.value; state.menuDirty = true; };
  $$("[data-open]").forEach((x) => { x.onclick = () => { location.hash = `#/recipe/${x.dataset.open}`; }; });
  $$("[data-reroll]").forEach((b) => { b.onclick = async () => { try { const p = await api("/api/menus/reroll", { method: "POST", body: { menu: m, slot_index: Number(b.dataset.reroll) } }); state.menu = p.menu; state.menuRecipes = p.recipes; state.shopping = p.shopping_list; state.menuDirty = true; renderMenuResult(); } catch (e) { toast(e.message, "error"); } }; });
  $("#save-menu").onclick = async () => { try { m.name = $("#menu-name").value; const p = await api(`/api/menus/${m.id}`, { method: "PUT", body: { menu: m } }); state.menu = p.menu; state.menuDirty = false; toast("Menu enregistré.", "ok"); refreshHealth(); renderMenus(); } catch (e) { toast(e.message, "error"); } };
  $("#copy").onclick = async () => { try { const txt = await api("/api/menus/text", { method: "POST", body: { menu: m } }); await navigator.clipboard.writeText(txt); toast("Menu et liste de courses copiés.", "ok"); } catch (e) { toast("Copie impossible : " + e.message, "error"); } };
  $$(".shopping input").forEach((cb) => { cb.onchange = async () => { const k = cb.dataset.key; m.checked_items = cb.checked ? [...new Set([...m.checked_items, k])] : m.checked_items.filter((x) => x !== k); cb.closest("label").classList.toggle("checked", cb.checked); if (state.savedMenus.some((s) => s.menu.id === m.id)) { try { await api(`/api/menus/${m.id}`, { method: "PUT", body: { menu: m } }); } catch (_) { /* ignore */ } } }; });
}

/* ======================================================================= RÉGLAGES */
async function renderSettings() {
  const [s, h] = await Promise.all([api("/api/settings"), api("/api/health")]);
  state.settings = s.settings; state.health = h;
  const st = s.settings;
  const installed = h.ollama.models || [];
  const modelOptions = [...s.recommended_llm_models.map((m) => ({ name: m.name, label: m.label })), ...installed.filter((n) => !s.recommended_llm_models.some((m) => m.name === n || m.name + ":latest" === n)).map((n) => ({ name: n, label: n + " (installé)" }))];
  if (!modelOptions.some((m) => m.name === st.ollama_model)) modelOptions.push({ name: st.ollama_model, label: st.ollama_model });
  const modelInstalled = (name) => installed.includes(name) || installed.includes(name + ":latest");
  view.innerHTML = `
  <div class="settings">
    <h1>Réglages</h1>
    <div class="card">
      <h2 style="margin-top:0">🧠 Intelligence artificielle locale (Ollama)</h2>
      <div class="status-line"><span class="dot ${h.ollama.running ? "ok" : "bad"}"></span>${h.ollama.running ? `Ollama ${esc(h.ollama.version || "")} est lancé` : h.ollama.app_installed ? "Ollama est installé mais pas lancé" : "Ollama n'est pas installé"}
        ${!h.ollama.running && h.ollama.app_installed ? `<button class="btn small" id="start-ollama">Lancer</button>` : ""}${!h.ollama.app_installed ? `<button class="btn small" data-open="https://ollama.com/download">Télécharger Ollama (gratuit) ↗</button>` : ""}</div>
      <div class="field-grid mt">
        <label class="field">Modèle utilisé pour rédiger les recettes<select id="s-model">${modelOptions.map((m) => `<option value="${esc(m.name)}" ${st.ollama_model === m.name ? "selected" : ""}>${esc(m.label)}${modelInstalled(m.name) ? " ✓" : ""}</option>`).join("")}</select></label>
        <label class="field">Adresse d'Ollama<input type="text" id="s-url" value="${esc(st.ollama_url)}"></label>
      </div>
      <div class="row mt"><span class="status-line"><span class="dot ${h.ollama.has_model ? "ok" : "warn"}"></span>${h.ollama.has_model ? "Modèle installé" : "Modèle à télécharger"}</span>${!h.ollama.has_model && h.ollama.running ? `<button class="btn small primary" id="pull-model">Télécharger ${esc(st.ollama_model)}</button>` : ""}<div id="pull-progress" class="grow"></div></div>
      <p class="tiny muted mt">Conseil : Qwen 2.5 7B donne les meilleurs résultats en français si votre Mac a 16 Go de RAM ou plus. Avec 8 Go, choisissez un modèle 3B ou 4B.</p>
    </div>
    <div class="card">
      <h2 style="margin-top:0">🎙 Transcription (Whisper) et lecture d'écran (Vision)</h2>
      <div class="field-grid">
        <label class="field">Modèle Whisper<select id="s-whisper">${Object.entries(s.whisper_models).map(([k, label]) => `<option value="${k}" ${st.whisper_model === k ? "selected" : ""}>${k} — ${esc(label)}</option>`).join("")}</select></label>
        <label class="field">Images analysées par vidéo (OCR)<input type="number" id="s-frames" min="4" max="40" value="${st.max_frames}"></label>
      </div>
      <div class="row mt"><span class="status-line"><span class="dot ${h.whisper.downloaded ? "ok" : "warn"}"></span>${h.whisper.downloaded ? "Modèle Whisper téléchargé" : "Modèle Whisper non téléchargé (téléchargement automatique au premier import)"}</span>${!h.whisper.downloaded ? `<button class="btn small" id="dl-whisper">Télécharger maintenant</button>` : ""}<div id="whisper-progress" class="grow"></div></div>
      <div class="row mt" style="gap:18px">
        <label class="check"><input type="checkbox" id="s-transcribe" ${st.transcribe_enabled ? "checked" : ""}> Transcrire l'audio</label>
        <label class="check"><input type="checkbox" id="s-ocr" ${st.ocr_enabled ? "checked" : ""}> Lire le texte à l'écran</label>
        <label class="check"><input type="checkbox" id="s-always" ${st.always_analyze_video ? "checked" : ""}> Toujours analyser la vidéo, même si la description contient la recette</label>
      </div>
    </div>
    <div class="card">
      <h2 style="margin-top:0">📷 Instagram</h2>
      <p class="small muted">La récupération fonctionne sans compte pour les publications publiques. Si Instagram bloque (« connexion requise », limitation), l'application peut réutiliser les cookies d'un navigateur où vous êtes connecté. Firefox fonctionne sans mot de passe ; Chrome demandera l'accès au trousseau ; Safari nécessite l'accès complet au disque.</p>
      <div class="field-grid">
        <label class="field">Navigateur pour les cookies<select id="s-browser">${s.cookie_browsers.map((b) => `<option value="${b}" ${st.cookies_browser === b ? "selected" : ""}>${b || "Aucun (anonyme)"}</option>`).join("")}</select></label>
        <label class="field">Ou fichier cookies.txt (format Netscape)<input type="text" id="s-cookiefile" value="${esc(st.cookies_file)}" placeholder="/Users/moi/cookies.txt"></label>
      </div>
    </div>
    <div class="card">
      <h2 style="margin-top:0">🗂 Données</h2>
      <p class="small">Vos recettes sont stockées uniquement sur ce Mac : <code>${esc(s.data_dir)}</code></p>
      <div class="row"><button class="btn small" data-reveal="data">Afficher dans le Finder</button><button class="btn small" data-reveal="logs">Journaux</button><button class="btn small" id="export-all">Exporter toutes les recettes</button><button class="btn small" id="import-json">Importer un fichier JSON</button></div>
      <div class="field-grid mt">
        <label class="field">Thème<select id="s-theme"><option value="auto" ${st.ui_theme === "auto" ? "selected" : ""}>Automatique</option><option value="light" ${st.ui_theme === "light" ? "selected" : ""}>Clair</option><option value="dark" ${st.ui_theme === "dark" ? "selected" : ""}>Sombre</option></select></label>
      </div>
    </div>
    <p class="tiny muted">Nourriture ${esc(h.version)} — 100 % local et gratuit : yt-dlp, faster-whisper, Apple Vision, Ollama. Aucune donnée n'est envoyée sur un serveur.</p>
  </div>`;

  const save = async (patch) => { try { const r = await api("/api/settings", { method: "PUT", body: patch }); state.settings = r.settings; toast("Réglages enregistrés."); refreshHealth(); } catch (e) { toast(e.message, "error"); } };
  $("#s-model").onchange = async (ev) => { await save({ ollama_model: ev.target.value }); renderSettings(); };
  $("#s-url").onchange = (ev) => save({ ollama_url: ev.target.value.trim() || "http://127.0.0.1:11434" });
  $("#s-whisper").onchange = async (ev) => { await save({ whisper_model: ev.target.value }); renderSettings(); };
  $("#s-frames").onchange = (ev) => save({ max_frames: Math.max(4, Math.min(40, Number(ev.target.value) || 14)) });
  $("#s-transcribe").onchange = (ev) => save({ transcribe_enabled: ev.target.checked });
  $("#s-ocr").onchange = (ev) => save({ ocr_enabled: ev.target.checked });
  $("#s-always").onchange = (ev) => save({ always_analyze_video: ev.target.checked });
  $("#s-browser").onchange = (ev) => save({ cookies_browser: ev.target.value });
  $("#s-cookiefile").onchange = (ev) => save({ cookies_file: ev.target.value.trim() });
  $("#s-theme").onchange = (ev) => { applyTheme(ev.target.value); save({ ui_theme: ev.target.value }); };
  $$("[data-reveal]").forEach((b) => { b.onclick = () => api("/api/system/reveal", { method: "POST", body: { what: b.dataset.reveal } }); });
  $$("[data-open]").forEach((b) => { b.onclick = () => openExternal(b.dataset.open); });
  $("#export-all").onclick = () => exportAll();
  $("#import-json").onclick = () => importJsonDialog();
  const so = $("#start-ollama"); if (so) so.onclick = async () => { so.disabled = true; const r = await api("/api/ollama/start", { method: "POST" }); toast(r.running ? "Ollama est lancé." : "Ouvrez l'application Ollama manuellement.", r.running ? "ok" : "error"); renderSettings(); };
  const pm = $("#pull-model"); if (pm) pm.onclick = async () => { const { task } = await api("/api/ollama/pull", { method: "POST", body: { name: st.ollama_model } }); pm.disabled = true; trackTask(task.id, $("#pull-progress"), () => renderSettings()); };
  const dw = $("#dl-whisper"); if (dw) dw.onclick = async () => { const { task } = await api("/api/whisper/download", { method: "POST", body: { name: st.whisper_model } }); dw.disabled = true; trackTask(task.id, $("#whisper-progress"), () => renderSettings()); };
  if (h.ollama.pulling) trackTask(h.ollama.pulling.id, $("#pull-progress"), () => renderSettings());
  if (h.whisper.downloading) trackTask(h.whisper.downloading.id, $("#whisper-progress"), () => renderSettings());
}

/* ----------------------------------------------------------------------- démarrage */
(async function init() {
  try { const s = await api("/api/settings"); state.settings = s.settings; applyTheme(s.settings.ui_theme); } catch (_) { /* ignore */ }
  await refreshHealth();
  setInterval(refreshHealth, 20000);
  router();
})();
