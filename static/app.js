/* Morph — website script. Plain JavaScript, no build step. */
(() => {
  "use strict";

  // ---------------------------------------------------------------- tiny DOM helpers
  const $ = (s, el = document) => el.querySelector(s);
  const $$ = (s, el = document) => [...el.querySelectorAll(s)];
  function h(tag, attrs = {}, ...kids) {
    const el = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs)) {
      if (v == null) continue;
      if (k.startsWith("aria-")) { el.setAttribute(k, String(v)); continue; }
      if (v === false) continue;
      if (k === "class") el.className = v;
      else if (k === "style") el.style.cssText = v;
      else if (k === "html") el.innerHTML = v;
      else if (k.startsWith("on")) el.addEventListener(k.slice(2), v);
      else el.setAttribute(k, v === true ? "" : v);
    }
    for (const kid of kids.flat()) if (kid != null && kid !== false) el.append(kid);
    return el;
  }
  const ICON = {
    chev: '<svg class="chev" viewBox="0 0 24 24"><path d="m7 10 5 5 5-5"/></svg>',
    tune: '<svg viewBox="0 0 24 24"><path d="M4 7h9M17 7h3M4 17h3M11 17h9"/><circle cx="15" cy="7" r="2.2"/><circle cx="9" cy="17" r="2.2"/></svg>',
    x: '<svg viewBox="0 0 24 24"><path d="M6 6l12 12M18 6 6 18"/></svg>',
    stop: '<svg viewBox="0 0 24 24"><rect x="7" y="7" width="10" height="10" rx="2"/></svg>',
    save: '<svg viewBox="0 0 24 24"><path d="M12 4v11M7 10.5l5 5 5-5M5 19.5h14"/></svg>',
    retry: '<svg viewBox="0 0 24 24"><path d="M4 12a8 8 0 0 1 14-5.3L20 9M20 4v5h-5M20 12a8 8 0 0 1-14 5.3L4 15M4 20v-5h5"/></svg>',
    up: '<svg viewBox="0 0 24 24"><path d="m7 14 5-5 5 5"/></svg>',
    down: '<svg viewBox="0 0 24 24"><path d="m7 10 5 5 5-5"/></svg>',
    merge: '<svg viewBox="0 0 24 24"><path d="M6 3v4a6 6 0 0 0 6 6M18 3v4a6 6 0 0 1-6 6v8M9 18l3 3 3-3"/></svg>',
    split: '<svg viewBox="0 0 24 24"><rect x="4" y="3" width="7" height="9" rx="1.5"/><rect x="13" y="12" width="7" height="9" rx="1.5"/><path d="M14 4h5v5M10 20H5v-5"/></svg>',
    compress: '<svg viewBox="0 0 24 24"><path d="M9 4v5H4M15 4v5h5M9 20v-5H4M15 20v-5h5"/></svg>',
    rotate: '<svg viewBox="0 0 24 24"><path d="M20 12a8 8 0 1 1-2.3-5.6M20 4v5h-5"/></svg>',
    images: '<svg viewBox="0 0 24 24"><rect x="3" y="5" width="14" height="12" rx="2"/><path d="m3 14 4-4 4 4 2-2 4 4M7 21h12a2 2 0 0 0 2-2V8"/></svg>',
    zip: '<svg viewBox="0 0 24 24"><path d="M6 3h8l4 4v14H6zM11 3v2m0 2v2m0 2v2m-1 2h2v3h-2z"/></svg>',
  };
  const TOOL_LOOK = {
    "merge-pdf": ["merge", "--c-pdf"], "split-pdf": ["split", "--c-ebook"], "compress-pdf": ["compress", "--c-subtitle"],
    "rotate-pdf": ["rotate", "--c-markup"], "images-to-pdf": ["images", "--c-image"], "zip": ["zip", "--c-archive"],
  };
  const DEFAULT_TARGET = {
    video: ["mp4", "mp3"], audio: ["mp3", "wav"], image: ["jpg", "png"], vector: ["png"], document: ["pdf", "docx"],
    markup: ["pdf", "docx", "html"], spreadsheet: ["xlsx", "csv"], presentation: ["pdf", "pptx"], pdf: ["docx", "png"],
    ebook: ["epub", "pdf"], data: ["json", "yaml"], archive: ["zip", "7z"], font: ["woff2", "woff", "ttf"], subtitle: ["srt", "vtt"],
  };
  const isMac = /Mac|iPhone|iPad/.test(navigator.platform || navigator.userAgent);

  const state = { cat: null, items: [], from: null, to: null, preset: {}, common: [], polling: false, uploads: 0, page: "convert" };

  // ---------------------------------------------------------------- format helpers
  const fmt = (k) => state.cat.formats[k];
  const catOf = (k) => (fmt(k) ? fmt(k).category : "archive");
  const hue = (k) => `var(--c-${catOf(k)})`;
  const catLabel = (id) => (state.cat.categories.find((c) => c.id === id) || {}).label || id;
  const label = (k) => (fmt(k) ? fmt(k).label : k.toUpperCase());
  const badge = (k) => h("span", { class: "badge", style: `--c: ${hue(k)}`, title: fmt(k) ? fmt(k).name : k }, label(k));
  const targetsOf = (src) => (state.cat.routes[src] || []).map(([d]) => d);
  // Grouped by family (in the site's family order), then A to Z: much easier to scan
  function byFamily(keys, first) {
    const order = Object.fromEntries(state.cat.categories.map((c, i) => [c.id, i]));
    const lead = first ? catOf(first) : null;
    return [...keys].sort((a, b) => ((catOf(b) === lead) - (catOf(a) === lead)) ||
      (order[catOf(a)] - order[catOf(b)]) || label(a).localeCompare(label(b)));
  }
  const allSources = () => Object.keys(state.cat.routes);
  function allTargets() {
    const s = new Set();
    for (const list of Object.values(state.cat.routes)) for (const [d] of list) s.add(d);
    return [...s];
  }
  function routeOptions(src, dst) {
    const r = (state.cat.routes[src] || []).find(([d]) => d === dst);
    return r ? state.cat.option_sets[r[1]] : [];
  }
  function detect(name) {
    const low = name.toLowerCase();
    for (const c of ["tar.gz", "tar.bz2", "tar.xz"]) if (low.endsWith("." + c)) return state.cat.aliases[c] || null;
    const i = low.lastIndexOf(".");
    return i < 0 ? null : state.cat.aliases[low.slice(i + 1)] || null;
  }
  function bytes(n) {
    if (n == null) return "";
    const u = ["B", "KB", "MB", "GB"];
    let i = 0;
    while (n >= 1024 && i < u.length - 1) { n /= 1024; i++; }
    return (i === 0 ? n : n.toFixed(n < 10 ? 1 : 0)) + " " + u[i];
  }
  function clock(s) {
    if (!s && s !== 0) return "";
    s = Math.round(s);
    const hh = Math.floor(s / 3600), mm = Math.floor((s % 3600) / 60), ss = s % 60;
    return (hh ? hh + ":" + String(mm).padStart(2, "0") : mm) + ":" + String(ss).padStart(2, "0");
  }
  function toast(msg, kind = "error") {
    const t = h("div", { class: `toast ${kind}`, role: kind === "error" ? "alert" : "status" }, msg);
    $("#toasts").append(t);
    setTimeout(() => { t.style.transition = "opacity .3s"; t.style.opacity = "0"; setTimeout(() => t.remove(), 300); }, kind === "error" ? 6500 : 3500);
  }
  async function api(path, opts = {}) {
    const r = await fetch(path, opts);
    let body = null;
    try { body = await r.json(); } catch (e) { /* not JSON */ }
    if (!r.ok) throw new Error((body && body.error) || `Request failed (${r.status})`);
    return body;
  }
  function download(href) {
    const a = h("a", { href, download: "" });
    document.body.append(a);
    a.click();
    a.remove();
  }
  const pairUrl = (a, b) => `/convert/${a}-to-${b}`;

  // ---------------------------------------------------------------- router
  function parsePath(path) {
    if (path.startsWith("/youtube")) return { page: "youtube" };
    if (path.startsWith("/pdf-tools")) return { page: "tools" };
    if (path.startsWith("/formats")) return { page: "formats" };
    if (path.startsWith("/developers")) return { page: "developers" };
    const m = path.match(/^\/convert\/([a-z0-9]+)(?:-to-([a-z0-9]+))?\/?$/i);
    if (m) return { page: "convert", from: m[1].toLowerCase(), to: (m[2] || "").toLowerCase() || null };
    return { page: "convert" };
  }
  const TITLES = {
    youtube: "YouTube to MP3 and MP4 | Morph", tools: "PDF tools: merge, split, compress, rotate | Morph",
    formats: "Supported formats | Morph", developers: "Developer API | Morph",
  };
  function go(path, push = true) {
    const r = parsePath(path);
    if (push && path !== location.pathname) history.pushState(null, "", path);
    state.page = r.page;
    for (const sec of $$(".page")) sec.hidden = sec.dataset.page !== r.page;
    $$(".nav a").forEach((a) => a.dataset.nav === r.page ? a.setAttribute("aria-current", "page") : a.removeAttribute("aria-current"));
    closePicker(false);
    if (r.page === "convert") {
      const from = r.from && fmt(r.from) ? r.from : null;
      const to = r.to && fmt(r.to) && (!from || targetsOf(from).includes(r.to)) ? r.to : null;
      setPair(from, to, false);
    } else {
      document.title = TITLES[r.page];
    }
    if (r.page === "formats" && location.hash) setTimeout(() => { const t = document.getElementById(location.hash.slice(1)); t && t.scrollIntoView(); }, 0);
    else if (push) scrollTo(0, 0);
  }
  document.addEventListener("click", (e) => {
    const a = e.target.closest("a[data-link], a[href^='/convert/'], a[href^='/formats']");
    if (!a || e.metaKey || e.ctrlKey || e.shiftKey || a.target === "_blank") return;
    const url = new URL(a.href, location.href);
    if (url.origin !== location.origin) return;
    e.preventDefault();
    go(url.pathname + url.hash);
    if (url.hash) history.replaceState(null, "", url.pathname + url.hash);
  });
  addEventListener("popstate", () => go(location.pathname, false));

  // ---------------------------------------------------------------- picker
  const pk = { el: $("#picker"), cats: $("#pickerCats"), body: $("#pickerBody"), search: $("#pickerSearch"), cat: null };

  function openPicker(anchor, opts) {
    Object.assign(pk, { anchor, choices: opts.choices.filter((k) => fmt(k)), current: opts.current, src: opts.src, any: opts.any, onPick: opts.onPick });
    pk.search.value = "";
    const fams = famsOf(pk.choices);
    pk.cat = pk.current && fams.includes(catOf(pk.current)) ? catOf(pk.current)
      : (pk.src && fams.includes(catOf(pk.src)) ? catOf(pk.src) : fams[0]);
    renderPicker();
    pk.el.hidden = false;
    placePicker();
    anchor.setAttribute("aria-expanded", "true");
    requestAnimationFrame(() => pk.search.focus({ preventScroll: true }));
  }
  function closePicker(focusBack = true) {
    if (pk.el.hidden) return;
    pk.el.hidden = true;
    if (pk.anchor) {
      pk.anchor.setAttribute("aria-expanded", "false");
      if (focusBack) pk.anchor.focus({ preventScroll: true });
    }
  }
  function placePicker() {
    if (innerWidth <= 820) return; // bottom sheet via CSS
    const r = pk.anchor.getBoundingClientRect(), p = pk.el;
    const w = p.offsetWidth, ph = p.offsetHeight;
    const left = Math.min(Math.max(12, r.left), innerWidth - w - 12);
    let top = r.bottom + 6;
    if (top + ph > innerHeight - 12 && r.top - ph - 6 > 12) top = r.top - ph - 6;
    p.style.left = left + "px";
    p.style.top = Math.max(12, Math.min(top, innerHeight - ph - 12)) + "px";
  }
  function famsOf(keys) {
    const set = new Set(keys.map(catOf));
    return state.cat.categories.map((c) => c.id).filter((c) => set.has(c));
  }
  function matches(k, q) {
    if (!q) return true;
    const f = fmt(k);
    const hay = `${k} ${f.ext} ${f.label} ${f.name} ${catLabel(f.category)}`.toLowerCase();
    return q.split(/\s+/).every((w) => hay.includes(w.replace(/^\./, "")));
  }
  function fmtOption(k) {
    return h("button", {
      class: "fmt-opt" + (k === pk.src ? " same" : ""), type: "button", role: "radio", "aria-checked": k === pk.current,
      style: `--c: ${hue(k)}`, "data-k": k, title: k === pk.src ? "Same format: resize, trim or shrink" : fmt(k).name,
      onclick: () => choose(k),
    }, h("b", {}, label(k)), h("span", {}, fmt(k).name));
  }
  function renderPicker() {
    const q = pk.search.value.trim().toLowerCase();
    const fams = famsOf(pk.choices);
    pk.cats.textContent = "";
    for (const c of fams) {
      pk.cats.append(h("button", { type: "button", role: "tab", "aria-selected": !q && c === pk.cat, style: `--c: var(--c-${c})`,
        onclick: () => { pk.search.value = ""; pk.cat = c; renderPicker(); } }, h("i"), catLabel(c)));
    }
    pk.body.textContent = "";
    if (pk.any) pk.body.append(h("button", { class: "any-opt", type: "button", onclick: () => choose(null) }, pk.any));
    if (q) {
      let any = false;
      for (const c of fams) {
        const ks = pk.choices.filter((k) => catOf(k) === c && matches(k, q));
        if (!ks.length) continue;
        any = true;
        pk.body.append(h("div", { class: "picker-group-title", style: `--c: var(--c-${c})` }, h("i"), catLabel(c)),
          h("div", { class: "picker-grid" }, ks.map(fmtOption)));
      }
      if (!any) pk.body.append(h("p", { class: "picker-empty" }, `No format matches “${q}”.`));
    } else {
      pk.body.append(h("div", { class: "picker-grid", role: "radiogroup", "aria-label": catLabel(pk.cat) },
        pk.choices.filter((k) => catOf(k) === pk.cat).map(fmtOption)));
    }
  }
  function choose(k) {
    const cb = pk.onPick;
    closePicker();
    cb && cb(k);
  }
  pk.search.addEventListener("input", renderPicker);
  pk.search.addEventListener("keydown", (e) => {
    if (e.key === "Enter") { e.preventDefault(); const f = $(".fmt-opt", pk.body); if (f) choose(f.dataset.k); }
    if (e.key === "ArrowDown") { e.preventDefault(); const f = $(".fmt-opt", pk.body); f && f.focus(); }
  });
  pk.body.addEventListener("keydown", (e) => {
    const opts = $$(".fmt-opt", pk.body), i = opts.indexOf(document.activeElement);
    const step = { ArrowRight: 1, ArrowDown: 1, ArrowLeft: -1, ArrowUp: -1 }[e.key];
    if (i < 0 || !step) return;
    e.preventDefault();
    if (i + step < 0) pk.search.focus(); else if (opts[i + step]) opts[i + step].focus();
  });
  $("#pickerClose").addEventListener("click", () => closePicker());
  document.addEventListener("keydown", (e) => { if (e.key === "Escape") closePicker(); });
  document.addEventListener("pointerdown", (e) => {
    if (!pk.el.hidden && !pk.el.contains(e.target) && !(pk.anchor && pk.anchor.contains(e.target))) closePicker(false);
  });
  addEventListener("resize", () => !pk.el.hidden && placePicker());
  addEventListener("scroll", () => !pk.el.hidden && placePicker(), { passive: true });

  function selectButton(btn, k, emptyText) {
    btn.innerHTML = "";
    if (k) btn.append(badge(k), h("span", {}, fmt(k).name.split(" (")[0]));
    else btn.append(h("span", { class: "placeholder" }, emptyText));
    btn.insertAdjacentHTML("beforeend", ICON.chev);
  }

  // ---------------------------------------------------------------- option controls
  function renderOptions(grid, ids, specs, values, onChange) {
    grid.textContent = "";
    const ordered = [...ids].sort((a, b) => ((specs[a] || {}).type === "toggle") - ((specs[b] || {}).type === "toggle"));
    for (const id of ordered) {
      const s = specs[id];
      if (!s) continue;
      const val = values[id] ?? s.default;
      const set = (v) => { values[id] = v; onChange && onChange(id, v); };
      const lid = `l-${grid.dataset.uid}-${id}`;
      const lab = h("span", { class: "field-label", id: lid }, s.label);
      let control;
      const short = s.type === "select" && s.choices.length <= 4 && s.choices.reduce((n, c) => n + c[1].length, 0) <= 26;
      if (short) {
        control = h("div", { class: "seg", role: "group", "aria-labelledby": lid },
          s.choices.map(([v, l]) => h("button", { type: "button", "aria-pressed": String(val) === v,
            onclick: (e) => { $$("button", e.currentTarget.parentNode).forEach((b) => b.setAttribute("aria-pressed", b === e.currentTarget)); set(v); } }, l)));
      } else if (s.type === "select") {
        control = h("select", { class: "input", "aria-labelledby": lid, onchange: (e) => set(e.target.value) },
          s.choices.map(([v, l]) => h("option", { value: v, selected: String(val) === v }, l)));
      } else if (s.type === "toggle") {
        grid.append(h("div", { class: "field", style: "justify-content:flex-end" },
          h("label", { class: "switch" }, h("input", { type: "checkbox", checked: !!val, onchange: (e) => set(e.target.checked) }),
            h("span", { class: "track" }), s.label)));
        continue;
      } else if (s.type === "range") {
        const out = h("output", {}, `${val}${s.unit || ""}`);
        control = h("div", { class: "range" }, h("input", { type: "range", min: s.min, max: s.max, step: s.step, value: val, "aria-labelledby": lid,
          oninput: (e) => { out.textContent = e.target.value + (s.unit || ""); set(Number(e.target.value)); } }), out);
      } else if (s.type === "color") {
        control = h("input", { type: "color", value: val, "aria-labelledby": lid, oninput: (e) => set(e.target.value) });
      } else {
        const input = h("input", { class: "input", type: s.type === "number" ? "number" : "text", inputmode: s.type === "time" ? "decimal" : null,
          min: s.min, max: s.max, placeholder: s.placeholder || "", value: val ?? "", "aria-labelledby": lid,
          oninput: (e) => {
            const v = e.target.value;
            e.target.classList.toggle("bad", s.type === "time" && !!v && !/^\d+(:\d{1,2}){0,2}(\.\d+)?$/.test(v.trim()));
            set(v);
          } });
        control = s.unit ? h("div", { class: "unit" }, input, h("em", {}, s.unit)) : input;
      }
      grid.append(h("div", { class: "field" }, lab, control, s.hint ? h("p", { class: "hint" }, s.hint) : null));
    }
  }
  function changed(ids, values) {
    return ids.some((id) => { const s = state.cat.options[id]; return s && id in values && String(values[id]) !== String(s.default ?? ""); });
  }

  // ---------------------------------------------------------------- convert page: pair selectors
  function setPair(from, to, push = true) {
    state.from = from;
    state.to = to;
    state.preset = {};
    selectButton($("#fromSel"), from, "Any format");
    selectButton($("#toSel"), to, "Choose format");
    $("#pairReset").hidden = !from && !to;
    const input = $("#fileInput");
    if (from) {
      const exts = Object.entries(state.cat.aliases).filter(([, k]) => k === from).map(([e]) => "." + e);
      input.setAttribute("accept", exts.join(","));
    } else input.removeAttribute("accept");

    const title = $("#convertTitle"), sub = $("#convertSub");
    if (from && to) {
      title.textContent = `${label(from)} to ${label(to)} converter`;
      sub.textContent = `Convert ${fmt(from).name} files to ${fmt(to).name}. Free, with no sign-up.`;
      document.title = `${label(from)} to ${label(to)} converter | Morph`;
    } else if (from) {
      title.textContent = `${label(from)} converter`;
      sub.textContent = `Convert ${fmt(from).name} files to ${targetsOf(from).length} other formats.`;
      document.title = `${label(from)} converter | Morph`;
    } else {
      title.textContent = "Convert any file";
      sub.textContent = "Video, audio, images, documents, e-books, spreadsheets and more. Free, with no sign-up.";
      document.title = "Morph: free online file converter";
    }
    if (push) {
      const path = from && to ? pairUrl(from, to) : from ? `/convert/${from}` : "/";
      if (path !== location.pathname) history.pushState(null, "", path);
    }
    renderPreset();
    renderAbout();
    // files already in the list follow a new target if they can
    if (to) for (const it of state.items) if (it.state === "ready" && it.src && targetsOf(it.src).includes(to)) it.dst = to;
    renderQueue();
  }
  $("#fromSel").addEventListener("click", (e) => openPicker(e.currentTarget, {
    choices: state.to ? allSources().filter((s) => targetsOf(s).includes(state.to)) : allSources(),
    current: state.from, any: "Any format", onPick: (k) => setPair(k, state.to && (!k || targetsOf(k).includes(state.to)) ? state.to : null),
  }));
  $("#toSel").addEventListener("click", (e) => openPicker(e.currentTarget, {
    choices: state.from ? targetsOf(state.from) : allTargets(), current: state.to, src: state.from,
    onPick: (k) => setPair(state.from, k),
  }));
  $("#pairReset").addEventListener("click", () => setPair(null, null));

  function renderPreset() {
    const ids = state.from && state.to ? routeOptions(state.from, state.to) : [];
    $("#preset").hidden = !ids.length;
    if (!ids.length) return;
    $("#presetLabel").textContent = `${label(state.to)} options`;
    renderOptions($("#presetGrid"), ids, state.cat.options, state.preset, () =>
      $("#presetToggle").classList.toggle("changed", changed(ids, state.preset)));
  }
  $("#presetToggle").addEventListener("click", (e) => {
    const d = $("#presetDrawer"), open = !d.classList.contains("open");
    d.classList.toggle("open", open);
    e.currentTarget.setAttribute("aria-expanded", open);
  });

  function renderAbout() {
    const box = $("#aboutPair");
    box.textContent = "";
    box.hidden = !state.from && !state.to;
    for (const k of [state.from, state.to].filter(Boolean)) {
      const isFrom = k === state.from;
      const others = byFamily(isFrom ? targetsOf(k).filter((d) => d !== k && d !== state.to)
        : allSources().filter((s) => s !== k && s !== state.from && targetsOf(s).includes(k)), k).slice(0, 14);
      box.append(h("div", {},
        h("h3", {}, badge(k), " ", fmt(k).name),
        h("p", {}, `${catLabel(catOf(k))} format, saved with the .${fmt(k).ext} extension.`),
        others.length ? h("p", {}, isFrom ? `Convert ${label(k)} to:` : `Convert to ${label(k)} from:`) : null,
        h("div", { class: "more" }, others.map((o) => h("a", { href: isFrom ? pairUrl(k, o) : pairUrl(o, k) }, badge(o))))));
    }
  }

  // ---------------------------------------------------------------- convert page: queue
  let uid = 0;
  function addFiles(list) {
    const files = [...list];
    if (!files.length) return;
    const max = state.cat.max_upload_mb * 1024 * 1024;
    const unknown = [];
    for (const file of files) {
      if (file.size > max) { toast(`${file.name} is over the ${state.cat.max_upload_mb} MB limit.`); continue; }
      const src = detect(file.name);
      const it = { id: ++uid, file, name: file.name, size: file.size, src, dst: null, opts: {}, state: "ready", progress: 0 };
      if (!src || !targetsOf(src).length) { it.state = "unsupported"; unknown.push(file.name); }
      else if (state.to && targetsOf(src).includes(state.to)) {
        it.dst = state.to;
        if (!state.from || state.from === src) it.opts = { ...state.preset };
      } else {
        const t = targetsOf(src);
        it.dst = (DEFAULT_TARGET[catOf(src)] || []).find((k) => k !== src && t.includes(k)) || null;
      }
      state.items.push(it);
    }
    if (unknown.length) toast(unknown.length === 1 ? `${unknown[0]} can't be converted yet.` : `${unknown.length} files can't be converted yet.`);
    renderQueue();
  }

  function renderQueue() {
    const has = state.items.length > 0;
    $("#queue").hidden = !has;
    $("#converter").classList.toggle("has-files", has);
    const rows = $("#rows");
    const keep = new Set(state.items.map((i) => "r" + i.id));
    $$(".row", rows).forEach((r) => { if (!keep.has(r.id)) r.remove(); });
    for (const it of state.items) {
      let row = document.getElementById("r" + it.id);
      if (!row) { row = buildRow(it); rows.append(row); }
      updateRow(it, row);
    }
    updateBar();
  }

  function buildRow(it) {
    const row = h("li", { class: "row", id: "r" + it.id });
    const sel = h("button", { class: "fmt-select small", type: "button", "aria-haspopup": "dialog", "aria-expanded": "false",
      onclick: () => openPicker(sel, { choices: targetsOf(it.src), current: it.dst, src: it.src, onPick: (k) => {
        it.dst = k;
        for (const key of Object.keys(it.opts)) if (!routeOptions(it.src, k).includes(key)) delete it.opts[key];
        if (["done", "error", "cancelled"].includes(it.state)) reset(it);
        renderQueue();
      } }) });
    const tune = h("button", { class: "icon-btn row-tune", type: "button", "aria-label": "Options", "aria-expanded": "false", html: ICON.tune,
      onclick: () => { const open = !drawer.classList.contains("open"); drawer.classList.toggle("open", open); tune.setAttribute("aria-expanded", open); } });
    const grid = h("div", { class: "opts-grid", "data-uid": it.id });
    const drawer = h("div", { class: "drawer" }, h("div", {}, grid));
    row.append(h("span", { class: "row-badge" }),
      h("div", { class: "row-main" }, h("div", { class: "row-name", title: it.name }, it.name), h("div", { class: "row-sub" })),
      h("div", { class: "row-to" }, h("span", {}, "to"), sel), tune, h("div", { class: "row-act" }), drawer, h("span", { class: "progress" }));
    return row;
  }
  function reset(it) { Object.assign(it, { state: "ready", progress: 0, jobId: null, result: null, error: null, message: null, note: null }); }

  function updateRow(it, row) {
    const busy = ["queued", "uploading", "working"].includes(it.state);
    row.style.setProperty("--dst", it.dst ? hue(it.dst) : "var(--accent)");
    const b = $(".row-badge", row);
    b.textContent = "";
    b.append(it.src ? badge(it.src) : h("span", { class: "badge" }, (it.name.split(".").pop() || "?").slice(0, 5).toUpperCase()));

    const sub = $(".row-sub", row);
    sub.className = "row-sub";
    if (it.state === "unsupported") { sub.textContent = "This file type isn't supported yet"; sub.classList.add("err"); }
    else if (it.state === "queued") sub.textContent = "Waiting for its turn…";
    else if (it.state === "uploading") sub.textContent = `Uploading… ${Math.round(it.progress * 100)}%`;
    else if (it.state === "working") sub.textContent = it.message || "Converting…";
    else if (it.state === "done") { sub.textContent = `Done: ${bytes(it.result.size)}${it.note ? ", " + it.note : ""}`; sub.classList.add("good"); }
    else if (it.state === "error") { sub.textContent = it.error || "Something went wrong."; sub.classList.add("err"); }
    else if (it.state === "cancelled") sub.textContent = "Cancelled";
    else sub.textContent = bytes(it.size);

    row.classList.toggle("indeterminate", it.state === "working" && it.progress == null);
    row.style.setProperty("--p", busy ? (it.progress || 0) : it.state === "done" ? 0 : 0);

    const sel = $(".row-to .fmt-select", row);
    $(".row-to", row).hidden = it.state === "unsupported";
    sel.disabled = busy;
    sel.innerHTML = "";
    sel.append(it.dst ? badge(it.dst) : h("span", { class: "placeholder" }, "Choose"));
    if (!busy) sel.insertAdjacentHTML("beforeend", ICON.chev);
    sel.setAttribute("aria-label", it.dst ? `Converting to ${label(it.dst)}. Change format` : "Choose a format");

    const ids = it.src && it.dst ? routeOptions(it.src, it.dst) : [];
    const tune = $(".row-tune", row);
    tune.style.visibility = ids.length && !busy ? "" : "hidden";
    tune.classList.toggle("changed", changed(ids, it.opts));
    const grid = $(".opts-grid", row);
    const sig = it.dst + ":" + ids.join(",");
    if (grid.dataset.sig !== sig) {
      grid.dataset.sig = sig;
      renderOptions(grid, ids, state.cat.options, it.opts, () => {
        tune.classList.toggle("changed", changed(ids, it.opts));
        if (["done", "error", "cancelled"].includes(it.state)) { reset(it); updateRow(it, row); updateBar(); }
      });
      if (it.src === it.dst) grid.prepend(h("p", { class: "opts-note" }, "Same format: use these settings to resize, trim or shrink the file."));
    }
    if (!ids.length || busy) { $(".drawer", row).classList.remove("open"); tune.setAttribute("aria-expanded", "false"); }

    const act = $(".row-act", row);
    act.textContent = "";
    const remove = h("button", { class: "icon-btn", type: "button", "aria-label": `Remove ${it.name}`, title: "Remove", html: ICON.x, onclick: () => removeItem(it) });
    if (it.state === "done") act.append(h("a", { class: "btn save", href: `/api/jobs/${it.jobId}/download`, download: "", html: ICON.save + "Download" }), remove);
    else if (busy) act.append(h("button", { class: "icon-btn", type: "button", "aria-label": "Cancel", title: "Cancel", html: ICON.stop, onclick: () => cancelItem(it) }));
    else {
      if (it.state === "error" || it.state === "cancelled") act.append(h("button", { class: "icon-btn", type: "button", "aria-label": "Try again", title: "Try again", html: ICON.retry, onclick: () => { reset(it); start(it); } }));
      act.append(remove);
    }
  }

  function removeItem(it) {
    if (it.xhr) it.xhr.abort();
    if (it.jobId) fetch(`/api/jobs/${it.jobId}`, { method: "DELETE" }).catch(() => {});
    state.items = state.items.filter((x) => x !== it);
    renderQueue();
  }
  function cancelItem(it) {
    if (it.xhr) it.xhr.abort();
    if (it.jobId) fetch(`/api/jobs/${it.jobId}`, { method: "DELETE" }).catch(() => {});
    it.state = "cancelled";
    renderQueue();
  }

  function updateBar() {
    const items = state.items;
    const ready = items.filter((i) => i.state === "ready" && i.dst);
    const done = items.filter((i) => i.state === "done");
    const busy = items.filter((i) => ["queued", "uploading", "working"].includes(i.state));
    $("#queueCount").textContent = `${items.length} file${items.length === 1 ? "" : "s"}` +
      (busy.length ? `, ${busy.length} converting` : "") + (done.length ? `, ${done.length} done` : "");
    const btn = $("#convertBtn");
    btn.disabled = !ready.length;
    btn.textContent = ready.length > 1 ? `Convert ${ready.length} files` : "Convert";
    const zip = $("#zipAllBtn");
    zip.hidden = done.length < 2;
    zip.href = `/api/bundle?ids=${done.map((i) => i.jobId).join(",")}`;
    const pool = items.filter((i) => i.src && i.state !== "unsupported" && !["queued", "uploading", "working"].includes(i.state));
    let common = null;
    for (const i of pool) { const t = new Set(targetsOf(i.src)); common = common ? new Set([...common].filter((k) => t.has(k))) : t; }
    const show = pool.length > 1 && common && common.size > 0;
    $("#allTo").hidden = !show;
    if (show) {
      state.common = [...common];
      const dsts = new Set(pool.map((i) => i.dst));
      const one = dsts.size === 1 ? [...dsts][0] : null;
      const s = $("#allToSel");
      s.innerHTML = "";
      s.append(one ? badge(one) : h("span", { class: "placeholder" }, "mixed"));
      s.insertAdjacentHTML("beforeend", ICON.chev);
    }
  }
  $("#allToSel").addEventListener("click", (e) => openPicker(e.currentTarget, { choices: state.common, current: null, onPick: (k) => {
    for (const it of state.items) {
      if (!it.src || ["queued", "uploading", "working", "unsupported"].includes(it.state) || !targetsOf(it.src).includes(k)) continue;
      it.dst = k;
      if (it.state !== "ready") reset(it);
    }
    renderQueue();
  } }));
  $("#clearBtn").addEventListener("click", () => {
    for (const it of state.items) { if (it.xhr) it.xhr.abort(); if (it.jobId) fetch(`/api/jobs/${it.jobId}`, { method: "DELETE" }).catch(() => {}); }
    state.items = [];
    renderQueue();
    $("#chooseBtn").focus();
  });
  $("#convertBtn").addEventListener("click", () => state.items.filter((i) => i.state === "ready" && i.dst).forEach(start));
  $("#addMoreBtn").addEventListener("click", () => $("#fileInput").click());
  $("#chooseBtn").addEventListener("click", () => $("#fileInput").click());
  $("#fileInput").addEventListener("change", (e) => { addFiles(e.target.files); e.target.value = ""; });
  $("#pasteKey").textContent = isMac ? "⌘" : "Ctrl";

  // Files wait their turn in the browser: at most 3 upload at once, and no more than the
  // server's per-visitor limit are converting at any moment.
  const waiting = [];
  const slots = () => (state.cat.site.max_active || 12) - state.uploads - state.items.filter((i) => i.state === "working").length;
  function start(it) {
    if (!it.dst) return;
    Object.assign(it, { state: "queued", progress: 0, error: null });
    waiting.push(it);
    pump();
    renderQueue();
  }
  function pump() {
    while (state.uploads < 3 && waiting.length && slots() > 0) {
      const it = waiting.shift();
      if (it.state !== "queued") continue;
      it.state = "uploading";
      state.uploads++;
      upload(it).finally(() => { state.uploads--; pump(); });
    }
  }
  function upload(it) {
    return new Promise((resolve) => {
      const fd = new FormData();
      fd.append("file", it.file, it.name);
      fd.append("source", it.src);
      fd.append("target", it.dst);
      fd.append("options", JSON.stringify(it.opts));
      const x = new XMLHttpRequest();
      it.xhr = x;
      x.open("POST", "/api/convert");
      x.upload.onprogress = (e) => {
        if (!e.lengthComputable) return;
        it.progress = e.loaded / e.total;
        const row = document.getElementById("r" + it.id);
        if (row) updateRow(it, row);
      };
      x.onload = () => {
        it.xhr = null;
        let body = {};
        try { body = JSON.parse(x.responseText); } catch (e) { /* ignore */ }
        if (x.status === 200) { Object.assign(it, { state: "working", jobId: body.id, progress: null, message: "Waiting in line…" }); poll(); }
        else if (x.status === 429) {  // busy in another tab: try again shortly
          Object.assign(it, { state: "queued", progress: 0 });
          setTimeout(() => { waiting.unshift(it); pump(); }, 3000);
        } else Object.assign(it, { state: "error", error: body.error || `Upload failed (${x.status})` });
        renderQueue();
        resolve();
      };
      x.onerror = () => { it.xhr = null; Object.assign(it, { state: "error", error: "The upload failed. Check your connection and try again." }); renderQueue(); resolve(); };
      x.onabort = () => { it.xhr = null; resolve(); };
      x.send(fd);
    });
  }

  async function poll() {
    if (state.polling) return;
    state.polling = true;
    try {
      while (true) {
        const active = state.items.filter((i) => i.state === "working" && i.jobId);
        const others = [yt.job, tools.job].filter(Boolean);
        if (!active.length && !others.length) break;
        let data;
        try {
          data = await api("/api/jobs/status", { method: "POST", headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ ids: [...active.map((i) => i.jobId), ...others.map((j) => j.id)] }) });
        } catch (e) { await new Promise((r) => setTimeout(r, 1500)); continue; }
        let changedAny = false;
        for (const it of active) {
          const j = data[it.jobId];
          if (!j || it.state !== "working") continue;
          if (j.status === "running" || j.status === "queued") {
            it.progress = j.progress;
            it.message = j.message;
            const row = document.getElementById("r" + it.id);
            if (row) updateRow(it, row);
          } else {
            changedAny = true;
            if (j.status === "done") Object.assign(it, { state: "done", result: j.file, note: j.note });
            else if (j.status === "cancelled") it.state = "cancelled";
            else Object.assign(it, { state: "error", error: j.status === "expired" ? "This result expired. Convert it again." : j.error });
          }
        }
        if (changedAny) { renderQueue(); pump(); }
        if (yt.job && data[yt.job.id]) yt.update(data[yt.job.id]);
        if (tools.job && data[tools.job.id]) tools.update(data[tools.job.id]);
        await new Promise((r) => setTimeout(r, 650));
      }
    } finally { state.polling = false; }
  }

  // drag, drop, paste
  let depth = 0;
  const hasFiles = (e) => e.dataTransfer && [...(e.dataTransfer.types || [])].includes("Files");
  const dropTarget = () => state.page === "tools" ? $(".tool-drop") : $("#dropzone");
  addEventListener("dragenter", (e) => { if (!hasFiles(e)) return; depth++; const t = dropTarget(); t && t.classList.add("dragging"); });
  addEventListener("dragleave", () => { depth = Math.max(0, depth - 1); if (!depth) $$(".dragging").forEach((el) => el.classList.remove("dragging")); });
  addEventListener("dragover", (e) => { if (hasFiles(e)) e.preventDefault(); });
  addEventListener("drop", (e) => {
    if (!hasFiles(e)) return;
    e.preventDefault();
    depth = 0;
    $$(".dragging").forEach((el) => el.classList.remove("dragging"));
    if (state.page === "tools") tools.add(e.dataTransfer.files);
    else { if (state.page !== "convert") go("/"); addFiles(e.dataTransfer.files); }
  });
  addEventListener("paste", (e) => {
    const files = e.clipboardData && e.clipboardData.files;
    if (files && files.length) {
      e.preventDefault();
      if (state.page === "tools") tools.add(files); else { if (state.page !== "convert") go("/"); addFiles(files); }
      return;
    }
    const text = e.clipboardData && e.clipboardData.getData("text");
    if (text && /^https?:\/\//i.test(text.trim()) && !e.target.closest("input, textarea")) {
      e.preventDefault();
      go("/youtube");
      $("#ytUrl").value = text.trim();
      yt.fetchInfo();
    }
  });

  // ---------------------------------------------------------------- convert page: content blocks
  function renderHomeBlocks() {
    $("#popular").append(...state.cat.popular.map(([a, b]) => h("li", {},
      h("a", { href: pairUrl(a, b) }, badge(a), h("span", { class: "to-word" }, "to"), badge(b)))));
    const counts = {};
    for (const f of Object.values(state.cat.formats)) counts[f.category] = (counts[f.category] || 0) + 1;
    $("#families").append(...state.cat.categories.filter((c) => counts[c.id]).map((c) => h("li", {},
      h("a", { href: `/formats#${c.id}`, style: `--c: var(--c-${c.id})` }, h("i"), c.label, h("small", {}, String(counts[c.id]))))));
    const site = state.cat.site;
    $("#limits").textContent = `Up to ${site.max_upload_mb >= 1024 ? (site.max_upload_mb / 1024).toFixed(0) + " GB" : site.max_upload_mb + " MB"} per file. Files are deleted after ${site.keep_minutes} minutes.`;
    $("#footNote").textContent = `Uploaded and converted files are deleted automatically after ${site.keep_minutes} minutes. Nobody else can see them.`;
    for (const id of ["ghLink", "ghFoot"]) $("#" + id).href = site.repo;
  }

  // ---------------------------------------------------------------- formats page
  function renderFormats() {
    const box = $("#formatTables");
    const keys = Object.keys(state.cat.formats);
    $("#formatsSub").textContent = `${keys.length} formats and ${state.cat.total_routes.toLocaleString()} conversions. Pick any pair to open its converter.`;
    const fams = state.cat.categories.filter((c) => keys.some((k) => catOf(k) === c.id));
    $("#familyJump").append(...fams.map((c) => h("a", { href: `#${c.id}`, style: `--c: var(--c-${c.id})`,
      onclick: (e) => { e.preventDefault(); document.getElementById(c.id).scrollIntoView({ behavior: "smooth" }); history.replaceState(null, "", "/formats#" + c.id); } }, h("i"), c.label)));
    for (const c of fams) {
      const ks = keys.filter((k) => catOf(k) === c.id);
      const tbody = h("tbody", {}, ks.map((k) => {
        const t = byFamily(targetsOf(k), k);
        const cell = h("div", { class: "targets" });
        const draw = (all) => {
          cell.textContent = "";
          (all ? t : t.slice(0, 14)).forEach((d) => cell.append(h("a", { href: pairUrl(k, d), style: `--c: ${hue(d)}`, title: `${label(k)} to ${label(d)}` }, badge(d))));
          if (!all && t.length > 14) cell.append(h("button", { class: "more-btn", type: "button", onclick: () => draw(true) }, `+${t.length - 14} more`));
        };
        if (t.length) draw(false); else cell.append(h("span", { class: "none" }, "Output only"));
        return h("tr", { "data-k": k }, h("td", {}, badge(k)), h("td", {}, fmt(k).name), h("td", {}, cell));
      }));
      box.append(h("section", { class: "fam-section", id: c.id, style: `--c: var(--c-${c.id})` },
        h("h2", {}, h("i"), c.label, h("small", {}, `${ks.length} format${ks.length === 1 ? "" : "s"}`)),
        h("table", { class: "ftable" }, h("thead", {}, h("tr", {}, h("th", {}, "Format"), h("th", {}, "Name"), h("th", {}, "Converts to"))), tbody)));
    }
    $("#formatSearch").addEventListener("input", (e) => {
      const q = e.target.value.trim().toLowerCase();
      for (const sec of $$(".fam-section", box)) {
        let any = false;
        for (const tr of $$("tr[data-k]", sec)) { const ok = matches(tr.dataset.k, q); tr.hidden = !ok; any ||= ok; }
        sec.hidden = !any;
      }
    });
  }

  // ---------------------------------------------------------------- developers page
  function renderDev() {
    const o = location.origin;
    const s = state.cat.status;
    const doc = $("#devDoc");
    const pre = (t) => h("pre", {}, h("code", {}, t));
    const ep = (m, path, desc) => [h("div", { class: "endpoint" }, h("span", { class: `method ${m.toLowerCase()}` }, m), path), h("p", {}, desc)];
    const engines = [["FFmpeg", s.ffmpeg, "audio and video"], ["LibreOffice", s.libreoffice, "Office documents"], ["Pandoc", s.pandoc, "Markdown, LaTeX, EPUB"],
      ["Calibre", s.calibre, "Kindle e-books"], ["Tesseract", s.tesseract, "text in images"], ["7-Zip", s.sevenzip, "RAR archives"],
      ["yt-dlp", s.ytdlp, "YouTube"], ["JavaScript runtime", s.js_runtime.length > 0, "YouTube unlocking"]];
    doc.append(...[
      h("h2", {}, "Quick start"),
      h("p", {}, "Upload a file with the format you want, check the job until it's done, then download the result."),
      pre(`# 1. Start a conversion\ncurl -F "file=@holiday.mov" -F "target=mp4" ${o}/api/convert\n# → {"id": "3f2c…", "status": "queued", …}\n\n# 2. Check progress\ncurl ${o}/api/jobs/3f2c…\n# → {"status": "done", "file": {"name": "holiday.mp4", "size": 18234112}}\n\n# 3. Download\ncurl -OJ ${o}/api/jobs/3f2c…/download`),
      h("p", {}, "Pass options as JSON, using the option names listed in the catalogue:"),
      pre(`curl -F "file=@song.wav" -F "target=mp3" -F 'options={"abitrate":"320","trim_end":"1:30"}' ${o}/api/convert`),
      h("h2", {}, "Endpoints"),
      ep("GET", "/api/catalogue", "Every format, every conversion route, and the options each route takes."),
      ep("POST", "/api/convert", "Multipart form: file, target, and optional source and options (JSON). Returns a job."),
      ep("GET", "/api/jobs/{id}", "Status (queued, running, done, error or cancelled), progress from 0 to 1, and a message."),
      ep("GET", "/api/jobs/{id}/download", "The converted file."),
      ep("DELETE", "/api/jobs/{id}", "Cancel a running job, or delete a finished one right away."),
      ep("GET", "/api/bundle?ids=a,b,c", "Several finished files in one .zip."),
      ep("POST", "/api/tools/{tool}", "Multipart form with one or more files fields. Tools: merge-pdf, split-pdf, compress-pdf, rotate-pdf, images-to-pdf, zip."),
      ep("POST", "/api/youtube/info", 'JSON {"url": "…"}: title, channel, duration, thumbnail and available qualities.'),
      ep("POST", "/api/youtube/download", 'JSON {"url", "format", "quality", "cover"}. Returns a job.'),
      h("p", {}, `In a browser, jobs are tied to the visitor's cookie, so nobody else can open them. From scripts without a cookie, the job id works like a private link: keep it to yourself. Finished files are deleted after ${state.cat.site.keep_minutes} minutes.`),
      h("h2", {}, "Engines on this server"),
      h("ul", { class: "engines" }, engines.map(([n, on, what]) => h("li", { class: on ? "on" : "off", title: what }, h("i"), n, h("small", { class: "muted" }, on ? "" : " (not installed)")))),
      state.cat.locked.length ? h("p", {}, "Installing the missing engines unlocks: " + state.cat.locked.slice(0, 5).map((l) => `${l.count} more with ${l.tool}`).join(", ") + ".") : null,
      h("h2", {}, "Run your own copy"),
      h("p", {}, "Morph is open source. The quickest way to run it is GitHub Codespaces: everything is installed for you and the site opens in your browser."),
      h("p", {}, h("a", { class: "btn primary codespaces-btn", href: `https://codespaces.new/${state.cat.site.repo.replace("https://github.com/", "")}`, target: "_blank", rel: "noopener" }, "Open in GitHub Codespaces")),
      h("p", {}, "Or with Docker:"),
      pre(`docker build -t morph .\ndocker run -p 8080:8080 morph`),
    ].flat().filter(Boolean));
  }

  // ---------------------------------------------------------------- YouTube
  const yt = {
    info: null, kind: "audio", format: "mp3", quality: "192", job: null, history: [],
    formats: { audio: ["mp3", "m4a", "wav", "flac", "opus"], video: ["mp4", "webm", "mkv"] },
    async fetchInfo() {
      const url = $("#ytUrl").value.trim();
      if (!url) return $("#ytUrl").focus();
      const btn = $("#ytFetch");
      btn.disabled = true;
      btn.textContent = "Finding…";
      try {
        yt.info = await api("/api/youtube/info", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ url }) });
        yt.show();
      } catch (e) { toast(e.message); }
      finally { btn.disabled = false; btn.textContent = "Find video"; }
    },
    show() {
      const i = yt.info;
      $("#ytCard").hidden = false;
      $("#ytThumb").src = i.thumbnail || "";
      $("#ytThumb").alt = i.title ? `Thumbnail for ${i.title}` : "";
      $("#ytDur").textContent = i.live ? "Live" : clock(i.duration);
      $("#ytDur").hidden = !i.duration && !i.live;
      $("#ytTitle").textContent = i.title;
      const views = i.views ? `${Intl.NumberFormat(undefined, { notation: "compact" }).format(i.views)} views` : "";
      $("#ytMeta").textContent = [i.channel, views, i.site && i.site !== "Youtube" ? `from ${i.site}` : ""].filter(Boolean).join(", ");
      $("#ytProgress").hidden = true;
      $("#ytDownload").hidden = false;
      yt.choices();
    },
    setKind(kind) {
      yt.kind = kind;
      $$(".kind-btn").forEach((b) => b.setAttribute("aria-checked", b.dataset.kind === kind));
      yt.format = yt.formats[kind][0];
      yt.quality = kind === "audio" ? "192" : (yt.heights().includes(1080) ? "1080" : "best");
      yt.choices();
    },
    heights() {
      const have = (yt.info && yt.info.heights) || [];
      return [2160, 1440, 1080, 720, 480, 360].filter((s) => have.some((x) => x >= s * 0.88 && x <= s * 1.12));
    },
    choices() {
      const fbox = $("#ytFormats"), qbox = $("#ytQualities");
      fbox.textContent = "";
      for (const f of yt.formats[yt.kind]) fbox.append(h("button", { class: "chip", type: "button", role: "radio", "aria-checked": f === yt.format,
        onclick: () => { yt.format = f; if (yt.kind === "audio") yt.quality = "192"; yt.choices(); } }, f.toUpperCase()));
      let qs = [], hint = "";
      if (yt.kind === "audio") {
        if (yt.format === "mp3") { qs = [["128", "128 kbps"], ["192", "192 kbps"], ["256", "256 kbps"], ["320", "320 kbps"]]; hint = "YouTube's own audio is about 130 to 160 kbps, so 192 keeps all of it."; }
        else if (yt.format === "m4a" || yt.format === "opus") hint = "Saved exactly as YouTube streams it, with no re-encoding.";
        else hint = "Lossless file: large, but nothing gets thrown away.";
      } else {
        qs = [["best", "Best"], ...yt.heights().map((x) => [String(x), x === 2160 ? "4K" : x + "p"])];
        if (!qs.some(([v]) => v === yt.quality)) yt.quality = "best";
        if (yt.format === "mp4") hint = (yt.quality === "best" || Number(yt.quality) > 1080)
          ? "Above 1080p YouTube only offers VP9 or AV1 video. It plays in browsers and VLC, but may not in older apps."
          : "H.264 video with AAC sound plays on everything.";
      }
      qbox.parentElement.hidden = !qs.length;
      qbox.textContent = "";
      for (const [v, l] of qs) qbox.append(h("button", { class: "chip", type: "button", role: "radio", "aria-checked": v === yt.quality, onclick: () => { yt.quality = v; yt.choices(); } }, l));
      $("#ytHint").textContent = hint;
      $("#ytHint").hidden = !hint;
      const ql = qs.find(([v]) => v === yt.quality);
      $("#ytDownload").textContent = `Download ${yt.format.toUpperCase()}${yt.kind === "video" && ql && ql[0] !== "best" ? ` (${ql[1]})` : ""}`;
      $("#ytCover").closest(".switch").hidden = yt.format === "wav";
    },
    async start() {
      if (!yt.info) return;
      try {
        const j = await api("/api/youtube/download", { method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ url: yt.info.url, format: yt.format, quality: yt.quality, cover: $("#ytCover").checked, title: yt.info.title }) });
        yt.job = { id: j.id, info: yt.info, format: yt.format };
        $("#ytDownload").hidden = true;
        $("#ytProgress").hidden = false;
        yt.update(j);
        poll();
      } catch (e) { toast(e.message); }
    },
    update(j) {
      $(".bar", $("#ytProgress")).classList.toggle("indeterminate", j.progress == null && (j.status === "running" || j.status === "queued"));
      $("#ytBar").style.width = `${Math.round((j.progress || 0) * 100)}%`;
      $("#ytStatus").textContent = j.message || "";
      if (["done", "error", "cancelled", "expired"].includes(j.status)) {
        const job = yt.job;
        yt.job = null;
        $("#ytProgress").hidden = true;
        $("#ytDownload").hidden = false;
        if (j.status === "done") {
          download(`/api/jobs/${j.id}/download`);
          yt.history.unshift({ id: j.id, info: job.info, file: j.file });
          yt.renderHistory();
        } else if (j.status === "error") toast(j.error || "The download failed.");
      }
    },
    renderHistory() {
      $("#ytHistoryBlock").hidden = !yt.history.length;
      const ul = $("#ytHistory");
      ul.textContent = "";
      for (const it of yt.history) ul.append(h("li", {},
        it.info.thumbnail ? h("img", { src: it.info.thumbnail, alt: "", referrerpolicy: "no-referrer" }) : null,
        h("div", { class: "t" }, it.file.name, h("span", { class: "s" }, bytes(it.file.size))),
        h("a", { class: "btn save", href: `/api/jobs/${it.id}/download`, download: "", html: ICON.save + "Download" })));
    },
  };
  $("#ytForm").addEventListener("submit", (e) => { e.preventDefault(); yt.fetchInfo(); });
  $("#ytPaste").addEventListener("click", async () => {
    try {
      const t = (await navigator.clipboard.readText()).trim();
      if (!t) return toast("Your clipboard is empty.", "info");
      $("#ytUrl").value = t;
      yt.fetchInfo();
    } catch (e) {
      toast(`Your browser blocked clipboard access. Click the box and press ${isMac ? "⌘" : "Ctrl"}+V instead.`, "info");
      $("#ytUrl").focus();
    }
  });
  let ytTimer = 0;
  $("#ytUrl").addEventListener("input", (e) => {
    clearTimeout(ytTimer);
    const v = e.target.value.trim();
    if (/^https?:\/\/\S+\.\S+/.test(v) && (!yt.info || yt.info.url !== v)) ytTimer = setTimeout(() => yt.fetchInfo(), 600);
  });
  $$(".kind-btn").forEach((b) => b.addEventListener("click", () => yt.setKind(b.dataset.kind)));
  $("#ytDownload").addEventListener("click", () => yt.start());
  $("#ytCancel").addEventListener("click", () => { if (yt.job) fetch(`/api/jobs/${yt.job.id}`, { method: "DELETE" }); });

  function renderYtNotice() {
    const s = state.cat.youtube, box = $("#ytNotice"), lines = [];
    if (!s.installed) lines.push(h("p", {}, h("strong", {}, "The YouTube downloader isn't installed on this server. "), "Run this, then restart Morph: "), h("p", {}, h("code", {}, 'pip install -U "yt-dlp[default]"')));
    else if (!s.js_runtimes.length) lines.push(h("p", {}, h("strong", {}, "Install Deno for reliable YouTube downloads. "), "YouTube now needs a small JavaScript helper; restart Morph after installing it."));
    if (!s.ffmpeg) lines.push(h("p", {}, "FFmpeg is missing, so audio and video can't be saved yet: ", h("code", {}, "pip install imageio-ffmpeg")));
    box.hidden = !lines.length;
    box.append(...lines);
  }

  // ---------------------------------------------------------------- PDF tools
  const tools = {
    current: null, perTool: {}, job: null,
    st() { return (this.perTool[this.current] ||= { files: [], opts: {} }); },
    select(name) {
      tools.current = name;
      $$("#toolList button").forEach((b) => b.setAttribute("aria-selected", b.dataset.tool === name));
      tools.render();
    },
    add(list) {
      const spec = state.cat.tools[tools.current], st = tools.st();
      let rejected = 0;
      for (const f of list) {
        const k = detect(f.name);
        if (spec.accept[0] !== "*" && !spec.accept.includes(k)) { rejected++; continue; }
        if (!spec.multi) st.files = [];
        st.files.push(f);
      }
      if (rejected) toast(`${rejected} file${rejected > 1 ? "s were" : " was"} skipped: ${spec.title} takes ${spec.accept.map((a) => "." + a).join(", ")} files.`, "info");
      st.result = null;
      tools.render();
    },
    render() {
      const spec = state.cat.tools[tools.current], st = tools.st();
      const stage = $("#toolStage");
      stage.setAttribute("aria-labelledby", "tool-" + tools.current);
      stage.textContent = "";
      const input = h("input", { type: "file", hidden: true, multiple: spec.multi, accept: spec.accept[0] === "*" ? null : spec.accept.map((a) => "." + a).join(","),
        onchange: (e) => { tools.add(e.target.files); e.target.value = ""; } });
      stage.append(h("p", {}, spec.blurb),
        h("div", { class: "dropzone tool-drop" },
          h("button", { class: "btn primary", type: "button", onclick: () => input.click() }, spec.multi ? "Choose files" : "Choose a file"),
          h("p", { class: "dz-hint" }, "or drop them here")), input);
      if (st.files.length) {
        const ul = h("ul", { class: "tool-files" });
        st.files.forEach((f, i) => {
          const move = (d) => { const j = i + d; [st.files[i], st.files[j]] = [st.files[j], st.files[i]]; tools.render(); };
          ul.append(h("li", {}, h("span", { class: "n" }, String(i + 1)), h("span", { class: "fn", title: f.name }, f.name), h("span", { class: "sz" }, bytes(f.size)),
            h("span", { class: "mv" },
              spec.multi && st.files.length > 1 ? h("button", { class: "icon-btn", type: "button", "aria-label": `Move ${f.name} up`, disabled: i === 0, html: ICON.up, onclick: () => move(-1) }) : null,
              spec.multi && st.files.length > 1 ? h("button", { class: "icon-btn", type: "button", "aria-label": `Move ${f.name} down`, disabled: i === st.files.length - 1, html: ICON.down, onclick: () => move(1) }) : null,
              h("button", { class: "icon-btn", type: "button", "aria-label": `Remove ${f.name}`, html: ICON.x, onclick: () => { st.files.splice(i, 1); tools.render(); } }))));
        });
        stage.append(ul);
      }
      if (spec.options) {
        const grid = h("div", { class: "opts-grid", "data-uid": "tool" });
        renderOptions(grid, Object.keys(spec.options), spec.options, st.opts);
        stage.append(grid);
      }
      const verb = { "merge-pdf": "Merge PDFs", "split-pdf": "Split PDF", "compress-pdf": "Compress PDF", "rotate-pdf": "Rotate PDF", "images-to-pdf": "Make PDF", "zip": "Make .zip" }[tools.current];
      const need = tools.current === "merge-pdf" ? 2 : 1;
      const run = h("button", { class: "btn primary", type: "button", disabled: st.files.length < need || !!tools.job, onclick: () => tools.run() }, tools.job ? "Working…" : verb);
      const res = h("span", { class: "tool-result", "aria-live": "polite" });
      if (tools.job) res.textContent = tools.job.message || "Working…";
      else if (st.result && st.result.error) { res.textContent = st.result.error; res.classList.add("err"); }
      else if (st.result) res.append(h("a", { class: "btn save", href: `/api/jobs/${st.result.id}/download`, download: "", html: ICON.save + "Download " + st.result.file.name }),
        `${bytes(st.result.file.size)}${st.result.note ? ", " + st.result.note : ""}`);
      else if (tools.current === "merge-pdf" && st.files.length === 1) res.textContent = "Add one more PDF to merge.";
      stage.append(h("div", { class: "tool-run" }, run, res));
    },
    async run() {
      const st = tools.st(), fd = new FormData();
      st.files.forEach((f) => fd.append("files", f, f.name));
      fd.append("options", JSON.stringify(st.opts));
      try {
        tools.job = { id: null, tool: tools.current, message: "Uploading…" };
        tools.render();
        const j = await api(`/api/tools/${tools.current}`, { method: "POST", body: fd });
        tools.job.id = j.id;
        st.result = null;
        poll();
      } catch (e) { tools.job = null; st.result = { error: e.message }; tools.render(); }
    },
    update(j) {
      if (!tools.job) return;
      tools.job.message = j.message;
      if (["done", "error", "cancelled", "expired"].includes(j.status)) {
        tools.perTool[tools.job.tool].result = j.status === "done" ? { id: j.id, file: j.file, note: j.note } : { error: j.error || "That didn't work." };
        tools.job = null;
      }
      if (tools.current) tools.render();
    },
  };
  function renderTools() {
    const list = $("#toolList");
    for (const [name, spec] of Object.entries(state.cat.tools)) {
      const [ic, color] = TOOL_LOOK[name] || ["zip", "--c-archive"];
      list.append(h("button", { type: "button", role: "tab", id: "tool-" + name, "data-tool": name, "aria-selected": "false", style: `--c: var(${color})`,
        onclick: () => tools.select(name) }, h("span", { class: "ti", html: ICON[ic] }), spec.title));
    }
    list.addEventListener("keydown", (e) => {
      const btns = $$("button", list), i = btns.indexOf(document.activeElement);
      if (i < 0 || (e.key !== "ArrowRight" && e.key !== "ArrowLeft")) return;
      const n = btns[(i + (e.key === "ArrowRight" ? 1 : btns.length - 1)) % btns.length];
      n.focus(); tools.select(n.dataset.tool);
    });
    tools.select(Object.keys(state.cat.tools)[0]);
  }

  // ---------------------------------------------------------------- boot
  async function boot() {
    try { state.cat = await api("/api/catalogue"); }
    catch (e) { $("#convertSub").textContent = "The converter isn't responding right now. Reload the page in a moment."; return; }
    renderHomeBlocks();
    renderFormats();
    renderDev();
    renderYtNotice();
    renderTools();
    yt.setKind("audio");
    go(location.pathname, false);
  }
  boot();
})();
