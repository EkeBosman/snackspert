/* Snackspert Trendradar – interface. */
(function () {
  const { esc, sparkline, lineChart, compareBars, columnChart } = window.Charts;
  const $ = s => document.querySelector(s);
  const $$ = s => Array.from(document.querySelectorAll(s));

  const PLATFORM = {
    instagram: { name: "Instagram", color: "var(--s-instagram)" },
    tiktok: { name: "TikTok", color: "var(--s-tiktok)" },
    facebook: { name: "Facebook", color: "var(--s-facebook)" },
    nieuws: { name: "Nieuws", color: "var(--s-nieuws)" },
  };
  const TYPE_CHIPS = [
    ["", "Alles"], ["categorie", "Gerechten"], ["product", "Producten"],
    ["merk", "Merken & winkels"], ["zaak", "Zaken"], ["woord", "Nieuwe woorden"], ["zin", "Woordcombinaties"], ["stad", "Steden"],
  ];

  const state = {
    tab: "trends", window: "24u", platform: "", minRel: "0.35",
    typeFilter: "", trends: null, posts: { offset: 0, topic: null },
    sourceFilter: "actief", status: null,
  };

  try {
    const saved = JSON.parse(localStorage.getItem("trendradar") || "{}");
    if (saved.window) state.window = saved.window;
    if (saved.platform != null) state.platform = saved.platform;
    if (saved.tab) state.tab = saved.tab;
  } catch (e) { /* geen opslag beschikbaar */ }

  function remember() {
    try {
      localStorage.setItem("trendradar", JSON.stringify({ window: state.window, platform: state.platform, tab: state.tab }));
    } catch (e) { /* negeren */ }
  }

  const nf = new Intl.NumberFormat("nl-NL");
  const fmt = n => nf.format(Math.round(n || 0));
  const compact = n => (n >= 10000 ? nf.format(Math.round(n / 1000)) + "k" : fmt(n));

  function ago(iso) {
    if (!iso) return "–";
    const s = (Date.now() - new Date(iso).getTime()) / 1000;
    if (s < 0) {
      const m = Math.round(-s / 60);
      return m < 60 ? `over ${m} min` : `over ${Math.round(m / 60)} uur`;
    }
    if (s < 90) return "zojuist";
    if (s < 3600) return `${Math.round(s / 60)} min geleden`;
    if (s < 86400 * 2) return `${Math.round(s / 3600)} uur geleden`;
    return `${Math.round(s / 86400)} dagen geleden`;
  }
  const dateNl = iso => new Date(iso).toLocaleDateString("nl-NL", { day: "numeric", month: "short" });

  function qs(extra = {}) {
    const p = new URLSearchParams({ window: state.window, min_rel: state.minRel, ...extra });
    if (state.platform) p.set("platform", state.platform);
    return p.toString();
  }

  async function api(path, opts) {
    const r = await fetch(path, opts);
    const data = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(data.fout || data.melding || `Fout ${r.status}`);
    return data;
  }

  function toast(msg) {
    const t = $("#toast");
    t.textContent = msg;
    t.hidden = false;
    clearTimeout(toast.timer);
    toast.timer = setTimeout(() => (t.hidden = true), 3500);
  }

  function pdots(platforms) {
    return `<span class="pdots">${platforms.map(p =>
      `<span class="pdot" style="--c:${PLATFORM[p]?.color}" title="${esc(PLATFORM[p]?.name || p)}"></span>`).join("")}</span>`;
  }

  // Hoe ver ligt iets boven normaal? Alleen tonen wat echt opvalt (≥ 2×).
  function sigChips(sig, opts = {}) {
    if (!sig) return "";
    const out = [];
    if (sig.breakouts) out.push(`<span class="sig hot" title="Posts die ver boven normaal scoren, vaak van kleine makers">🚀 ${sig.breakouts} doorbraak${sig.breakouts > 1 ? "en" : ""}</span>`);
    if (sig.breakout) out.push(`<span class="sig hot" title="Veel meer bereik dan normaal voor deze maker of leeftijd">🚀 doorbraak</span>`);
    const x = (v, icon, label, title) => v && v >= 2 ? out.push(`<span class="sig" title="${title}">${icon} ${label} ${fmtX(v)}</span>`) : null;
    x(sig.views_x, "▶", "views", "Views vergeleken met een gewone post van dezelfde leeftijd");
    x(sig.shares_x, "↗", "gedeeld", "Hoe vaak doorgestuurd per view, vergeleken met normaal");
    x(sig.likes_x, "♥", "likes", "Likes per view, vergeleken met normaal");
    if (opts.reach && sig.reach_x && sig.reach_x >= 3) out.push(`<span class="sig" title="Views gedeeld door het aantal volgers">👥 bereik ${fmtX(sig.reach_x)} volgers</span>`);
    return `<span class="sigs">${out.join("")}</span>`;
  }
  const euro2 = v => "€ " + Number(v || 0).toFixed(v < 0.1 && v > 0 ? 3 : 2).replace(".", ",");
  const fmtX = v => (v >= 10 ? Math.round(v) : Math.round(v * 10) / 10).toString().replace(".", ",") + "×";

  function makers(t) {
    const extra = t.authors - (t.authors_baseline || 0);
    const tip = `${t.authors} makers nu, gemiddeld ${String(t.authors_baseline).replace(".", ",")} per periode ervoor`;
    return `<span title="${tip}">${t.authors}${extra >= 2 ? ` <small class="up">+${Math.round(extra)}</small>` : ""}</span>`;
  }

  function growth(t) {
    // Was er in de periodes ervoor (bijna) niets, dan is een percentage misleidend.
    if (t.new || t.growth_pct === null || t.baseline < 0.5) return `<span class="badge new">nieuw</span>`;
    if (t.growth_pct >= 200) return `<span class="up" title="+${fmt(t.growth_pct)}%">×${fmt(t.growth_pct / 100 + 1)}</span>`;
    const cls = t.growth_pct > 0 ? "up" : t.growth_pct < 0 ? "down" : "";
    const sign = t.growth_pct > 0 ? "+" : "";
    return `<span class="${cls}">${sign}${fmt(t.growth_pct)}%</span>`;
  }

  // --- status ------------------------------------------------------------

  async function loadStatus() {
    const s = await api("/api/status");
    state.status = s;
    $("#demo-banner").hidden = !s.demo_data;
    $("#btn-clear-demo").hidden = !s.demo_data;
    const btn = $("#btn-run");
    btn.disabled = s.running;
    btn.textContent = s.running ? "Bezig met ophalen…" : "Nu ophalen";
    let line = s.last_run ? `Laatste ronde ${ago(s.last_run.started_at)}` : "Nog geen ophaalronde";
    if (s.running) line = "Ophaalronde loopt…";
    if (s.next_run && !s.running) line += ` · volgende ${ago(s.next_run)}`;
    line += ` · ${fmt(s.posts)} posts · ${fmt(s.sources.actief || 0)} actieve bronnen`;
    if (s.sources.kandidaat) line += ` · ${s.sources.kandidaat} kandidaten`;
    $("#status-line").textContent = line;
    return s;
  }

  let wasRunning = false;
  async function poll() {
    try {
      const s = await loadStatus();
      if (wasRunning && !s.running) { toast("Ophaalronde klaar"); refresh(); }
      wasRunning = s.running;
    } catch (e) { /* server even weg */ }
  }

  // --- trends -------------------------------------------------------------

  async function loadTrends() {
    const d = await api("/api/trends?" + qs());
    state.trends = d;
    const note = $("#history-note");
    if (!d.history_ok) {
      note.hidden = false;
      note.textContent = `Opbouwfase: voor een betrouwbare vergelijking in de periode '${d.label}' is ${Math.round(d.needed_hours / 24 * 10) / 10} dagen historie nodig, er is nu ${Math.round(d.history_hours / 24 * 10) / 10} dag. Tot die tijd zijn de groeicijfers indicatief.`;
    } else note.hidden = true;

    const vol = d.volume;
    const sumAll = arr => arr.reduce((a, b) => a + b, 0);
    let curTotal = 0, baseTotal = 0;
    Object.values(vol.series).forEach(s => {
      curTotal += sumAll(s.slice(vol.current_from));
      baseTotal += sumAll(s.slice(0, vol.current_from));
    });
    const baseAvg = vol.current_from ? baseTotal / (vol.current_from / (vol.labels.length - vol.current_from)) : 0;
    const delta = baseAvg ? Math.round((curTotal / baseAvg - 1) * 100) : null;
    const kpis = [
      ["Relevante posts", fmt(d.totals.posts), delta === null ? "" : `${delta >= 0 ? "+" : ""}${delta}% t.o.v. periode ervoor`],
      ["Makers", fmt(d.totals.makers), "verschillende accounts"],
      ["Doorbraken", fmt(d.totals.breakouts), "posts die ver boven normaal scoren"],
      ["Nieuwe onderwerpen", fmt(d.new_topics.length), "niet gezien in de periodes ervoor"],
    ];
    $("#kpis").innerHTML = kpis.map(([l, v, s]) =>
      `<div class="kpi"><div class="label">${l}</div><div class="value">${v}</div><div class="delta">${esc(s)}</div></div>`).join("");

    renderTopics();
    $("#stijgers-sub").textContent = `· ${d.label}`;

    $("#list-new").innerHTML = d.new_topics.length ? d.new_topics.slice(0, 10).map(t =>
      `<li><div class="row"><button class="linkish" data-topic="${esc(t.type)}|${esc(t.name)}">${esc(t.name)}</button>
       <span class="meta">${t.posts} posts · ${t.authors} makers</span></div>
       <div class="meta"><span class="badge">${esc(t.type_label)}</span>${pdots(t.platforms)}</div></li>`).join("")
      : `<li class="meta">Niets nieuws in deze periode.</li>`;

    $("#list-breakouts").innerHTML = d.breakouts.length ? d.breakouts.slice(0, 6).map(b => {
      const p = d.post_lookup[b.id];
      if (!p) return "";
      const fol = b.signals.followers ? `${compact(b.signals.followers)} volgers` : "volgers onbekend";
      return `<li><div class="row"><span><span class="ptag" style="--pc:${PLATFORM[p.platform]?.color}">${esc(PLATFORM[p.platform]?.name)}</span> @${esc(p.author || "?")} <span class="meta">· ${fol}</span></span>
        <span class="meta">${compact(p.views)} views${b.count > 1 ? ` · ${b.count} virale posts` : ""}</span></div>
        <div>${sigChips(b.signals, { reach: true })}</div>
        <div class="meta">${esc((p.summary || p.text || "").slice(0, 120))}${p.url ? ` · <a href="${esc(p.url)}" target="_blank" rel="noopener">bekijk</a>` : ""}</div></li>`;
    }).join("") : `<li class="meta">Geen doorbraken in deze periode.</li>`;

    $("#list-rising").innerHTML = d.rising_posts.length ? d.rising_posts.slice(0, 6).map(p =>
      `<li><div class="row"><span><span class="ptag" style="--pc:${PLATFORM[p.platform]?.color}">${esc(PLATFORM[p.platform]?.name)}</span> @${esc(p.author || "?")}</span>
       <span class="meta up">+${fmt(p.gain_per_hour)}/uur</span></div>
       <div class="meta">${esc((p.summary || p.text || "").slice(0, 110))}${p.url ? ` · <a href="${esc(p.url)}" target="_blank" rel="noopener">bekijk</a>` : ""}</div></li>`).join("")
      : `<li class="meta">Er zijn minstens twee ophaalrondes nodig om groei te meten.</li>`;

    const keys = Object.keys(vol.series).sort((a, b) => Object.keys(PLATFORM).indexOf(a) - Object.keys(PLATFORM).indexOf(b));
    const sm = {}; keys.forEach(k => (sm[k] = vol.series[k]));
    lineChart($("#chart-volume"), vol.labels, sm, {
      currentFrom: vol.current_from, bucketHours: d.bucket_hours, label: "Relevante posts per platform",
      names: Object.fromEntries(keys.map(k => [k, PLATFORM[k]?.name || k])),
      colors: Object.fromEntries(keys.map(k => [k, PLATFORM[k]?.color])),
    });
    compareBars($("#chart-cats"), d.categories.slice(0, 10).map(c => ({ name: c.name, cur: c.posts, base: c.baseline, t: c })), {
      label: "Posts per categorie", onClick: r => openTopic("categorie", r.name),
    });

    $("#exp-trends").href = "/api/export/trends.csv?" + qs();
    $("#exp-posts").href = "/api/export/posts.csv?" + qs();
  }

  function renderTopics() {
    const d = state.trends;
    if (!d) return;
    // 'Alles' toont de specifieke onderwerpen; brede gerechten en steden hebben een eigen knop.
    const rows = d.topics.filter(t => state.typeFilter ? t.type === state.typeFilter
      : !["categorie", "stad"].includes(t.type)).slice(0, 25);
    const tbody = $("#tbl-topics tbody");
    tbody.innerHTML = rows.length ? "" : `<tr><td colspan="8" class="muted">Geen onderwerpen gevonden. Probeer een langere periode of strengheid 'Breed'.</td></tr>`;
    rows.forEach((t, i) => {
      const tr = document.createElement("tr");
      tr.className = "click";
      tr.innerHTML = `<td class="rank">${i + 1}</td>
        <td><span class="badge">${esc(t.type_label)}</span><span class="topic-name">${esc(t.name)}</span></td>
        <td class="hide-s spark"></td>
        <td class="num">${fmt(t.posts)}</td><td class="num">${growth(t)}</td>
        <td class="num hide-s">${makers(t)}</td><td class="hide-s">${sigChips(t.signals)}</td>
        <td class="hide-s">${pdots(t.platforms)}</td>`;
      tr.querySelector(".spark").appendChild(sparkline(t.series, d.baseline_buckets));
      tr.addEventListener("click", () => openTopic(t.type, t.name));
      tbody.appendChild(tr);
    });
  }

  // --- onderwerp-detail ---------------------------------------------------

  async function openTopic(type, name) {
    const drawer = $("#drawer");
    drawer.hidden = false;
    $("#d-title").textContent = name;
    $("#d-type").textContent = (TYPE_CHIPS.find(c => c[0] === type) || [, type])[1];
    $("#d-chart").innerHTML = '<div class="empty">Laden…</div>';
    $("#d-posts").innerHTML = "";
    const win = state.window === "nu" ? "24u" : state.window;
    const d = await api("/api/topic?" + new URLSearchParams({ type, name, window: win, min_rel: state.minRel }));
    columnChart($("#d-chart"), d.labels, d.series, { currentFrom: d.current_from, label: `Posts over ${name}` });
    $("#d-meta").innerHTML = `<span class="chip static">${d.total} posts</span><span class="chip static">${d.makers} makers</span>` +
      (d.signals ? sigChips(d.signals) : "") +
      Object.entries(d.platforms).map(([p, n]) => `<span class="chip static"><span class="pdot" style="--c:${PLATFORM[p]?.color}"></span> ${esc(PLATFORM[p]?.name || p)} ${n}</span>`).join("");
    $("#d-related").innerHTML = d.related.length ? d.related.map(([t, n]) =>
      `<button class="chip" data-topic="hashtag|${esc(t)}">${esc(t)} · ${n}</button>`).join("") : '<span class="muted">–</span>';
    $("#d-posts").innerHTML = d.posts.map(postCard).join("");
    $("#d-all").onclick = () => {
      drawer.hidden = true;
      state.posts.topic = { type, name };
      switchTab("posts");
    };
    const follow = $("#d-follow");
    follow.hidden = type !== "hashtag";
    follow.onclick = async () => {
      const value = name.replace(/^#/, "");
      for (const platform of ["instagram", "tiktok"]) {
        await api("/api/sources", { method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ platform, kind: "hashtag", value }) });
      }
      toast(`#${value} wordt gevolgd op Instagram en TikTok`);
    };
  }

  function postCard(p) {
    const plat = PLATFORM[p.platform] || { name: p.platform, color: "var(--muted)" };
    const metrics = [];
    if (p.likes) metrics.push(`♥ ${compact(p.likes)}`);
    if (p.comments) metrics.push(`💬 ${compact(p.comments)}`);
    if (p.shares) metrics.push(`↗ ${compact(p.shares)}`);
    if (p.views) metrics.push(`▶ ${compact(p.views)}`);
    const sig = p.signals ? sigChips(p.signals, { reach: true }) : "";
    const tags = [...(p.categories || []), ...(p.brands || []).slice(0, 2)].slice(0, 4)
      .map(c => `<span class="badge">${esc(c)}</span>`).join("");
    const thumb = p.thumbnail ? `<img src="${esc(p.thumbnail)}" alt="" loading="lazy" referrerpolicy="no-referrer" onerror="this.remove()">` : "";
    return `<article class="post">
      <div class="post-head"><span><span class="ptag" style="--pc:${plat.color}">${esc(plat.name)}</span> · <strong>${p.platform === "nieuws" ? esc(p.author || "") : "@" + esc(p.author || "onbekend")}</strong></span>
      <span title="${esc(new Date(p.posted_at).toLocaleString("nl-NL"))}">${ago(p.posted_at)}</span></div>
      ${sig}
      ${p.summary ? `<div class="post-sum">${esc(p.summary)}</div>` : ""}
      <div class="post-body">${thumb}<div class="post-text">${esc(p.text)}</div></div>
      <div>${tags}${p.city ? `<span class="badge">📍 ${esc(p.city)}</span>` : ""}${p.demo ? '<span class="badge warn">demo</span>' : ""}</div>
      <div class="post-foot">${metrics.join(" ")}<span>relevantie ${Math.round((p.relevance || 0) * 100)}%</span>
      ${p.url ? `<a href="${esc(p.url)}" target="_blank" rel="noopener">Open ↗</a>` : ""}</div>
    </article>`;
  }

  // --- posts --------------------------------------------------------------

  async function loadPosts(append = false) {
    if (!append) state.posts.offset = 0;
    const extra = { sort: $("#p-sort").value, offset: state.posts.offset, limit: 60 };
    const q = $("#p-q").value.trim();
    if (q) extra.q = q;
    if ($("#p-cat").value) extra.category = $("#p-cat").value;
    const topic = state.posts.topic;
    if (topic) { extra.topic_type = topic.type; extra.topic = topic.name; }
    const d = await api("/api/posts?" + qs(extra));
    const note = $("#p-topic");
    note.hidden = !topic;
    if (topic) {
      note.innerHTML = `Gefilterd op <strong>${esc(topic.name)}</strong> · <button class="btn small ghost" id="p-untopic">filter weghalen</button>`;
      $("#p-untopic").onclick = () => { state.posts.topic = null; loadPosts(); };
    }
    const html = d.posts.map(postCard).join("");
    $("#posts").innerHTML = append ? $("#posts").innerHTML + html : (html || '<p class="muted">Geen posts gevonden.</p>');
    state.posts.offset += d.posts.length;
    $("#p-count").textContent = `${fmt(d.total)} posts`;
    $("#p-more").hidden = state.posts.offset >= d.total;
  }

  // --- supermarkt ---------------------------------------------------------

  async function loadSupermarkt() {
    const d = await api("/api/supermarkt?" + qs(state.allProducts ? { alles: "1" } : {}));
    const st = Object.entries(d.status || {});
    $("#store-status").innerHTML = st.length ? st.map(([store, s]) =>
      `<span class="chip static"><span class="badge ${s.ok ? "ok" : "bad"}">${s.ok ? "✓ werkt" : "✗ storing"}</span>${esc(store)}: ${esc(s.melding)} · ${ago(s.t)}</span>`).join("")
      : `<span class="chip static">Het assortiment van AH, Jumbo, Lidl, Plus en andere winkels wordt twee keer per dag vergeleken (eerste keer bij de eerstvolgende ronde).</span>`;
    const CONF = { winkel: "🏪 winkel", social: "📱 social", nieuws: "📰 nieuws" };
    $("#list-early").innerHTML = d.early.length ? d.early.map(m =>
      `<li><div class="row"><button class="linkish" data-topic="product|${esc(m.name)}">${esc(m.name)}</button>
        <span class="meta">${m.makers} maker${m.makers === 1 ? "" : "s"} · ${m.posts} posts</span></div>
        <div class="meta">${esc(m.stores.join(", ") || "winkel onbekend")} · eerst gezien ${ago(m.first)} ${pdots(m.platforms)}
        ${m.store_tracked ? '<span class="badge new">nog niet in winkeldata</span>' : '<span class="badge">geen winkeldata voor deze winkel</span>'}</div></li>`).join("")
      : `<li class="meta">Geen vroege signalen deze week.</li>`;
    $("#tbl-products tbody").innerHTML = d.products.length ? d.products.map(p =>
      `<tr><td><span class="topic-name">${p.url ? `<a href="${esc(p.url)}" target="_blank" rel="noopener">${esc(p.name)}</a>` : esc(p.name)}</span>${p.demo ? ' <span class="badge warn">demo</span>' : ""}<div class="meta muted">${esc(p.brand || "")}</div></td>
       <td>${esc(p.store)}</td><td class="hide-s">${esc(p.size || p.category || "")}</td>
       <td class="num">${p.price != null ? "€ " + Number(p.price).toFixed(2).replace(".", ",") : "–"}</td>
       <td>${dateNl(p.first_seen)}</td>
       <td><span class="sigs">${p.confirmed_by.map(c => `<span class="sig ${c !== "winkel" ? "hot" : ""}">${CONF[c]}${c === "social" ? " " + p.social_makers : ""}</span>`).join("")}</span></td></tr>`).join("")
      : `<tr><td colspan="6" class="muted">Nog geen nieuwe producten. De eerste controle legt alleen vast wat er ligt; daarna verschijnen nieuwkomers hier.</td></tr>`;
    $("#tbl-mentioned tbody").innerHTML = d.mentioned.length ? d.mentioned.map(m =>
      `<tr class="click" data-topic="product|${esc(m.name)}"><td><span class="topic-name">${esc(m.name)}</span> ${pdots(m.platforms)}
       <div class="meta">${m.in_store ? "in winkeldata" : m.store_tracked ? '<span class="up">nog niet in winkeldata</span>' : ""}</div></td>
       <td class="hide-s">${esc(m.stores.join(", "))}</td><td class="num">${m.makers}</td><td class="num">${m.posts}</td><td class="num hide-s">${compact(m.engagement)}</td></tr>`).join("")
      : `<tr><td colspan="5" class="muted">Nog geen producten genoemd in deze week.</td></tr>`;
    $("#list-news").innerHTML = d.news.length ? d.news.map(n =>
      `<li><div class="row"><span>${n.url ? `<a href="${esc(n.url)}" target="_blank" rel="noopener">${esc(n.title)}</a>` : esc(n.title)}</span>
       <span class="meta">${esc(n.outlet || "")} · ${ago(n.published_at)}</span></div></li>`).join("")
      : `<li class="meta">Nog geen nieuws opgehaald.</li>`;
  }

  // --- zaken & steden ------------------------------------------------------

  let map, mapLayer;
  async function loadZaken() {
    const win = state.window === "nu" ? "24u" : state.window;
    const d = await api("/api/zaken?" + qs({ window: win }));
    $("#zaken-hint").textContent = `Eetzaken en foodtrucks die in posts genoemd of getagd worden (${win === state.window ? "" : "minimaal 24 uur, "}periode ${win}). Vergeleken met ${d.reviewed_count} zaken die al op Snackspert staan.`;
    $("#tbl-zaken tbody").innerHTML = d.places.length ? d.places.map(p =>
      `<tr class="click" data-topic="zaak|${esc(p.name)}"><td><span class="topic-name">${esc(p.display)}</span> ${pdots(p.platforms)}${p.aliases && p.aliases.length ? `<div class="meta muted">ook: ${esc(p.aliases.join(", "))}</div>` : ""}</td>
       <td class="hide-s">${esc(p.city || "")}</td><td class="num">${p.posts}</td><td class="num">${growth(p)}</td>
       <td>${p.reviewed ? `<span class="badge ok">✓ gereviewd</span>` : `<span class="badge new">reviewkandidaat</span>`}</td></tr>`).join("")
      : `<tr><td colspan="5" class="muted">Nog geen zaken herkend in deze periode.</td></tr>`;

    $("#list-cities").innerHTML = d.cities.slice(0, 12).map(c =>
      `<li><div class="row"><button class="linkish" data-topic="stad|${esc(c.name)}">${esc(c.name)}</button><span class="meta">${c.posts} posts · ${growth(c)}</span></div></li>`).join("")
      || `<li class="meta">Nog geen steden herkend.</li>`;

    if (!window.L) { $("#map").innerHTML = '<div class="empty">Kaart niet beschikbaar (geen internet?).</div>'; return; }
    if (!map) {
      map = L.map("map", { scrollWheelZoom: false }).setView([52.2, 5.3], 7);
      L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
        maxZoom: 13, attribution: "© OpenStreetMap",
      }).addTo(map);
    }
    if (mapLayer) mapLayer.remove();
    mapLayer = L.layerGroup().addTo(map);
    const max = Math.max(1, ...d.cities.map(c => c.posts));
    d.cities.filter(c => c.coords).forEach(c => {
      const color = getComputedStyle(document.documentElement).getPropertyValue("--accent").trim();
      L.circleMarker(c.coords, { radius: 6 + 20 * Math.sqrt(c.posts / max), color: "#fff", weight: 2,
        fillColor: color, fillOpacity: 0.75 })
        .bindTooltip(`${esc(c.name)}: ${c.posts} posts`).on("click", () => openTopic("stad", c.name)).addTo(mapLayer);
    });
    setTimeout(() => map.invalidateSize(), 50);
  }

  // --- bronnen -------------------------------------------------------------

  async function loadSources() {
    const d = await api("/api/sources");
    const counts = {};
    d.sources.forEach(s => (counts[s.status] = (counts[s.status] || 0) + 1));
    const filters = ["actief", "kandidaat", "gepauzeerd", "ongeldig", "afgewezen", "alle"];
    $("#source-filter").innerHTML = filters.map(f =>
      `<button class="chip ${state.sourceFilter === f ? "on" : ""}" data-sf="${f}">${f} ${f === "alle" ? d.sources.length : counts[f] || 0}</button>`).join("");
    $("#graph-info").textContent = state.status?.keys.meta
      ? `Gratis Meta-API: nog ${d.graph_slots_free} van de 30 hashtag-plekken vrij deze week (Meta-limiet). Overige Instagram-hashtags gaan via Apify.`
      : "Tip: met een Meta-sleutel haalt de tool Instagram-hashtags en zakelijke accounts gratis op (zie README).";
    const rows = d.sources.filter(s => state.sourceFilter === "alle" || s.status === state.sourceFilter);
    const badge = { actief: "ok", kandidaat: "new", gepauzeerd: "warn", ongeldig: "bad", afgewezen: "" };
    $("#tbl-sources tbody").innerHTML = rows.length ? rows.map(s => {
      const prefix = s.kind === "hashtag" ? "#" : s.kind === "account" ? "@" : "🔎 ";
      const yieldTxt = s.yield_score == null ? "–" : Math.round(s.yield_score * 100) + "%";
      const actions = [];
      if (s.status !== "actief") actions.push(`<button class="btn small" data-act="actief" data-id="${s.id}">Activeren</button>`);
      if (s.status === "actief") actions.push(`<button class="btn small ghost" data-act="gepauzeerd" data-id="${s.id}">Pauzeren</button>`);
      if (s.status === "kandidaat") actions.push(`<button class="btn small ghost" data-act="afgewezen" data-id="${s.id}">Afwijzen</button>`);
      actions.push(`<button class="btn small ghost" data-del="${s.id}" title="Verwijderen" aria-label="Verwijderen">✕</button>`);
      return `<tr><td><span class="ptag" style="--pc:${PLATFORM[s.platform]?.color}">${esc(PLATFORM[s.platform]?.name)}</span></td>
        <td><span class="topic-name">${prefix}${esc(s.value)}</span>${s.last_error ? `<div class="meta down">${esc(s.last_error.slice(0, 90))}</div>` : ""}</td>
        <td><span class="badge ${badge[s.status] || ""}">${esc(s.status)}</span></td>
        <td class="hide-s"><span class="meta">${esc(s.origin)}${s.reason ? " · " + esc(s.reason) : ""}</span></td>
        <td class="num" title="Aandeel nieuwe, relevante posts per betaald resultaat">${yieldTxt}${s.last_results ? `<div class="meta">${s.last_new}/${s.last_results} nieuw</div>` : ""}</td>
        <td class="num hide-s" title="Kosten per nieuwe relevante post (totaal ${euro2(s.eur_total)})">${s.eur_per_useful != null ? euro2(s.eur_per_useful) : (s.eur_total ? euro2(s.eur_total) + " <span class='meta'>totaal</span>" : "–")}</td>
        <td class="hide-s meta">${s.last_fetched ? ago(s.last_fetched) : "nog niet"}${s.next_due && new Date(s.next_due) > new Date() ? `<div>volgende ${ago(s.next_due)}</div>` : ""}</td>
        <td><div class="toolbar">${actions.join("")}</div></td></tr>`;
    }).join("") : `<tr><td colspan="8" class="muted">Geen bronnen met deze status.</td></tr>`;
  }

  // --- budget & instellingen ------------------------------------------------

  const SETTINGS_FORM = [
    ["Ophalen", [
      ["interval_uren", "Elke … uur ophalen", "number", 1],
      ["maandbudget_eur", "Maandbudget data (Apify), €", "number", 1],
      ["min_per_bron", "Minimaal posts per bron per ronde", "number", 1],
      ["max_per_bron", "Maximaal posts per bron per ronde", "number", 1],
    ]],
    ["Prijzen Apify ($ per 1000 resultaten, zie Pricing-tab van de actor)", [
      ["prijs_instagram_per_1000", "Instagram", "number", 0.01],
      ["prijs_tiktok_per_1000", "TikTok", "number", 0.01],
      ["prijs_facebook_per_1000", "Facebook", "number", 0.01],
      ["eur_per_usd", "Koers: € per $", "number", 0.01],
    ]],
    ["Verdeling budget per ronde (verhouding)", [
      ["verdeling.instagram", "Instagram", "number", 0.05],
      ["verdeling.tiktok", "TikTok", "number", 0.05],
      ["verdeling.facebook", "Facebook", "number", 0.05],
    ]],
    ["Automatisch bronnen ontdekken", [
      ["auto_toevoegen", "Ontdekte bronnen direct activeren", "checkbox"],
      ["max_nieuwe_bronnen_per_run", "Max. nieuwe bronnen per ronde", "number", 1],
      ["max_actieve_bronnen_per_platform", "Max. actieve bronnen per platform", "number", 1],
    ]],
    ["AI-indeling (Claude)", [
      ["ai_aan", "AI gebruiken als er een sleutel is", "checkbox"],
      ["ai_maandbudget_eur", "Maandbudget AI, €", "number", 1],
      ["ai_model", "Model", "select", ["claude-opus-5-5", "claude-sonnet-5-5", "claude-haiku-5-5"]],
      ["ai_effort", "Denkniveau", "select", ["low", "medium", "high"]],
    ]],
    ["Kosten besparen", [
      ["alleen_nieuwe_posts", "Alleen posts sinds de vorige keer opvragen (datumfilter)", "checkbox"],
      ["herhaalmeting_per_ronde", "Snelle posts opnieuw meten (per platform per ronde)", "number", 1],
    ]],
    ["Overig", [
      ["supermarkt_interval_uren", "Supermarkten controleren elke … uur", "number", 1],
      ["supermarkt_aan", "Supermarkten controleren", "checkbox"],
      ["nieuws_aan", "Nieuws ophalen", "checkbox"],
      ["extra_rss", "Extra RSS-feeds (één per regel)", "textarea"],
    ]],
  ];

  async function loadBeheer() {
    const [b, settings, runs] = await Promise.all([api("/api/budget"), api("/api/settings"), api("/api/runs")]);
    const pct = (a, t) => (t ? Math.min(100, (a / t) * 100) : 0);
    const meter = (a, t) => {
      const p = pct(a, t);
      return `<div class="meter ${p >= 100 ? "over" : p >= 80 ? "warn" : ""}"><span style="width:${p}%"></span></div>`;
    };
    const euro = v => "€ " + Number(v || 0).toFixed(2).replace(".", ",");
    $("#budget-kpis").innerHTML = `
      <div class="kpi"><div class="label">Data (Apify) deze maand</div><div class="value">${euro(b.data_uitgegeven_eur)}</div>
        <div class="delta">van ${euro(b.data_budget_eur)}</div>${meter(b.data_uitgegeven_eur, b.data_budget_eur)}</div>
      <div class="kpi"><div class="label">AI deze maand</div><div class="value">${euro(b.ai_uitgegeven_eur)}</div>
        <div class="delta">van ${euro(b.ai_budget_eur)}</div>${meter(b.ai_uitgegeven_eur, b.ai_budget_eur)}</div>
      <div class="kpi"><div class="label">Kosten per nuttige post</div><div class="value">${b.per_nuttige_post_eur != null ? euro2(b.per_nuttige_post_eur) : "–"}</div>
        <div class="delta">${fmt(b.nuttige_posts)} nieuwe relevante NL-posts deze maand · prognose ${euro(b.prognose_eur)}</div></div>
      <div class="kpi"><div class="label">Budget volgende ronde</div><div class="value">${euro(b.per_ronde_eur)}</div>
        <div class="delta">${b.rondes_over} rondes over deze maand · ${Object.entries(b.plan).map(([p, v]) => `${PLATFORM[p].name} ±${v.results}`).join(", ")} posts</div></div>`;

    const form = $("#form-settings");
    const get = k => k.includes(".") ? settings[k.split(".")[0]][k.split(".")[1]] : settings[k];
    form.innerHTML = SETTINGS_FORM.map(([title, fields]) => `<fieldset><legend>${esc(title)}</legend>${fields.map(([k, label, type, opt]) => {
      const v = get(k);
      if (type === "checkbox") return `<label class="check"><input type="checkbox" name="${k}" ${v ? "checked" : ""}> ${esc(label)}</label>`;
      if (type === "select") return `<label>${esc(label)}<select name="${k}">${opt.map(o => `<option ${o === v ? "selected" : ""}>${o}</option>`).join("")}</select></label>`;
      if (type === "textarea") return `<label class="full">${esc(label)}<textarea name="${k}">${esc((v || []).join("\n"))}</textarea></label>`;
      return `<label>${esc(label)}<input type="number" name="${k}" value="${v}" step="${opt}" min="0"></label>`;
    }).join("")}</fieldset>`).join("") +
      `<div class="actions"><button class="btn primary" type="submit">Opslaan</button><span class="muted" id="settings-msg"></span></div>`;

    const k = state.status?.keys || {};
    const keyRow = (ok, name, yes, no) => `<li><div class="row"><span><span class="badge ${ok ? "ok" : "bad"}">${ok ? "✓" : "✗"}</span> <strong>${name}</strong></span></div><div class="meta">${ok ? yes : no}</div></li>`;
    $("#list-keys").innerHTML =
      keyRow(k.apify, "Apify", "TikTok, Facebook en extra Instagram worden opgehaald.", "Zet <code>APIFY_TOKEN</code> in .env voor TikTok en Facebook.") +
      keyRow(k.meta, "Meta Graph API", "Instagram-hashtags en zakelijke accounts gratis.", "Optioneel: <code>META_ACCESS_TOKEN</code> + <code>META_IG_USER_ID</code> bespaart Apify-kosten.") +
      keyRow(k.anthropic, "Claude (AI)", "Herkent producten, zaken en steden in posts.", "Optioneel: <code>ANTHROPIC_API_KEY</code> voor betere herkenning. Zonder werkt de tool op trefwoorden.") +
      keyRow((state.status?.reviewed || 0) > 0, "Snackspert-recensies", `${state.status?.reviewed} zaken bekend.`, "Worden bij de eerste ophaalronde opgehaald van snackspert.nl.");

    $("#list-runs").innerHTML = runs.length ? runs.slice(0, 12).map(r => {
      const cls = { klaar: "ok", deels: "warn", fout: "bad", bezig: "new" }[r.status] || "";
      const cost = (r.cost_usd || 0) + (r.ai_cost_usd || 0);
      return `<li><details><summary><span class="badge ${cls}">${esc(r.status)}</span> ${new Date(r.started_at).toLocaleString("nl-NL", { dateStyle: "short", timeStyle: "short" })}
        · ${fmt(r.results)} resultaten · ${fmt(r.new_posts)} nieuw${cost ? ` · $${cost.toFixed(2)}` : ""} <span class="meta">(${esc(r.trigger)})</span></summary>
        <ul class="log">${(r.log || []).map(l => `<li class="${l.niveau === "fout" ? "down" : ""}">${esc(l.tekst)}</li>`).join("")}</ul></details></li>`;
    }).join("") : `<li class="meta">Nog geen rondes.</li>`;
  }

  async function saveSettings(evt) {
    evt.preventDefault();
    const form = evt.target;
    const out = { verdeling: {} };
    SETTINGS_FORM.forEach(([, fields]) => fields.forEach(([k, , type]) => {
      const input = form.elements[k];
      let v = type === "checkbox" ? input.checked : type === "textarea" ? input.value.split("\n") : input.value;
      if (type === "number") v = Number(v);
      if (k.includes(".")) out.verdeling[k.split(".")[1]] = v; else out[k] = v;
    }));
    try {
      await api("/api/settings", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(out) });
      $("#settings-msg").textContent = "Opgeslagen";
      loadBeheer();
    } catch (e) {
      $("#settings-msg").textContent = e.message;
    }
  }

  // --- navigatie -------------------------------------------------------------

  const LOADERS = { trends: loadTrends, posts: () => loadPosts(), supermarkt: loadSupermarkt, zaken: loadZaken,
    bronnen: loadSources, beheer: loadBeheer };

  function switchTab(tab) {
    state.tab = tab;
    remember();
    $$(".tabs button").forEach(b => b.setAttribute("aria-selected", b.dataset.tab === tab));
    $$(".panel").forEach(p => (p.hidden = p.dataset.panel !== tab));
    $("#filters").hidden = ["bronnen", "beheer"].includes(tab);
    refresh();
  }

  function refresh() {
    const fn = LOADERS[state.tab];
    if (fn) fn().catch(e => toast("Laden mislukt: " + e.message));
  }

  function init() {
    $$(".tabs button").forEach(b => b.addEventListener("click", () => switchTab(b.dataset.tab)));
    $$("#f-window button").forEach(b => {
      b.classList.toggle("on", b.dataset.v === state.window);
      b.addEventListener("click", () => {
        state.window = b.dataset.v;
        $$("#f-window button").forEach(x => x.classList.toggle("on", x === b));
        remember();
        refresh();
      });
    });
    $("#f-platform").value = state.platform;
    $("#f-platform").addEventListener("change", e => { state.platform = e.target.value; remember(); refresh(); });
    $("#f-rel").addEventListener("change", e => { state.minRel = e.target.value; refresh(); });

    $("#type-chips").innerHTML = TYPE_CHIPS.map(([v, l]) => `<button class="chip ${v === state.typeFilter ? "on" : ""}" data-tf="${v}">${l}</button>`).join("");
    $("#type-chips").addEventListener("click", e => {
      const b = e.target.closest("[data-tf]");
      if (!b) return;
      state.typeFilter = b.dataset.tf;
      $$("#type-chips .chip").forEach(c => c.classList.toggle("on", c === b));
      renderTopics();
    });

    document.addEventListener("click", e => {
      const t = e.target.closest("[data-topic]");
      if (t) {
        const [type, ...rest] = t.dataset.topic.split("|");
        openTopic(type, rest.join("|"));
      }
    });
    $("#d-close").addEventListener("click", () => ($("#drawer").hidden = true));
    document.addEventListener("keydown", e => { if (e.key === "Escape") $("#drawer").hidden = true; });

    let debounce;
    $("#p-q").addEventListener("input", () => { clearTimeout(debounce); debounce = setTimeout(() => loadPosts(), 300); });
    $("#p-sort").addEventListener("change", () => loadPosts());
    $("#p-cat").addEventListener("change", () => loadPosts());
    $("#p-more").addEventListener("click", () => loadPosts(true));
    $("#p-cat").innerHTML += ["Friet & frituur", "Burgers", "Shoarma, döner & grill", "Pizza & Italiaans", "Kip", "Aziatisch",
      "Mexicaans & Latijns", "Broodjes & tosti", "Zoet & dessert", "Chips & snacks", "Drinken",
      "Supermarkt & nieuwe producten", "Streetfood & events"].map(c => `<option>${esc(c)}</option>`).join("");

    $("#btn-run").addEventListener("click", async () => {
      try { await api("/api/run", { method: "POST" }); toast("Ophaalronde gestart"); wasRunning = true; poll(); }
      catch (e) { toast(e.message); }
    });
    $("#p-all-products").addEventListener("change", e => { state.allProducts = e.target.checked; loadSupermarkt(); });
    $("#btn-supermarkt").addEventListener("click", async () => {
      try {
        await api("/api/run", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ supermarkt: true }) });
        toast("Ronde gestart, inclusief supermarkten"); wasRunning = true; poll();
      } catch (e) { toast(e.message); }
    });
    $("#btn-clear-demo").addEventListener("click", async () => {
      if (!confirm("Alle demodata wissen?")) return;
      await api("/api/demo/clear", { method: "POST" });
      toast("Demodata gewist");
      await loadStatus();
      refresh();
    });
    $("#form-settings").addEventListener("submit", saveSettings);
    $("#form-source").addEventListener("submit", async e => {
      e.preventDefault();
      const f = e.target;
      try {
        await api("/api/sources", { method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ platform: f.platform.value, kind: f.kind.value, value: f.value.value }) });
        f.value.value = "";
        toast("Bron toegevoegd");
        state.sourceFilter = "actief";
        loadSources();
      } catch (err) { toast(err.message); }
    });
    $("#source-filter").addEventListener("click", e => {
      const b = e.target.closest("[data-sf]");
      if (b) { state.sourceFilter = b.dataset.sf; loadSources(); }
    });
    $("#tbl-sources").addEventListener("click", async e => {
      const act = e.target.closest("[data-act]");
      const del = e.target.closest("[data-del]");
      if (act) {
        await api(`/api/sources/${act.dataset.id}`, { method: "PATCH", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ status: act.dataset.act }) });
        loadSources();
      } else if (del && confirm("Bron verwijderen?")) {
        await api(`/api/sources/${del.dataset.del}`, { method: "DELETE" });
        loadSources();
      }
    });
    window.addEventListener("resize", () => { clearTimeout(init.rt); init.rt = setTimeout(() => state.tab === "trends" && loadTrends(), 250); });

    loadStatus().then(() => switchTab(state.tab));
    setInterval(poll, 15000);
  }

  init();
})();
