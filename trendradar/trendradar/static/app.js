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
    tab: "vandaag", window: "24u", platform: "", minRel: "0.35",
    typeFilter: "", trends: null, posts: { offset: 0, topic: null },
    sourceFilter: "actief", status: null, watch: new Map(), lijstFilter: "open",
    feedback: new Map(), tipsView: "tips", mpYear: null, mpDim: "format", mpTop: "views",
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

  // Alleen echte webadressen als link: een 'javascript:'-link uit een post of feed doet niets.
  const safeHref = u => /^https?:\/\//i.test(u || "") ? esc(u) : "#";

  // Alleen het antwoord op de laatste vraag tekenen: een trager, ouder antwoord mag een nieuwer niet overschrijven.
  const latest = {};
  function ticket(name) {
    const t = (latest[name] = (latest[name] || 0) + 1);
    return () => latest[name] === t;
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
      if (wasRunning && !s.running) { toast("Ophaalronde klaar"); refreshWhenIdle(); }
      wasRunning = s.running;
    } catch (e) { /* server even weg */ }
  }

  // Na een ronde opnieuw laden, maar niet terwijl je een notitie of instelling typt: dan pas als je klaar bent.
  function refreshWhenIdle() {
    const el = document.activeElement;
    if (el?.matches("input, textarea, select") && el.closest(".panel:not([hidden])")) {
      if (!refreshWhenIdle.waiting) {
        refreshWhenIdle.waiting = true;
        el.addEventListener("blur", () => { refreshWhenIdle.waiting = false; setTimeout(refresh, 300); }, { once: true });
      }
      return;
    }
    refresh();
  }

  // --- trends -------------------------------------------------------------

  async function loadTrends() {
    const fresh = ticket("trends");
    const d = await api("/api/trends?" + qs());
    if (!fresh()) return;
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
        <div class="meta">${esc((p.summary || p.text || "").slice(0, 120))}${p.url ? ` · <a href="${safeHref(p.url)}" target="_blank" rel="noopener">bekijk</a>` : ""}</div></li>`;
    }).join("") : `<li class="meta">Geen doorbraken in deze periode.</li>`;

    $("#list-rising").innerHTML = d.rising_posts.length ? d.rising_posts.slice(0, 6).map(p =>
      `<li><div class="row"><span><span class="ptag" style="--pc:${PLATFORM[p.platform]?.color}">${esc(PLATFORM[p.platform]?.name)}</span> @${esc(p.author || "?")}</span>
       <span class="meta up">+${fmt(p.gain_per_hour)}/uur</span></div>
       <div class="meta">${esc((p.summary || p.text || "").slice(0, 110))}${p.url ? ` · <a href="${safeHref(p.url)}" target="_blank" rel="noopener">bekijk</a>` : ""}</div></li>`).join("")
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
    tbody.innerHTML = rows.length ? "" : `<tr><td colspan="10" class="muted">Geen onderwerpen gevonden. Probeer een langere periode of strengheid 'Breed'.</td></tr>`;
    rows.forEach((t, i) => {
      const tr = document.createElement("tr");
      tr.className = "click";
      tr.innerHTML = `<td class="rank">${i + 1}</td>
        <td><span class="badge">${esc(t.type_label)}</span><span class="topic-name">${esc(t.name)}</span></td>
        <td class="hide-s spark"></td>
        <td class="num">${fmt(t.posts)}</td><td class="num">${growth(t)}</td><td>${phaseBadge(t.phase)}</td>
        <td class="num hide-s">${makers(t)}</td><td class="hide-s">${sigChips(t.signals)}</td>
        <td class="hide-s">${pdots(t.platforms)}</td><td>${starBtn("onderwerp", t.type + "|" + t.name, t.name)}</td>`;
      tr.querySelector(".spark").appendChild(sparkline(t.series, d.baseline_buckets));
      tr.addEventListener("click", e => {
        if (!e.target.closest("button, a, select, textarea, input")) openTopic(t.type, t.name);
      });
      tbody.appendChild(tr);
    });
  }

  // --- onderwerp-detail ---------------------------------------------------

  async function openTopic(type, name) {
    const fresh = ticket("topic");
    const drawer = $("#drawer");
    drawer.hidden = false;
    $("#d-title").textContent = name;
    $("#d-type").textContent = (TYPE_CHIPS.find(c => c[0] === type) || [, type])[1];
    $("#d-chart").innerHTML = '<div class="empty">Laden…</div>';
    ["#d-posts", "#d-meta", "#d-related"].forEach(id => ($(id).innerHTML = ""));
    const dstar = $("#d-star");
    const watchedTopic = state.watch.get(`onderwerp|${type}|${name}`);
    dstar.textContent = watchedTopic ? "★ Bewaard" : "☆ Bewaren";
    dstar.onclick = async () => {
      await toggleWatch({ kind: "onderwerp", ref: `${type}|${name}`, title: name });
      dstar.textContent = state.watch.get(`onderwerp|${type}|${name}`) ? "★ Bewaard" : "☆ Bewaren";
    };
    $("#d-all").onclick = () => {
      drawer.hidden = true;
      state.posts.topic = { type, name };
      $("#p-q").value = "";
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

    const win = state.window === "nu" ? "24u" : state.window;
    let d;
    try {
      d = await api("/api/topic?" + new URLSearchParams({ type, name, window: win, min_rel: state.minRel }));
    } catch (e) {
      if (fresh()) $("#d-chart").innerHTML = `<div class="empty">Laden mislukt: ${esc(e.message)}</div>`;
      return;
    }
    if (!fresh()) return;  // intussen een ander onderwerp aangeklikt
    columnChart($("#d-chart"), d.labels, d.series, { currentFrom: d.current_from, label: `Posts over ${name}` });
    $("#d-meta").innerHTML = `<span class="chip static">${d.total} posts</span><span class="chip static">${d.makers} makers</span>` +
      (d.signals ? sigChips(d.signals) : "") +
      Object.entries(d.platforms).map(([p, n]) => `<span class="chip static"><span class="pdot" style="--c:${PLATFORM[p]?.color}"></span> ${esc(PLATFORM[p]?.name || p)} ${n}</span>`).join("");
    $("#d-related").innerHTML = d.related.length ? d.related.map(([t, n]) =>
      `<button class="chip" data-topic="hashtag|${esc(t)}">${esc(t)} · ${n}</button>`).join("") : '<span class="muted">–</span>';
    $("#d-posts").innerHTML = d.posts.map(postCard).join("");
  }

  function postCard(p) {
    const plat = PLATFORM[p.platform] || { name: p.platform, color: "var(--muted)" };
    const metrics = [];
    if (p.likes) metrics.push(`♥ ${compact(p.likes)}`);
    if (p.comments) metrics.push(`💬 ${compact(p.comments)}`);
    if (p.shares) metrics.push(`↗ ${compact(p.shares)}`);
    if (p.views) metrics.push(`▶ ${compact(p.views)}`);
    // Kandidaten hebben al redenen (doorbraak, n× views); dan geen dubbele signaalchips.
    const sig = p.signals && !p.reasons ? sigChips(p.signals, { reach: true }) : "";
    const flags = (p.flags || []).map(f => f === "nieuw_op_kaart"
      ? `<span class="sig hot">🆕 Nieuw op de kaart</span>`
      : f.startsWith("combinatie:") ? `<span class="sig hot">🧪 ${esc(f.slice(11))}</span>`
      : f.startsWith("twist:") ? `<span class="sig hot">🔄 ${esc(f.slice(6))}</span>` : "").join("");
    const reasons = p.reasons ? `<div class="reasons">${p.reasons
      .filter(r => !r.startsWith("Combinatie") && !r.startsWith("Twist") && r !== "Nieuw op de kaart")
      .map(r => `<span class="reason ${r.startsWith("Past bij") ? "taste" : r.startsWith("Jouw publiek") ? "taste" : r.startsWith("Al gepost") ? "done" : ""}">${r.startsWith("Past bij") ? "⭐ " : r.startsWith("Jouw publiek") ? "📈 " : ""}${esc(r)}</span>`).join("")}</div>` : "";
    const title = (p.summary || p.text || "").replace(/\s+/g, " ").slice(0, 90);
    const tags = [...(p.categories || []), ...(p.brands || []).slice(0, 2)].slice(0, 4)
      .map(c => `<span class="badge">${esc(c)}</span>`).join("");
    const thumb = p.thumbnail ? `<img src="${esc(p.thumbnail)}" alt="" loading="lazy" referrerpolicy="no-referrer" onerror="this.remove()">` : "";
    return `<article class="post ${state.feedback.get(p.id) === -1 ? "disliked" : ""}" data-post="${esc(p.id)}">
      <div class="post-head"><span><span class="ptag" style="--pc:${plat.color}">${esc(plat.name)}</span> · <strong>${p.platform === "nieuws" ? esc(p.author || "") : "@" + esc(p.author || "onbekend")}</strong></span>
      <span class="post-actions"><span title="${esc(new Date(p.posted_at).toLocaleString("nl-NL"))}">${ago(p.posted_at)}</span>
      ${p.platform !== "nieuws" ? fbBtns(p.id) + starBtn("post", p.id, title, p.url, p.city) : ""}</span></div>
      ${flags ? `<div class="sigs">${flags}</div>` : ""}${reasons}
      ${sig}
      ${p.summary ? `<div class="post-sum">${esc(p.summary)}</div>` : ""}
      <div class="post-body">${thumb}<div class="post-text">${esc(p.text)}</div></div>
      <div>${tags}${p.city ? `<span class="badge">📍 ${esc(p.city)}</span>` : ""}${p.demo ? '<span class="badge warn">demo</span>' : ""}</div>
      <div class="post-foot">${metrics.join(" ")}<span>relevantie ${Math.round((p.relevance || 0) * 100)}%</span>
      ${p.url ? `<a href="${safeHref(p.url)}" target="_blank" rel="noopener">Open ↗</a>` : ""}</div>
    </article>`;
  }

  // --- posts --------------------------------------------------------------

  async function loadPosts(append = false) {
    const fresh = ticket("posts");
    const more = $("#p-more");
    more.disabled = true;  // twee keer 'Meer laden' gaf dubbele posts
    const offset = append ? state.posts.offset : 0;
    const extra = { sort: $("#p-sort").value, offset, limit: 60 };
    const q = $("#p-q").value.trim();
    if (q) extra.q = q;
    if ($("#p-cat").value) extra.category = $("#p-cat").value;
    const topic = state.posts.topic;
    if (topic?.ids) extra.ids = topic.ids.join(",");
    else if (topic) { extra.topic_type = topic.type; extra.topic = topic.name; }
    try {
      const d = await api("/api/posts?" + qs(extra));
      if (!fresh()) return;
      const note = $("#p-topic");
      note.hidden = !topic;
      if (topic) {
        note.innerHTML = `${topic.ids ? "Posts over" : "Gefilterd op"} <strong>${esc(topic.name)}</strong> · <button class="btn small ghost" id="p-untopic">filter weghalen</button>`;
        $("#p-untopic").onclick = () => { state.posts.topic = null; loadPosts(); };
      }
      const html = d.posts.map(postCard).join("");
      if (append) $("#posts").insertAdjacentHTML("beforeend", html);
      else $("#posts").innerHTML = html || '<p class="muted">Geen posts gevonden.</p>';
      state.posts.offset = offset + d.posts.length;
      $("#p-count").textContent = `${fmt(d.total)} posts`;
      more.hidden = state.posts.offset >= d.total;
    } finally {
      if (fresh()) more.disabled = false;
    }
  }

  // --- supermarkt ---------------------------------------------------------

  async function loadSupermarkt() {
    const fresh = ticket("supermarkt");
    const d = await api("/api/supermarkt?" + qs(state.allProducts ? { alles: "1" } : {}));
    if (!fresh()) return;
    const st = Object.entries(d.status || {});
    $("#store-status").innerHTML = st.length ? st.map(([store, s]) =>
      `<span class="chip static"><span class="badge ${s.ok ? "ok" : s.stil ? "warn" : "bad"}">${s.ok ? "✓ werkt" : s.stil ? "⚠ staat stil" : "✗ storing"}</span>${esc(store)}: ${esc(s.melding)} · ${ago(s.t)}</span>`).join("")
      : `<span class="chip static">Het assortiment van AH, Jumbo, Lidl, Plus en andere winkels wordt twee keer per dag vergeleken (eerste keer bij de eerstvolgende ronde).</span>`;
    $("#list-tests").innerHTML = testIdeas(d.test_ideas,
      "Nog geen kandidaten. Zodra er nieuwe snackproducten in het schap komen, zet de tool de beste hier.");
    const CONF = { winkel: "🏪 winkel", social: "📱 social", nieuws: "📰 nieuws" };
    $("#list-early").innerHTML = d.early.length ? d.early.map(m =>
      `<li><div class="row"><button class="linkish" data-topic="product|${esc(m.name)}">${esc(m.name)}</button>
        <span class="meta">${m.makers} maker${m.makers === 1 ? "" : "s"} · ${m.posts} posts</span></div>
        <div class="meta">${esc(m.stores.join(", ") || "winkel onbekend")} · eerst gezien ${ago(m.first)} ${pdots(m.platforms)}
        ${m.store_tracked ? '<span class="badge new">nog niet in winkeldata</span>' : '<span class="badge">geen winkeldata voor deze winkel</span>'}</div></li>`).join("")
      : `<li class="meta">Geen vroege signalen deze week.</li>`;
    $("#tbl-products tbody").innerHTML = d.products.length ? d.products.map(p =>
      `<tr><td><span class="topic-name">${p.url ? `<a href="${safeHref(p.url)}" target="_blank" rel="noopener">${esc(p.name)}</a>` : esc(p.name)}</span>${p.demo ? ' <span class="badge warn">demo</span>' : ""}<div class="meta muted">${esc(p.brand || "")}</div></td>
       <td>${esc(p.store)}</td><td class="hide-s">${esc(p.size || p.category || "")}</td>
       <td class="num">${p.price != null ? "€ " + Number(p.price).toFixed(2).replace(".", ",") : "–"}</td>
       <td>${dateNl(p.first_seen)}</td>
       <td><span class="sigs">${p.confirmed_by.map(c => `<span class="sig ${c !== "winkel" ? "hot" : ""}">${CONF[c]}${c === "social" ? " " + p.social_makers : ""}</span>`).join("")}</span></td>
       <td>${starBtn("product", p.id, `${p.name} (${p.store})`, p.url)}</td></tr>`).join("")
      : `<tr><td colspan="7" class="muted">Nog geen nieuwe producten. De eerste controle legt alleen vast wat er ligt; daarna verschijnen nieuwkomers hier.</td></tr>`;
    $("#tbl-mentioned tbody").innerHTML = d.mentioned.length ? d.mentioned.map(m =>
      `<tr class="click" data-topic="product|${esc(m.name)}"><td><span class="topic-name">${esc(m.name)}</span> ${pdots(m.platforms)}
       <div class="meta">${m.in_store ? "in winkeldata" : m.store_tracked ? '<span class="up">nog niet in winkeldata</span>' : ""}</div></td>
       <td class="hide-s">${esc(m.stores.join(", "))}</td><td class="num">${m.makers}</td><td class="num">${m.posts}</td><td class="num hide-s">${compact(m.engagement)}</td></tr>`).join("")
      : `<tr><td colspan="5" class="muted">Nog geen producten genoemd in deze week.</td></tr>`;
    $("#list-news").innerHTML = d.news.length ? d.news.map(n =>
      `<li><div class="row"><span>${n.url ? `<a href="${safeHref(n.url)}" target="_blank" rel="noopener">${esc(n.title)}</a>` : esc(n.title)}</span>
       <span class="meta">${esc(n.outlet || "")} · ${ago(n.published_at)}</span></div></li>`).join("")
      : `<li class="meta">Nog geen nieuws opgehaald.</li>`;
  }

  // --- zaken & steden ------------------------------------------------------

  let map, mapLayer;
  async function loadZaken() {
    const fresh = ticket("zaken");
    const win = state.window === "nu" ? "24u" : state.window;
    const d = await api("/api/zaken?" + qs({ window: win }));
    if (!fresh()) return;
    $("#zaken-hint").textContent = `Eetzaken en foodtrucks die in posts genoemd of getagd worden (${win === state.window ? "" : "minimaal 24 uur, "}periode ${win}). Vergeleken met ${d.reviewed_count} zaken die al op Snackspert staan.`;
    $("#tbl-zaken tbody").innerHTML = d.places.length ? d.places.map(p =>
      `<tr class="click" data-topic="zaak|${esc(p.name)}"><td><span class="topic-name">${esc(p.display)}</span> ${pdots(p.platforms)}${p.aliases && p.aliases.length ? `<div class="meta muted">ook: ${esc(p.aliases.join(", "))}</div>` : ""}</td>
       <td class="hide-s">${esc(p.city || "")}</td><td class="num">${p.posts}</td><td class="num">${growth(p)}</td>
       <td>${zaakBadges(p, "reviewkandidaat")}</td>
       <td><span class="post-actions">${tipBtn(p.display, p.city, p.tip)}${starBtn("zaak", p.name, p.display, null, p.city)}</span></td></tr>`).join("")
      : `<tr><td colspan="6" class="muted">Nog geen zaken herkend in deze periode.</td></tr>`;

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
      ["verdeling_automatisch", "Automatisch bijsturen naar wat per euro het meest oplevert", "checkbox"],
      ["verdeling.instagram", "Instagram", "number", 0.05],
      ["verdeling.tiktok", "TikTok", "number", 0.05],
      ["verdeling.facebook", "Facebook", "number", 0.05],
    ]],
    ["Automatisch bronnen ontdekken", [
      ["auto_toevoegen", "Ontdekte bronnen direct activeren", "checkbox"],
      ["max_nieuwe_bronnen_per_run", "Max. nieuwe bronnen per ronde", "number", 1],
      ["max_actieve_bronnen_per_platform", "Max. actieve bronnen per platform", "number", 1],
    ]],
    ["Routes", [
      ["thuisbasis", "Thuisbasis (vanaf hier rekent de tool routes)", "text"],
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
    ["Nieuwe zaken via Google Maps (Apify, ± 1 dollar per week)", [
      ["maps_aan", "Elke week zoeken naar nieuwe zaken", "checkbox"],
      ["maps_steden_per_week", "Steden per week", "number", 1],
      ["maps_steden", "Steden, op rij af (één per regel)", "textarea"],
      ["maps_zoektermen", "Zoektermen (één per regel)", "textarea"],
    ]],
    ["Mijn posts automatisch bijwerken (Apify, ± 2 cent per week)", [
      ["eigen_instagram", "Je Instagram-account (zonder @, leeg = uit)", "text"],
      ["eigen_posts_dagen", "Elke … dagen", "number", 1],
    ]],
    ["Onderhoud", [
      ["bewaar_maanden", "Posts bewaren (maanden, 0 = altijd)", "number", 1],
      ["backup_dagen", "Back-up elke … dagen", "number", 1],
      ["backup_map", "Back-upmap (leeg = Google Drive-map 'Snackspert Trendradar')", "text"],
    ]],
    ["Supermarkten via Apify (AH, Jumbo, Plus, Lidl, Aldi, Dirk, Vomar · ± 3,50 dollar per keer, op de achtergrond)", [
      ["supermarkt_apify_aan", "Deze winkels zelf doorzoeken via Apify", "checkbox"],
      ["supermarkt_tijden", "Vaste tijden (één per regel, bijv. 'maandag 07:00')", "textarea"],
      ["supermarkt_per_zoekwoord", "Producten per zoekwoord per winkel", "number", 1],
      ["supermarkt_apify_winkels", "Winkelcodes (één per regel)", "textarea"],
      ["supermarkt_zoektermen", "Zoekwoorden (één per regel)", "textarea"],
    ]],
    ["Overig", [
      ["supermarkt_interval_uren", "Supermarkten controleren elke … uur", "number", 1],
      ["supermarkt_aan", "Supermarkten controleren", "checkbox"],
      ["nieuws_aan", "Nieuws ophalen", "checkbox"],
      ["extra_rss", "Extra RSS-feeds (één per regel)", "textarea"],
    ]],
  ];

  async function loadBeheer() {
    const [b, settings, runs, ond] = await Promise.all([api("/api/budget"), api("/api/settings"), api("/api/runs"),
      api("/api/onderhoud")]);
    const last = ond.last;
    $("#backup-info").innerHTML = (last ? `Laatste back-up: <b>${new Date(last.at).toLocaleString("nl-NL", { dateStyle: "medium", timeStyle: "short" })}</b> (${String(last.mb).replace(".", ",")} MB)`
      : "Nog geen back-up gemaakt.") + `<br>Map: <code>${esc(ond.folder)}</code>`
      + (ond.drive ? " ✓ Google Drive" : `<br><b>Nog niet in Google Drive.</b> Open op je Chromebook de app <em>Bestanden</em>, ga naar Google Drive > Mijn Drive, klik met rechts op de map <em>${esc(ond.drive_folder)}</em> en kies <em>Delen met Linux</em>. Daarna gaan de back-ups vanzelf naar Drive.`)
      + (ond.cleanup ? `<br>Laatst opgeruimd: ${fmt(ond.cleanup.posts)} oude posts, ${ago(ond.cleanup.at)}.` : "")
      + "<br>De tool maakt elke week een back-up en bewaart de laatste acht.";
    const pct = (a, t) => (t ? Math.min(100, (a / t) * 100) : 0);
    const meter = (a, t) => {
      const p = pct(a, t);
      return `<div class="meter ${p >= 100 ? "over" : p >= 80 ? "warn" : ""}"><span style="width:${p}%"></span></div>`;
    };
    const euro = v => "€ " + Number(v || 0).toFixed(2).replace(".", ",");
    $("#budget-kpis").classList.toggle("kpis-5", !!b.apify_account);
    $("#budget-kpis").innerHTML = `
      <div class="kpi"><div class="label">Data (Apify) deze maand</div><div class="value">${euro(b.data_uitgegeven_eur)}</div>
        <div class="delta">van ${euro(b.data_budget_eur)}</div>${meter(b.data_uitgegeven_eur, b.data_budget_eur)}</div>
      <div class="kpi"><div class="label">AI deze maand</div><div class="value">${euro(b.ai_uitgegeven_eur)}</div>
        <div class="delta">van ${euro(b.ai_budget_eur)}</div>${meter(b.ai_uitgegeven_eur, b.ai_budget_eur)}</div>
      <div class="kpi"><div class="label">Kosten per nuttige post</div><div class="value">${b.per_nuttige_post_eur != null ? euro2(b.per_nuttige_post_eur) : "–"}</div>
        <div class="delta">${fmt(b.nuttige_posts)} nieuwe relevante NL-posts deze maand · prognose ${euro(b.prognose_eur)}</div></div>
      ${b.apify_account ? (() => {
        const a = b.apify_account, low = a.limit_usd - a.used_usd < 0.05;
        const toolUsd = b.data_budget_eur / 0.92;
        return `<div class="kpi"><div class="label">Apify-account deze maand</div><div class="value ${low ? "down" : ""}">$ ${a.used_usd.toFixed(2).replace(".", ",")}</div>
          <div class="delta">van $ ${a.limit_usd.toFixed(2).replace(".", ",")} tegoed${a.cycle_end ? ` · nieuw tegoed ${new Date(a.cycle_end).toLocaleDateString("nl-NL", { day: "numeric", month: "long" })}` : ""}
          ${a.limit_usd + 0.5 < toolUsd ? `<br><b>Let op:</b> je Apify-tegoed is lager dan het budget in de tool. Verhoog het tegoed bij Apify (Billing), of verlaag het maandbudget hieronder.` : ""}</div>
          ${meter(a.used_usd, a.limit_usd)}</div>`;
      })() : ""}
      <div class="kpi"><div class="label">Budget volgende ronde</div><div class="value">${euro(b.per_ronde_eur)}</div>
        <div class="delta">${b.rondes_over} rondes over deze maand · ${Object.entries(b.plan).map(([p, v]) => `${PLATFORM[p].name} ±${v.results}`).join(", ")} posts</div>
        <div class="delta" title="Nuttige posts per dollar, sinds het begin">Verdeling nu: ${Object.entries(b.verdeling).map(([p, v]) =>
          `${PLATFORM[p].name} ${v}%${v !== b.verdeling_ingesteld[p] ? ` <small class="${v > b.verdeling_ingesteld[p] ? "up" : "down"}">(ingesteld ${b.verdeling_ingesteld[p]}%)</small>` : ""}${b.rendement[p]?.per_usd != null ? ` · ${String(b.rendement[p].per_usd).replace(".", ",")}/$` : ""}`).join(" · ")}</div></div>`;

    const form = $("#form-settings");
    const get = k => k.includes(".") ? settings[k.split(".")[0]][k.split(".")[1]] : settings[k];
    form.innerHTML = SETTINGS_FORM.map(([title, fields]) => `<fieldset><legend>${esc(title)}</legend>${fields.map(([k, label, type, opt]) => {
      const v = get(k);
      if (type === "checkbox") return `<label class="check"><input type="checkbox" name="${k}" ${v ? "checked" : ""}> ${esc(label)}</label>`;
      if (type === "select") return `<label>${esc(label)}<select name="${k}">${opt.map(o => `<option ${o === v ? "selected" : ""}>${o}</option>`).join("")}</select></label>`;
      if (type === "text") return `<label>${esc(label)}<input type="text" name="${k}" value="${esc(v || "")}"></label>`;
      if (type === "textarea") return `<label class="full">${esc(label)}<textarea name="${k}">${esc((v || []).join("\n"))}</textarea></label>`;
      return `<label>${esc(label)}<input type="number" name="${k}" value="${v}" step="${opt}" min="0"></label>`;
    }).join("")}</fieldset>`).join("") +
      `<div class="actions"><button class="btn primary" type="submit">Opslaan</button><span class="muted" id="settings-msg"></span></div>`;

    const k = state.status?.keys || {};
    // Optionele koppelingen zijn geen fout als ze ontbreken: grijs streepje in plaats van rood kruis.
    const keyRow = (ok, name, yes, no, optional = false) => `<li><div class="row"><span><span class="badge ${ok ? "ok" : optional ? "" : "bad"}">${ok ? "✓" : optional ? "–" : "✗"}</span> <strong>${name}</strong>${!ok && optional ? ' <span class="muted">niet gekoppeld, optioneel</span>' : ""}</span></div><div class="meta">${ok ? yes : no}</div></li>`;
    $("#list-keys").innerHTML =
      keyRow(k.apify, "Apify", "TikTok, Facebook en Instagram worden opgehaald.", "Zet <code>APIFY_TOKEN</code> in .env voor TikTok, Facebook en Instagram.") +
      keyRow(k.meta, "Meta Graph API", "Instagram-hashtags en zakelijke accounts gratis.", "Niet nodig: Instagram loopt via Apify. Met <code>META_ACCESS_TOKEN</code> + <code>META_IG_USER_ID</code> zou je een paar euro per maand besparen.", true) +
      keyRow(k.anthropic, "Claude (AI)", "Herkent producten, zaken en steden in posts die de trefwoorden missen.", "Niet nodig: de tool werkt op trefwoorden. Met <code>ANTHROPIC_API_KEY</code> herkent hij zaken, producten en steden beter, binnen het AI-budget hieronder.", true) +
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
      if (type === "number" && input.value.trim() === "") return;  // leeg gelaten: oude waarde houden, niet 0
      let v = type === "checkbox" ? input.checked : type === "textarea" ? input.value.split("\n") : input.value;
      if (type === "number") v = Number(v);
      if (k.includes(".")) out.verdeling[k.split(".")[1]] = v; else out[k] = v;
    }));
    try {
      await api("/api/settings", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(out) });
      await loadBeheer();  // tekent het formulier opnieuw, dus de melding pas daarna
      $("#settings-msg").textContent = "Opgeslagen";
    } catch (e) {
      $("#settings-msg").textContent = e.message;
    }
  }

  // --- bewaren (Mijn lijst) ---------------------------------------------------

  const PHASES = { vroeg: "🌱 Vroeg", groeit: "📈 Groeit", piek: "🔥 Piek", over: "📉 Over hoogtepunt" };
  const phaseBadge = p => p ? `<span class="phase ${p}">${PHASES[p] || p}</span>` : "";

  function starBtn(kind, ref, title, url, city) {
    const on = state.watch.has(`${kind}|${ref}`);
    return `<button class="star ${on ? "on" : ""}" title="${on ? "Bewaard in Mijn lijst" : "Bewaren in Mijn lijst"}"
      aria-label="Bewaren" data-kind="${esc(kind)}" data-ref="${esc(ref)}" data-title="${esc(title || ref)}"
      data-url="${esc(url || "")}" data-city="${esc(city || "")}">${on ? "★" : "☆"}</button>`;
  }

  async function loadWatch() {
    try {
      const d = await api("/api/lijst");
      state.watch = new Map(d.items.map(i => [`${i.kind}|${i.ref}`, i]));
      state.statuses = d.statuses;
      const open = d.items.filter(i => !["gereviewd", "afgevallen"].includes(i.status)).length
        + d.tips.length + d.routes.length;
      $("#lijst-count").textContent = open ? `(${open})` : "";
      return d;
    } catch (e) { return { items: [], statuses: [], tips: [], routes: [], tip_statuses: [] }; }
  }

  async function toggleWatch(item) {
    const existing = state.watch.get(`${item.kind}|${item.ref}`);
    if (existing) {
      await api(`/api/lijst/${existing.id}`, { method: "DELETE" });
      toast("Uit je lijst gehaald");
    } else {
      await api("/api/lijst", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(item) });
      toast("Bewaard in Mijn lijst");
    }
    await loadWatch();
  }

  async function loadLijst() {
    await state.pendingNote;  // een notitie die net is weggeklikt eerst opslaan
    const d = await loadWatch();
    const filters = [["open", "Open"], ...d.statuses.map(st => [st, st]), ["alle", "Alle"]];
    $("#lijst-filter").innerHTML = filters.map(([v, l]) =>
      `<button class="chip ${state.lijstFilter === v ? "on" : ""}" data-lf="${esc(v)}">${esc(l)}</button>`).join("");
    const rows = d.items.filter(i => state.lijstFilter === "alle" ? true
      : state.lijstFilter === "open" ? !["gereviewd", "afgevallen"].includes(i.status) : i.status === state.lijstFilter);
    const KIND = { post: "Post", zaak: "Zaak", product: "Product", onderwerp: "Onderwerp" };
    $("#tbl-lijst tbody").innerHTML = rows.length ? rows.map(i => {
      const open = i.kind === "onderwerp" ? `data-topic="${esc(i.ref)}"` : "";
      const title = i.url ? `<a href="${safeHref(i.url)}" target="_blank" rel="noopener">${esc(i.title)}</a>`
        : i.kind === "onderwerp" ? `<button class="linkish" ${open}>${esc(i.title)}</button>` : esc(i.title);
      return `<tr><td><span class="topic-name">${title}</span>${i.city ? `<div class="meta">📍 ${esc(i.city)}</div>` : ""}</td>
        <td class="hide-s"><span class="badge">${KIND[i.kind] || i.kind}</span></td>
        <td><select data-status="${i.id}" aria-label="Status">${d.statuses.map(st => `<option ${st === i.status ? "selected" : ""}>${st}</option>`).join("")}</select></td>
        <td><textarea class="note-input" rows="1" data-note="${i.id}" placeholder="Notitie…">${esc(i.note || "")}</textarea></td>
        <td class="hide-s meta">${ago(i.added_at)}</td>
        <td><button class="btn small ghost" data-wdel="${i.id}" aria-label="Verwijderen">✕</button></td></tr>`;
    }).join("") : `<tr><td colspan="6" class="muted">Nog niets bewaard. Klik op ☆ bij een post, zaak, product of onderwerp.</td></tr>`;
    renderPlan(d);
  }

  // Mijn plan: tips en routes op 'te proberen' of 'gepland'.
  function renderPlan(d) {
    const st = d.tip_statuses;
    $("#tbl-plan tbody").innerHTML = d.tips.length ? d.tips.map(x => `<tr>
      <td><a class="tip-name" href="${safeHref(x.maps)}" target="_blank" rel="noopener">${esc(x.name)}</a>
        <div class="meta">${esc([x.place, x.region].filter(Boolean).join(" · "))}</div></td>
      <td>${esc(x.specialty || "")}</td>
      <td>${statusSelect("data-plan-tip", x.id, x.status, st)}</td>
      <td class="hide-s meta">${esc(x.note || "")}</td></tr>`).join("")
      : `<tr><td colspan="4" class="muted">Nog geen tips in je plan. Zet bij Tips &amp; routes of Viral-potentie een zaak op 'te proberen'.</td></tr>`;
    $("#plan-routes").innerHTML = d.routes.map(x => `<div class="route">
      <h3>${esc(x.name)}</h3>
      <div class="meta">${esc(x.region)}${x.km ? " · " + esc(x.km) + " retour" : ""}${x.duration ? " · " + esc(x.duration) + " rijden" : ""}</div>
      <ol>${x.stops.map(s => `<li><b>${esc(s.name)}</b>${s.place ? ` <span class="muted">(${esc(s.place)})</span>` : ""}</li>`).join("")}</ol>
      <div class="foot"><a class="btn small primary" href="${safeHref(x.maps)}" target="_blank" rel="noopener">Route in Google Maps ↗</a>
      ${statusSelect("data-plan-route", x.id, x.status, st)}</div></div>`).join("");
  }

  // --- vandaag ---------------------------------------------------------------

  function newsList(items, empty) {
    return items.length ? items.map(n =>
      `<li><div class="row"><span>${n.url ? `<a href="${safeHref(n.url)}" target="_blank" rel="noopener">${esc(n.title)}</a>` : esc(n.title)}</span>
       <span class="meta">${esc(n.outlet || "")} · ${ago(n.published_at)}</span></div></li>`).join("")
      : `<li class="meta">${empty}</li>`;
  }

  function miniCandidates(items, empty) {
    return items.length ? items.map(p =>
      `<li><div class="row"><span><span class="ptag" style="--pc:${PLATFORM[p.platform]?.color}">${esc(PLATFORM[p.platform]?.name)}</span> @${esc(p.author || "?")}</span>
       <span class="post-actions">${fbBtns(p.id)}${starBtn("post", p.id, (p.summary || p.text || "").slice(0, 90), p.url, p.city)}</span></div>
       <div class="reasons">${(p.reasons || []).map(r => `<span class="reason">${esc(r)}</span>`).join("")}</div>
       <div class="meta">${esc((p.summary || p.text || "").slice(0, 110))}${p.url ? ` · <a href="${safeHref(p.url)}" target="_blank" rel="noopener">bekijk</a>` : ""}</div></li>`).join("")
      : `<li class="meta">${empty}</li>`;
  }

  async function loadVandaag() {
    const d = await api("/api/vandaag");
    $("#v-candidates").innerHTML = d.candidates.length ? d.candidates.map(postCard).join("")
      : '<p class="muted">Nog geen kandidaten. Na een paar ophaalrondes verschijnen hier posts met een nieuwe creatie of een kleine viral.</p>';
    const SOORT = { zin: "zin", twist: "twist", combinatie: "combinatie", snack: "snack", zaak: "zaak",
      maker: "maker", label: "soort vondst" };
    $("#v-learned").innerHTML = d.learned.length ? d.learned.map(l =>
      `<span class="sig" title="${esc(SOORT[l.soort] || l.soort)}, weegt ${String(l.keer).replace(".", ",")} mee">${esc(l.kenmerk)}</span>`).join("")
      : '<span class="meta">Nog niets geleerd. Geef posts een ♥ of 👎, bewaar ze met ☆, of importeer je tips en posts.</span>';
    const lf = d.learned_from;
    $("#v-learned-from").textContent = `Op basis van ${lf.lijst} bewaard · ${lf.likes} ♥ · ${lf.dislikes} 👎 · ${fmt(lf.tips)} tips · ${fmt(lf.eigen_posts)} eigen posts`;
    $("#v-audience").innerHTML = d.audience.length ? `<p class="hint">📈 Jouw publiek kijkt het meest naar:</p>
      <div class="sigs">${d.audience.map(a => `<span class="reason taste" title="${a.posts} posts, mediaan ${fmt(a.median_views)} views">${esc(a.snack)} ${String(a.lift).replace(".", ",")}×</span>`).join("")}</div>` : "";
    $("#v-tips-card").hidden = !d.tips_in_radar.length;
    $("#v-tips").innerHTML = d.tips_in_radar.map(t =>
      `<li><div class="row"><span class="tip-name">${esc(t.name)}</span><span class="badge new">🔥 ${t.radar.posts} ${t.radar.posts === 1 ? "post" : "posts"}</span></div>
       <div class="meta">${esc([t.place, t.specialty].filter(Boolean).join(" · "))} · ${esc(t.status)} ·
       <button class="linkish" data-posts="${esc(t.radar.post_ids.join(","))}" data-label="${esc(t.name)}">bekijk posts</button></div></li>`).join("");
    $("#v-early").innerHTML = d.early_topics.length ? d.early_topics.map(t =>
      `<li><div class="row"><button class="linkish" data-topic="${esc(t.type)}|${esc(t.name)}">${esc(t.name)}</button>
       <span>${phaseBadge(t.phase)} ${starBtn("onderwerp", t.type + "|" + t.name, t.name)}</span></div>
       <div class="meta"><span class="badge">${esc(t.type_label)}</span>${t.authors} makers · ${t.posts} posts ${pdots(t.platforms)}</div></li>`).join("")
      : `<li class="meta">Niets in de vroege fase op dit moment.</li>`;
    $("#v-news-me").innerHTML = newsList(d.snackspert_news, "Geen berichten over Snackspert in de afgelopen 30 dagen.");
    $("#v-news").innerHTML = newsList(d.snack_news, "Geen snacknieuws in de afgelopen 3 dagen.");
    $("#v-products").innerHTML = d.new_products.length ? d.new_products.map(p =>
      `<li><div class="row"><span>${p.url ? `<a href="${safeHref(p.url)}" target="_blank" rel="noopener">${esc(p.name)}</a>` : esc(p.name)}</span>
       ${starBtn("product", p.id, `${p.name} (${p.store})`, p.url)}</div>
       <div class="meta">${esc(p.store)}${p.price != null ? " · € " + Number(p.price).toFixed(2).replace(".", ",") : ""}${p.social_makers ? ` · <span class="up">${p.social_makers} makers posten erover</span>` : ""}</div></li>`).join("")
      : `<li class="meta">Geen nieuwe snackproducten in de afgelopen 2 dagen.</li>`;
    $("#v-tests-card").hidden = !d.test_ideas.length;
    $("#v-tests").innerHTML = testIdeas(d.test_ideas, "");
    $("#v-amsterdam").innerHTML = miniCandidates(d.amsterdam, "Geen Amsterdamse kandidaten op dit moment.");
  }

  function testIdeas(items, empty) {
    return items.length ? items.map(p =>
      `<li><div class="row"><span>${p.url ? `<a href="${safeHref(p.url)}" target="_blank" rel="noopener"><b>${esc(p.name)}</b></a>` : `<b>${esc(p.name)}</b>`}</span>
        <span>${starBtn("product", p.id, `${p.name} (${p.stores.join(", ")})`, p.url)}</span></div>
       <div class="meta">${esc(p.stores.join(", "))}${p.price != null ? " · € " + Number(p.price).toFixed(2).replace(".", ",") : ""} · in het schap sinds ${dateNl(p.first_seen)}${p.demo ? ' <span class="badge warn">demo</span>' : ""}</div>
       <div class="reasons">${p.reasons.map(r => `<span class="reason small">${esc(r)}</span>`).join("")}</div></li>`).join("")
      : `<li class="meta">${empty}</li>`;
  }

  // --- amsterdam -------------------------------------------------------------

  async function loadAmsterdam() {
    const fresh = ticket("amsterdam");
    const city = { city: "Amsterdam" };
    const win = state.window === "nu" ? "24u" : state.window;
    const [cands, tr, zk, news, posts] = await Promise.all([
      api("/api/kandidaten?" + qs(city)),
      api("/api/trends?" + qs(city)),
      api("/api/zaken?" + qs({ ...city, window: win })),
      api("/api/nieuws?soort=amsterdam"),
      api("/api/posts?" + qs({ ...city, sort: "nieuw", limit: 24 })),
    ]);
    if (!fresh()) return;
    $("#a-candidates").innerHTML = cands.length ? cands.map(postCard).join("")
      : '<p class="muted">Geen Amsterdamse kandidaten in de afgelopen 3 dagen.</p>';
    $("#a-sub").textContent = `· ${tr.label}`;
    const topics = tr.topics.filter(t => !["categorie", "stad"].includes(t.type)).slice(0, 15);
    $("#tbl-a-topics tbody").innerHTML = topics.length ? topics.map(t =>
      `<tr class="click" data-topic="${esc(t.type)}|${esc(t.name)}"><td><span class="badge">${esc(t.type_label)}</span><span class="topic-name">${esc(t.name)}</span></td>
       <td class="num">${t.posts}</td><td>${phaseBadge(t.phase)}</td><td>${starBtn("onderwerp", t.type + "|" + t.name, t.name)}</td></tr>`).join("")
      : `<tr><td colspan="4" class="muted">Nog geen onderwerpen in deze periode.</td></tr>`;
    $("#tbl-a-zaken tbody").innerHTML = zk.places.length ? zk.places.slice(0, 15).map(p =>
      `<tr class="click" data-topic="zaak|${esc(p.name)}"><td><span class="topic-name">${esc(p.display)}</span> ${pdots(p.platforms)}</td>
       <td class="num">${p.posts}</td>
       <td>${zaakBadges(p, "kandidaat")}</td>
       <td>${starBtn("zaak", p.name, p.display, null, "Amsterdam")}</td></tr>`).join("")
      : `<tr><td colspan="4" class="muted">Nog geen Amsterdamse zaken herkend.</td></tr>`;
    $("#a-news").innerHTML = newsList(news, "Geen Amsterdams eetnieuws in de afgelopen 2 weken.");
    $("#a-posts").innerHTML = posts.posts.map(postCard).join("") || '<p class="muted">Nog geen posts uit Amsterdam.</p>';
    const tips = await api("/api/tips");
    if (!fresh()) return;
    const order = st => tips.statuses.indexOf(st);
    const ams = tips.spots.filter(t => t.place === "Amsterdam" || t.lists.includes("Amsterdam"))
      .sort((a, b) => (b.radar ? 1 : 0) - (a.radar ? 1 : 0) || order(a.status) - order(b.status));
    $("#a-tips").innerHTML = ams.length ? ams.slice(0, 12).map(t =>
      `<li><div class="row"><span><span class="tip-name">${esc(t.name)}</span>${t.radar ? ` <span class="badge new">🔥 ${t.radar.posts}</span>` : ""}${t.posted ? ' <span class="badge ok">✓ gepost</span>' : ""}</span>
       <span class="badge">${esc(t.status)}</span></div>
       ${t.specialty ? `<div class="meta">${esc(t.specialty)}</div>` : ""}</li>`).join("")
      + (ams.length > 12 ? `<li class="meta">en nog ${ams.length - 12} meer</li>` : "")
      : `<li class="meta">Nog geen Amsterdam-tips. Importeer je tips bij Tips &amp; routes.</li>`;
  }

  // --- ♥ en 👎 -----------------------------------------------------------------

  function fbBtns(id) {
    const v = state.feedback.get(id) || 0;
    return `<button class="fb ${v === 1 ? "on" : ""}" data-fb="1" data-id="${esc(id)}" title="Goed: meer zoals dit" aria-label="Waarderen">♥</button>` +
      `<button class="fb ${v === -1 ? "on" : ""}" data-fb="-1" data-id="${esc(id)}" title="Niet interessant: minder zoals dit" aria-label="Afkeuren">👎</button>`;
  }

  async function loadFeedback() {
    try { state.feedback = new Map(Object.entries(await api("/api/feedback"))); } catch (e) { /* leeg laten */ }
  }

  async function setFeedback(id, value) {
    const next = state.feedback.get(id) === value ? 0 : value;
    await api("/api/feedback", { method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ post_id: id, value: next }) });
    if (next) state.feedback.set(id, next); else state.feedback.delete(id);
    document.querySelectorAll(`.fb[data-id="${CSS.escape(id)}"]`).forEach(b =>
      b.classList.toggle("on", Number(b.dataset.fb) === next));
    document.querySelectorAll(`.post[data-post="${CSS.escape(id)}"]`).forEach(c => c.classList.toggle("disliked", next === -1));
    toast(next === 1 ? "♥ De tool zoekt meer zoals dit" : next === -1 ? "👎 De tool laat dit soort posts zakken" : "Beoordeling weggehaald");
  }

  // Een zaak uit de radar met één klik in je tips zetten.
  const tipBtn = (name, place, tip) => tip ? "" :
    `<button class="tipbtn" data-zaak-tip="${esc(name)}" data-place="${esc(place || "")}" title="In mijn tips zetten" aria-label="In mijn tips zetten">📍</button>`;

  function zaakBadges(p, fallback) {
    const out = [p.reviewed ? `<span class="badge ok">✓ gereviewd</span>` : ""];
    if (p.posted) out.push(p.posted.url ? `<a class="badge ok" href="${safeHref(p.posted.url)}" target="_blank" rel="noopener" title="Je eigen post">✓ gepost ${esc(p.posted.date || "")}</a>`
      : `<span class="badge ok">✓ gepost ${esc(p.posted.date || "")}</span>`);
    if (p.tip) out.push(`<span class="badge" title="Staat in je tips">📍 tip · ${esc(p.tip.status)}</span>`);
    if (!p.reviewed && !p.posted) out.push(`<span class="badge new">${fallback}</span>`);
    return out.join(" ");
  }

  // --- importeren ----------------------------------------------------------------

  async function importFile(input) {
    const file = input.files[0];
    if (!file) return;
    const form = new FormData();
    form.append("bestand", file);
    toast("Bezig met inlezen…");
    try {
      const r = await api("/api/import", { method: "POST", body: form });
      // Nieuwe routes, regio's en jaren: wat de pagina onthouden had, opnieuw ophalen.
      state.routes = null;
      state.mpYear = null;
      toast(r.melding);
      refresh();
    } catch (e) {
      toast(e.message);
    } finally {
      input.value = "";
    }
  }

  // --- tips & routes --------------------------------------------------------------

  // Statussen van tips en routes: 'te proberen' en 'gepland' vormen je plan (Mijn lijst),
  // afgeronde tips verdwijnen uit de gewone weergave (filter 'Afgerond' haalt ze terug).
  const PLANNED = ["te proberen", "gepland"], DONE = ["bezocht", "gereviewd", "afgevallen"];
  const statusMatch = (filter, st) => filter === "open" ? !DONE.includes(st) : filter === "plan" ? PLANNED.includes(st)
    : filter === "afgerond" ? DONE.includes(st) : filter === "alle" || !filter || st === filter;
  function fillStatusFilter(sel, statuses) {
    const cur = sel.value || "open";
    const opts = [["open", "Open (nog niet bezocht)"], ["plan", "📍 Mijn plan (te proberen + gepland)"],
      ...statuses.map(x => [x, x]), ["afgerond", "Afgerond (bezocht, gereviewd, afgevallen)"], ["alle", "Alle statussen"]];
    sel.innerHTML = opts.map(([v, l]) => `<option value="${esc(v)}">${esc(l)}</option>`).join("");
    sel.value = opts.some(([v]) => v === cur) ? cur : "open";
  }
  const statusSelect = (attr, id, current, statuses) =>
    `<select class="status-select" ${attr}="${id}" aria-label="Status">${statuses.map(x => `<option ${x === current ? "selected" : ""}>${x}</option>`).join("")}</select>`;
  function statusToast(name, st) {
    toast(DONE.includes(st) ? `${name}: ${st}. Staat nu onder 'Afgerond'.`
      : PLANNED.includes(st) ? `${name}: ${st}. Staat nu in Mijn lijst → Mijn plan.` : `${name}: ${st}`);
  }

  async function loadTips() {
    state.tips = await api("/api/tips");
    const t = state.tips;
    const fillSelect = (sel, values, label) => {
      const cur = sel.value;
      sel.innerHTML = `<option value="">${label}</option>` + values.map(v => `<option>${esc(v)}</option>`).join("");
      sel.value = values.includes(cur) ? cur : "";
    };
    fillSelect($("#t-list"), t.lists, "Alle lijsten");
    fillSelect($("#t-region"), t.regions, "Alle regio's");
    fillStatusFilter($("#t-status"), t.statuses);
    const count = sts => t.spots.filter(x => sts.includes(x.status)).length;
    const kpis = [["Open tips", fmt(t.spots.length - count(DONE)), `${t.lists.length} lijsten`],
      ["📍 In je plan", fmt(count(PLANNED)), `${count(["gepland"])} gepland`],
      ["Afgerond", fmt(count(DONE)), `${t.spots.filter(x => x.posted).length} al eens gepost`],
      ["🔥 In de radar", fmt(t.spots.filter(x => x.radar).length), "genoemd in posts, 30 dagen"]];
    $("#t-kpis").innerHTML = kpis.map(([l, v, d]) =>
      `<div class="kpi"><div class="label">${l}</div><div class="value">${v}</div><div class="delta">${esc(d)}</div></div>`).join("");
    $("#t-lists").innerHTML = t.lists.map(l => `<option value="${esc(l)}">`).join("");
    renderTips();
    showTipsView();
    loadSuggestions();
    loadNewPlaces();
  }

  async function loadNewPlaces() {
    const d = await api("/api/nieuwezaken");
    state.newPlaces = d.places;
    const last = d.last;
    $("#t-maps-info").innerHTML = last
      ? `Laatst gezocht ${ago(last.at)} in ${esc(last.cities.join(" en "))}: ${fmt(last.found)} zaken bekeken, ${fmt(last.new)} nieuw. Elke week zoekt de tool in de volgende steden (instelbaar bij Budget &amp; instellingen). De eerste keer per stad legt hij vast wat er al is; pas daarna verschijnen nieuwe zaken.`
      : "Elke week zoekt de tool op Google Maps naar nieuwe snackbars, foodtrucks en streetfood, steeds in twee andere steden (± 1 dollar per week). De eerste keer per stad legt hij vast wat er al is; vanaf de volgende keer zie je hier wat er nieuw bij komt.";
    $("#t-maps").innerHTML = d.places.length ? d.places.map((p, i) =>
      `<li><div class="row"><span>${p.url ? `<a href="${safeHref(p.url)}" target="_blank" rel="noopener"><b>${esc(p.name)}</b></a>` : `<b>${esc(p.name)}</b>`}
         <span class="meta">${esc([p.category, p.city].filter(Boolean).join(" · "))}</span>${p.hot ? ' <span class="badge new">⭐ al goed beoordeeld</span>' : ""}</span>
         <button class="btn small" data-maps-add="${i}">📍 In mijn tips</button></div>
       <div class="meta">${p.rating ? `${String(p.rating).replace(".", ",")} ★ · ` : ""}${p.reviews} reviews · gevonden ${ago(p.first_seen)}${p.address ? " · " + esc(p.address) : ""}</div></li>`).join("")
      : `<li class="meta">Nog geen nieuwe zaken gevonden.</li>`;
  }

  function showTipsView() {
    const v = state.tipsView;
    $$("#t-view button").forEach(x => x.classList.toggle("on", x.dataset.v === v));
    $("#t-tips-card").hidden = v !== "tips" && v !== "kaart";
    $("#t-map-wrap").hidden = $("#t-map-routes-label").hidden = v !== "kaart";
    $("#t-table-wrap").hidden = v === "kaart";
    if (v === "tips" || v === "kaart") renderTips();
    $("#t-routes-card").hidden = v !== "routes";
    $("#t-proposals-card").hidden = v !== "voorstellen";
    if (v === "routes") loadRoutes();
    if (v === "voorstellen") loadProposals();
  }

  async function loadSuggestions() {
    const s = await api("/api/tips/suggesties");
    state.suggestions = s;
    $("#t-suggest-card").hidden = !s.length;
    $("#t-suggest").innerHTML = s.map((x, i) =>
      `<li><div class="row"><span><button class="linkish" data-topic="${esc(x.topic)}">${esc(x.name)}</button>
         ${x.place ? `<span class="meta">${esc(x.place)}</span>` : ""}</span>
         <button class="btn small" data-sugg-add="${i}">📍 In mijn tips</button></div>
       <div class="reasons">${x.reasons.map(r => `<span class="reason small">${esc(r)}</span>`).join("")} ${phaseBadge(x.phase)}</div>
       ${x.snippet ? `<div class="meta">“${esc(x.snippet)}”</div>` : ""}</li>`).join("");
  }

  async function loadProposals() {
    const d = await api("/api/routes/voorstellen");
    state.proposals = d;
    const h = d.habits;
    $("#t-proposals-info").innerHTML = `Vanaf <b>${esc(d.home)}</b> en weer terug (aan te passen bij Budget &amp; instellingen). ` +
      (h.routes ? `De tool leert van je ${fmt(h.routes)} routes: meestal ${fmt(h.median_km)} km retour, tot ${fmt(h.max_km)} km, met ${h.stops.join(" of ")} stops. ` : "") +
      `Hij combineert kansrijke tips (Viral-potentie) die dicht bij elkaar liggen. Routes die je afwijst, stelt hij niet opnieuw voor. Afstand en rijtijd zijn een schatting; Google Maps geeft de echte route.`;
    const p = d.progress || {};
    $("#t-geo").innerHTML = d.missing ? `<div class="geo-note">📍 Van ${fmt(d.missing)} plaatsen weet de tool nog niet waar ze liggen, dus die tips doen nog niet mee.
      ${p.running ? `Bezig met opzoeken: ${p.done} van ${p.todo}…` : `Dit gebeurt vanzelf bij elke ophaalronde, of <button class="btn small" id="t-geo-start">nu opzoeken</button> (duurt ±${Math.ceil(d.missing * 1.2 / 60)} min).`}</div>` : "";
    if (p.running) setTimeout(() => { if (state.tab === "tips" && state.tipsView === "voorstellen") loadProposals(); }, 5000);
    $("#t-proposals").innerHTML = d.routes.length ? d.routes.map((r, i) => `<div class="route proposal">
      <h3>${esc(r.name)}</h3>
      <div class="meta">±${fmt(r.km)} km retour · ±${esc(r.duration)} rijden · gemiddelde potentie <b>${r.potential}</b></div>
      <ol>${r.stops.map(s => `<li><a href="${safeHref(s.maps)}" target="_blank" rel="noopener"><b>${esc(s.name)}</b></a> <span class="muted">(${esc(s.place)})</span> <b>${s.potential}</b>
        ${s.specialty ? ` – ${esc(s.specialty)}` : ""}<span class="stop-reasons">${esc(s.reasons.join(" · "))}</span></li>`).join("")}</ol>
      <div class="foot"><a class="btn small primary" href="${safeHref(r.maps)}" target="_blank" rel="noopener">Route in Google Maps ↗</a>
        <span><button class="btn small" data-prop-save="${i}">Bewaren</button>
        <button class="btn small ghost" data-prop-reject="${i}" title="Deze route niet meer voorstellen">👎 Niet voor mij</button></span></div>
    </div>`).join("") : `<p class="muted">${esc(d.melding || "") || "Nog geen voorstellen: er zijn (nog) te weinig kansrijke tips dicht bij elkaar met een bekende plaats."}</p>`;
  }

  function renderTips() {
    const t = state.tips;
    if (!t) return;
    const q = $("#t-q").value.trim().toLowerCase();
    const lst = $("#t-list").value, reg = $("#t-region").value, st = $("#t-status").value, radar = $("#t-radar").checked;
    const rows = t.spots.filter(x => (!q || `${x.name} ${x.place} ${x.specialty}`.toLowerCase().includes(q))
      && (!lst || x.lists.includes(lst)) && (!reg || x.region === reg) && statusMatch(st, x.status) && (!radar || x.radar))
      .sort((a, b) => (b.radar?.posts || 0) - (a.radar?.posts || 0));
    if (state.tipsView === "kaart") { renderTipMap(rows); return; }
    $("#tbl-tips tbody").innerHTML = rows.length ? rows.map(x => `<tr>
      <td><a class="tip-name" href="${safeHref(x.maps)}" target="_blank" rel="noopener" title="Open in Google Maps">${esc(x.name)}</a>
        <div class="meta">${esc([x.place, x.region].filter(Boolean).join(" · "))}
        ${x.radar ? ` · <button class="linkish" data-posts="${esc(x.radar.post_ids.join(","))}" data-label="${esc(x.name)}">🔥 ${x.radar.posts} ${x.radar.posts === 1 ? "post" : "posts"}</button>` : ""}
        ${x.posted ? ` · ${x.posted.url ? `<a href="${safeHref(x.posted.url)}" target="_blank" rel="noopener">✓ gepost ${esc(x.posted.date || "")}</a>` : `✓ gepost ${esc(x.posted.date || "")}`}` : ""}</div></td>
      <td>${esc(x.specialty || "")}</td>
      <td class="hide-s">${x.lists.map(l => `<span class="badge">${esc(l)}</span>`).join(" ")}</td>
      <td>${statusSelect("data-tip-status", x.id, x.status, t.statuses)}</td>
      <td class="hide-s"><textarea class="note-input" rows="1" data-tip-note="${x.id}" placeholder="Notitie…">${esc(x.note || "")}</textarea></td>
      <td><button class="btn small ghost" data-tip-del="${x.id}" aria-label="Verwijderen">✕</button></td></tr>`).join("")
      : `<tr><td colspan="6" class="muted">${t.spots.length ? "Geen tips met deze filters." : "Nog geen tips. Importeer je Excel-bestand met de knop hierboven, of voeg er hieronder een toe."}</td></tr>`;
  }

  // --- kaart met tips --------------------------------------------------------------

  let tipMap, tipLayer;
  async function renderTipMap(rows) {
    const t = state.tips;
    if (!window.L) { $("#t-map").innerHTML = '<div class="empty">Kaart niet beschikbaar (geen internet?).</div>'; return; }
    if (!tipMap) {
      tipMap = L.map("t-map", { scrollWheelZoom: true }).setView([52.2, 5.3], 7);
      L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", { maxZoom: 16, attribution: "© OpenStreetMap" }).addTo(tipMap);
    }
    if (tipLayer) tipLayer.remove();
    tipLayer = L.layerGroup().addTo(tipMap);
    const css = getComputedStyle(document.documentElement);
    const color = { plan: css.getPropertyValue("--accent").trim() || "#e4572e", hot: "#d62828", done: "#8a8a8a", tip: "#2a6f97" };
    // Eén stip per plaats: tips liggen op plaatsniveau, dus Utrecht krijgt één stip met alle Utrechtse tips.
    const groups = new Map();
    let without = 0;
    rows.forEach(x => {
      if (!x.coords) { without++; return; }
      const k = x.coords.join(",");
      if (!groups.has(k)) groups.set(k, { coords: x.coords, place: x.place, tips: [] });
      groups.get(k).tips.push(x);
    });
    const max = Math.max(1, ...[...groups.values()].map(g => g.tips.length));
    const bounds = [];
    groups.forEach(g => {
      const kind = g.tips.some(x => PLANNED.includes(x.status)) ? "plan" : g.tips.some(x => x.radar) ? "hot"
        : g.tips.every(x => DONE.includes(x.status)) ? "done" : "tip";
      const list = g.tips.sort((a, b) => PLANNED.includes(b.status) - PLANNED.includes(a.status)).map(x =>
        `<li><a href="${safeHref(x.maps)}" target="_blank" rel="noopener"><b>${esc(x.name)}</b></a>${x.radar ? " 🔥" : ""}
          <span class="st">· ${esc(x.status)}</span>${x.specialty ? `<br><span class="st">${esc(x.specialty.slice(0, 90))}</span>` : ""}</li>`).join("");
      L.circleMarker(g.coords, { radius: 6 + 14 * Math.sqrt(g.tips.length / max), color: "#fff", weight: 2,
        fillColor: color[kind], fillOpacity: 0.85, className: "tipdot" })
        .bindTooltip(`${esc(g.place)}: ${g.tips.length} ${g.tips.length === 1 ? "tip" : "tips"}`)
        .bindPopup(`<div class="tippop"><h4>${esc(g.place)} · ${g.tips.length}</h4><ul>${list}</ul></div>`)
        .addTo(tipLayer);
      bounds.push(g.coords);
    });
    if (t.home?.coords) {
      L.marker(t.home.coords, { title: "Thuisbasis" }).bindTooltip(`🏠 ${esc(t.home.name)}`).addTo(tipLayer);
      bounds.push(t.home.coords);
    }
    if ($("#t-map-routes").checked) {
      if (!state.routes) await loadRoutesData();
      (state.routes?.routes || []).filter(r => statusMatch($("#t-status").value, r.status)).forEach(r => {
        const pts = r.stops.map(x => x.coords).filter(Boolean);
        if (pts.length < 2) return;
        L.polyline(t.home?.coords ? [t.home.coords, ...pts, t.home.coords] : pts,
          { color: PLANNED.includes(r.status) ? color.plan : color.tip, weight: 2, opacity: 0.55 })
          .bindTooltip(esc(r.name)).addTo(tipLayer).bringToBack();  // stippen blijven klikbaar
      });
    }
    if (bounds.length && !state.tipMapFitted) { tipMap.fitBounds(bounds, { padding: [30, 30], maxZoom: 11 }); state.tipMapFitted = true; }
    setTimeout(() => tipMap.invalidateSize(), 50);
    $("#t-map-note").innerHTML = `${fmt(rows.length - without)} tips op ${fmt(groups.size)} plaatsen. Kleur: <b style="color:${color.plan}">●</b> in je plan, `
      + `<b style="color:${color.hot}">●</b> nu in de radar, <b style="color:${color.tip}">●</b> overig, <b style="color:${color.done}">●</b> afgerond. `
      + "De stippen staan op de plaats, niet op het adres: klik voor de zaken en open ze in Google Maps."
      + (without ? ` ${fmt(without)} tips staan er nog niet op omdat de tool hun plaats nog niet kent`
        + (t.missing_places ? ` (<button class="btn small" id="t-map-geo">nu opzoeken</button>, duurt ±${Math.ceil(t.missing_places * 1.2 / 60)} min)` : "") + "." : "");
  }

  async function loadRoutesData() {
    state.routes = await api("/api/routes");
    const sel = $("#r-region"), cur = sel.value;
    const regions = [...new Set(state.routes.routes.map(x => x.region).filter(Boolean))].sort();
    sel.innerHTML = `<option value="">Alle regio's</option>` + regions.map(v => `<option>${esc(v)}</option>`).join("");
    sel.value = regions.includes(cur) ? cur : "";
    fillStatusFilter($("#r-status"), state.routes.statuses);
  }

  async function loadRoutes() {
    if (!state.routes) {
      await loadRoutesData();
    }
    renderRoutes();
  }

  function renderRoutes() {
    const r = state.routes;
    if (!r) return;
    const q = $("#r-q").value.trim().toLowerCase(), reg = $("#r-region").value, n = $("#r-stops").value;
    const st = $("#r-status").value;
    const rows = r.routes.filter(x => (!reg || x.region === reg) && (!n || x.stops.length === Number(n)) && statusMatch(st, x.status)
      && (!q || `${x.name} ${x.stops.map(s => s.text).join(" ")}`.toLowerCase().includes(q)));
    $("#t-routes").innerHTML = rows.length ? rows.map(x => `<div class="route">
      <h3>${esc(x.name)}</h3>
      <div class="meta">${esc(x.region)}${x.km ? " · " + esc(x.km) + " retour" : ""}${x.duration ? " · " + esc(x.duration) + " rijden" : ""}</div>
      <ol>${x.stops.map(s => `<li><b>${esc(s.name)}</b>${s.place ? ` <span class="muted">(${esc(s.place)})</span>` : ""}${s.specialty ? ` – ${esc(s.specialty)}` : ""}${s.status && s.status !== "nieuw" ? ` <span class="badge ${DONE.includes(s.status) ? "ok" : "new"}">${esc(s.status)}</span>` : ""}</li>`).join("")}</ol>
      ${x.note ? `<div class="meta">${esc(x.note)}</div>` : ""}
      <div class="foot"><a class="btn small primary" href="${safeHref(x.maps)}" target="_blank" rel="noopener">Route in Google Maps ↗</a>
      ${statusSelect("data-route-status", x.id, x.status, r.statuses)}</div>
    </div>`).join("") : `<p class="muted">${r.routes.length ? "Geen routes met deze filters (afgeronde routes staan onder 'Afgerond')." : "Nog geen routes. Importeer je Excel-bestand met tabbladen 'Route' en 'Stop 1'."}</p>`;
  }

  // --- viral-potentie -------------------------------------------------------------

  const POT_LABELS = { creatie: "Eigen creatie", variant: "Variant op een bekende snack", combinatie: "Combinatie van snacks", spektakel: "Opvallend om te zien",
    twist: "Twist op een bekende snack", getipt: "Vaker getipt door volgers", radar: "Nu al posts over (🔥)",
    kleine_viral: "Een daarvan gaat hard", huisgemaakt: "Huisgemaakt", claim: "Verhaal of claim",
    schaarste: "Schaars (alleen op vrijdag…)", herkenbaar: "Herkenbare snack", prijs: "Prijs als haakje",
    niche: "Niche gerecht", algemeen: "Weinig bijzonders genoemd", gesloten: "Mogelijk gesloten" };

  async function loadPotentie() {
    const fresh = ticket("potentie");
    const d = await api(`/api/potentie?limit=${state.potLimit || 10}`);
    if (!fresh()) return;
    state.pot = d;
    $("#pot-list").innerHTML = d.top.length ? d.top.map((t, i) => {
      const chips = t.reasons.slice().sort((a, b) => b.points - a.points).map(r =>
        `<span class="reason ${r.points < 0 ? "minus" : r.points < 0.9 ? "small" : ""}" title="${r.points > 0 ? "+" : ""}${String(r.points).replace(".", ",")} punten">${esc(r.text)}</span>`).join("");
      const status = t.id != null
        ? `<select class="status-select" data-pot-status="${t.id}" aria-label="Status">${d.statuses.map(s => `<option ${s === t.status ? "selected" : ""}>${s}</option>`).join("")}</select>`
        : `<button class="btn small ghost" data-pot-add="${i}">+ Bewaren als tip</button>`;
      return `<li class="pot"><div class="pot-rank">${i + 1}</div><div class="pot-body">
        <div class="pot-head"><span><a class="tip-name" href="${safeHref(t.maps)}" target="_blank" rel="noopener" title="Open in Google Maps">${esc(t.name)}</a>
          <span class="where">${esc([t.place, t.region].filter(Boolean).join(" · "))}</span></span>
          <span class="pot-score" title="Potentie op een schaal van 0 tot 100"><span class="meter"><span style="width:${t.potential}%"></span></span><b>${t.potential}</b></span></div>
        ${t.specialty ? `<div class="pot-spec">${esc(t.specialty)}</div>` : ""}
        <div class="reasons">${chips}</div>
        <div class="pot-foot"><span>Zekerheid: ${esc(t.confidence)}</span>
          ${t.lists.map(l => `<span class="badge">${esc(l)}</span>`).join("")}
          ${t.routes.length ? `<span>In route: ${esc(t.routes[0])}${t.routes.length > 1 ? ` (+${t.routes.length - 1})` : ""}</span>` : ""}
          ${status}</div>
      </div></li>`;
    }).join("") : `<li class="meta">Nog geen tips. Importeer je tips en routes bij <b>Tips &amp; routes</b>.</li>`;
    $("#pot-routes").innerHTML = d.routes.filter(r => r.score > 0).map(r =>
      `<li><div class="row"><span class="tip-name">${esc(r.name)}</span><a class="btn small primary" href="${safeHref(r.maps)}" target="_blank" rel="noopener">Maps ↗</a></div>
       <div class="meta">${r.stops.map(s => `${esc(s.name)}${s.potential != null ? ` <b>${s.potential}</b>` : ""}`).join(" → ")}</div></li>`).join("")
      || `<li class="meta">Nog geen routes.</li>`;
    const P = d.points;
    const own = d.own_posts ? (() => {
      const rec = d.lifts.recognition, loc = d.lifts.locations;
      const parts = [];
      if (rec.Mainstream && rec.Niche) parts.push(`herkenbare snacks ${String((rec.Mainstream.lift / rec.Niche.lift).toFixed(1)).replace(".", ",")}× zo goed als niche`);
      if (loc["Buiten Amsterdam"] && loc.Amsterdam) parts.push(`buiten Amsterdam ${String(loc["Buiten Amsterdam"].lift).replace(".", ",")}× en Amsterdam ${String(loc.Amsterdam.lift).replace(".", ",")}× je mediaan`);
      if (d.lifts.snacks.length) parts.push("snacks die bij jou het best scoren: " + d.lifts.snacks.map(s => `${esc(s.snack)} ${String(s.lift).replace(".", ",")}×`).join(", "));
      return `<p class="hint">Uit je ${fmt(d.own_posts)} eigen posts: ${parts.join("; ")}. Dat telt mee als extra punten (tot ±1,5).</p>`;
    })() : `<p class="hint">Importeer je posts bij <b>Mijn posts</b>, dan telt ook mee wat bij jouw publiek werkt.</p>`;
    $("#pot-how").innerHTML = `<ul class="how">${Object.entries(POT_LABELS).filter(([k]) => P[k] != null)
      .sort((a, b) => P[b[0]] - P[a[0]]).map(([k, label]) => `<li><span>${label}</span><b class="${P[k] < 0 ? "down" : ""}">${P[k] > 0 ? "+" : ""}${String(P[k]).replace(".", ",")}</b></li>`).join("")}</ul>
      ${own}
      <p class="hint">Je ♥, 👎 en bewaarde items tellen ook mee (tot ±2). Niet meegeteld: ${d.skipped.gepost} al gepost, ${d.skipped.status} bezocht, gereviewd of afgewezen. ${fmt(d.total)} tips beoordeeld.</p>`;
  }

  // --- mijn posts -----------------------------------------------------------------

  const MONTHS = ["jan", "feb", "mrt", "apr", "mei", "jun", "jul", "aug", "sep", "okt", "nov", "dec"];
  const monthLabel = m => `${MONTHS[Number(m.slice(5, 7)) - 1]} '${m.slice(2, 4)}`;
  const kfmt = v => v >= 1e6 ? (v / 1e6).toFixed(1).replace(".", ",") + "M" : v >= 1000 ? Math.round(v / 1000) + "k" : String(Math.round(v));

  async function loadMijnPosts() {
    const fresh = ticket("mijnposts");
    if (state.mpYear === null) {
      const first = await api("/api/mijnposts");
      state.mpYear = first.years?.[0] || "";
    }
    const d = await api("/api/mijnposts" + (state.mpYear ? `?jaar=${encodeURIComponent(state.mpYear)}` : ""));
    if (!fresh()) return;
    state.mp = d;
    $("#m-years").innerHTML = (d.years || []).length ? [...d.years.map(y => [y, y]), ["", "Alles"]].map(([v, l]) =>
      `<button class="chip ${state.mpYear === v ? "on" : ""}" data-year="${v}">${l}</button>`).join("") : "";
    if (!d.posts && !d.kpis) {
      $("#m-kpis").innerHTML = "";
      $("#m-insights").innerHTML = `<li class="meta">Nog geen posts. Klik op <b>Excel importeren</b> en kies je totaaloverzicht (met het tabblad <em>Posts</em>).</li>`;
      ["#m-months", "#m-followers"].forEach(id => $(id).innerHTML = "");
      ["#tbl-m-groups", "#tbl-m-snacks", "#tbl-m-top", "#tbl-m-tests"].forEach(id => $(id + " tbody").innerHTML = "");
      $("#m-dims").innerHTML = "";
      return;
    }
    const k = d.kpis;
    const kp = [["Posts", fmt(k.posts), `${k.collabs} samenwerkingen of collabs`],
      ["Mediaan views", fmt(k.median_views), "per post"],
      ["Totaal views", kfmt(k.views_total), ""],
      ["Nieuwe volgers", fmt(k.followers), "zonder collabs"],
      ["Volgers per post", k.followers_per_post != null ? String(k.followers_per_post).replace(".", ",") : "–",
        k.followers_per_10k != null ? `${String(k.followers_per_10k).replace(".", ",")} per 10.000 views` : ""]];
    $("#m-kpis").innerHTML = kp.map(([l, v, s]) =>
      `<div class="kpi"><div class="label">${l}</div><div class="value">${v}</div><div class="delta">${esc(s)}</div></div>`).join("");
    const labels = d.months.map(m => m.month);
    const series = { cur: d.months.map(m => m.median_views) };
    const names = { cur: "Mediaan views" }, colors = { cur: "var(--accent)" };
    if (d.months.some(m => m.median_prev_year != null)) {
      series.prev = d.months.map(m => m.median_prev_year);
      names.prev = "Zelfde maand vorig jaar";
      colors.prev = "var(--seq-1)";
    }
    Charts.lineChart($("#m-months"), labels, series, { names, colors, fmtLabel: monthLabel, fmtTick: kfmt,
      fmtValue: v => fmt(v), label: "Mediaan views per maand", height: 200 });
    Charts.columnChart($("#m-followers"), labels, d.months.map(m => m.followers), { fmtLabel: monthLabel,
      fmtTick: kfmt, fmtValue: v => fmt(v), valueName: "Nieuwe volgers", label: "Nieuwe volgers per maand", height: 150 });
    $("#m-insights").innerHTML = d.insights.map(i => `<li>${i}</li>`).join("") || `<li class="meta">Nog te weinig posts voor conclusies.</li>`;
    $("#m-dims").innerHTML = d.dimensions.map(([key, label]) =>
      `<button class="chip ${state.mpDim === key ? "on" : ""}" data-dim="${key}">${label}</button>`).join("");
    renderMpGroups();
    $("#tbl-m-snacks tbody").innerHTML = d.snacks.length ? d.snacks.map(x =>
      `<tr><td>${esc(x.snack)}</td><td class="num">${x.posts}</td><td class="num">${fmt(x.median_views)}</td>
       <td class="num ${x.lift >= 1.1 ? "up" : x.lift < 0.9 ? "down" : ""}">${String(x.lift).replace(".", ",")}×</td></tr>`).join("")
      : `<tr><td colspan="4" class="muted">Nog geen snack met 6 of meer posts in deze periode.</td></tr>`;
    renderMpTop();
    renderTiming(d.timing);
    loadTrefkans();
    const hf = $("#hook-format"), cur = hf.value;
    hf.innerHTML = `<option value="">Alle formats</option>` + (d.formats || []).map(f => `<option>${esc(f)}</option>`).join("");
    hf.value = (d.formats || []).includes(cur) ? cur : "";
    $("#tbl-m-tests tbody").innerHTML = d.supermarket_tests.length ? d.supermarket_tests.map((t, i) =>
      `<tr><td class="num">${i + 1}</td><td>${t.url ? `<a href="${safeHref(t.url)}" target="_blank" rel="noopener">${esc(t.product)}</a>` : esc(t.product)} <span class="meta">${esc(t.month || "")}</span></td>
       <td class="num">${fmt(t.views)}</td><td class="num">${t.followers != null ? fmt(t.followers) : "–"}</td></tr>`).join("")
      : `<tr><td colspan="4" class="muted">Geen supermarkttests in deze periode.</td></tr>`;
  }

  const idxCell = v => v == null ? `<td class="num">–</td>` : `<td class="num ${v >= 110 ? "up" : v < 90 ? "down" : ""}">${v}</td>`;

  async function loadTrefkans() {
    const r = await api("/api/trefkans");
    $("#tk-info").innerHTML = r.suggested
      ? `Sinds ${dateNl(r.since)} raadde de tool ${fmt(r.suggested)} zaken, snacks en producten aan; ${fmt(r.posted)} daarvan heb je gepost`
        + (r.hit_median ? ` (mediaan ${fmt(r.hit_median)} views, je normale mediaan is ${fmt(r.median_views)}).` : ".")
        + ` Vanaf 3 geposte tips met hetzelfde signaal telt de tool dat signaal op Vandaag zwaarder of lichter mee. Importeer je posts regelmatig, dan leert hij sneller.`
      : "De tool houdt vanaf nu bij wat hij je aanraadt. Importeer later je posts, dan zie je hier welke tips je postte en hoe die liepen.";
    $("#tbl-tk-signals tbody").innerHTML = r.signals.length ? r.signals.map(s => `<tr class="${s.hits < 3 ? "small-n" : ""}" title="${s.hits < 3 ? "Minder dan 3: telt nog niet mee" : ""}">
      <td>${esc(s.signal)}</td><td class="num">${s.hits}</td>
      <td class="num ${s.lift >= 1.1 ? "up" : s.lift < 0.9 ? "down" : ""}">${s.lift != null ? String(s.lift).replace(".", ",") + "×" : "–"}</td></tr>`).join("")
      : `<tr><td colspan="3" class="muted">Nog geen geposte tips.</td></tr>`;
    $("#tk-hits").innerHTML = r.hits.map(h => `<li><div class="row"><span>${h.url ? `<a href="${safeHref(h.url)}" target="_blank" rel="noopener">${esc(h.label)}</a>` : esc(h.label)}</span>
      <span class="meta">${fmt(h.views)} views</span></div><div class="meta">${esc(h.date || "")} · tip sinds ${dateNl(h.since)} · ${esc(h.signals.join(", ") || h.kind)}</div></li>`).join("");
  }

  function renderTiming(t) {
    if (!t) return;
    $("#tbl-m-days tbody").innerHTML = t.days.length ? t.days.map(x => `<tr><td>${esc(x.name)}</td><td class="num">${x.posts}</td>
      ${idxCell(x.views_index)}${idxCell(x.followers_index)}<td class="hide-s meta">${x.mostly ? `${esc(x.mostly)} (${x.mostly_pct}%)` : "gemengd"}</td></tr>`).join("")
      : `<tr><td colspan="5" class="muted">Te weinig posts met een datum.</td></tr>`;
    $("#tbl-m-monthidx tbody").innerHTML = t.months.map(x => `<tr><td>${esc(x.name)}</td><td class="num">${x.posts}</td>
      ${idxCell(x.views_index)}${idxCell(x.followers_index)}</tr>`).join("");
  }

  async function hookCheck(e) {
    e.preventDefault();
    const f = e.target;
    const r = await api("/api/hookcheck", { method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ caption: f.caption.value, format: f.format.value }) });
    const scope = r.format ? `je ${fmt(r.posts)} posts in '${esc(r.format)}'` : `je ${fmt(r.posts)} posts`;
    $("#hook-result").innerHTML = (r.findings.length ? `<p class="hint">Vergeleken met ${scope} (100 = even goed als de rest):</p><ul class="list">${r.findings.map(x =>
      `<li><div class="row"><span>Eerste zin ${esc(x.label)}</span><b class="${x.index >= 110 ? "up" : x.index < 90 ? "down" : ""}">${x.index}</b></div>
       <div class="meta">${x.posts} posts, mediaan ${fmt(x.median_views)} views${x.followers != null ? ` · ${x.followers} volgers per post (de rest ${x.followers_other ?? "–"})` : ""}</div></li>`).join("")}</ul>`
      : `<p class="muted">Niets wat duidelijk afwijkt in ${scope}: de eerste zin lijkt op wat je normaal doet.</p>`)
      + (r.similar.length ? `<p class="hint">Je posts met de meest vergelijkbare eerste zin:</p><ul class="list">${r.similar.map(p =>
        `<li><div class="row"><span>${p.url ? `<a href="${safeHref(p.url)}" target="_blank" rel="noopener">${esc(p.first_line)}</a>` : esc(p.first_line)}</span>
         <span class="meta">${fmt(p.views)} views${p.followers_count && p.followers != null ? ` · ${fmt(p.followers)} volgers` : ""}</span></div></li>`).join("")}</ul>` : "")
      + `<p class="hint">Een verband, geen garantie: test het een paar keer.</p>`;
  }

  function renderMpGroups() {
    const d = state.mp;
    if (!d?.groups) return;
    const rows = (d.groups[state.mpDim] || []).map(g => [g.name, g]);
    $("#m-dim-hint").textContent = d.classified < d.kpis.posts
      ? `${d.classified} van de ${d.kpis.posts} posts zijn ingedeeld; de rest telt hier niet mee.` : "";
    const max = Math.max(1, ...rows.map(([, v]) => v.median_views));
    $("#tbl-m-groups tbody").innerHTML = rows.length ? rows.map(([name, v]) => {
      const few = v.posts < 5;
      return `<tr class="${few ? "small-n" : ""}" title="${few ? "Minder dan 5 posts: zegt nog weinig" : ""}">
        <td>${esc(name)}</td><td class="num">${v.posts}</td>
        <td><div class="bar-cell"><span class="bar" style="width:${Math.round(100 * v.median_views / max)}px"></span><b>${fmt(v.median_views)}</b></div></td>
        <td class="num hide-s ${v.index >= 110 ? "up" : v.index < 90 ? "down" : ""}">${v.index ?? "–"}</td>
        <td class="num">${v.followers_per_post != null ? String(v.followers_per_post).replace(".", ",") : "–"}</td>
        <td class="num hide-s">${fmt(v.median_shares)}</td></tr>`;
    }).join("") : `<tr><td colspan="6" class="muted">Geen ingedeelde posts in deze periode.</td></tr>`;
  }

  function renderMpTop() {
    const d = state.mp;
    if (!d) return;
    const rows = d["top_" + state.mpTop] || [];
    $("#tbl-m-top tbody").innerHTML = rows.length ? rows.map(p =>
      `<tr><td>${p.url ? `<a href="${safeHref(p.url)}" target="_blank" rel="noopener">${esc((p.caption || "").slice(0, 70))}</a>` : esc((p.caption || "").slice(0, 70))}
        <div class="meta">${esc(p.date || p.month || "")}</div></td>
       <td class="hide-s">${p.format ? `<span class="badge">${esc(p.format)}</span>` : ""}</td>
       <td class="num">${fmt(p.views)}</td><td class="num">${p.followers_count && p.followers != null ? fmt(p.followers) : "–"}</td>
       <td class="num hide-s">${fmt(p.shares)}</td></tr>`).join("")
      : `<tr><td colspan="5" class="muted">Geen posts.</td></tr>`;
  }

  // --- navigatie -------------------------------------------------------------

  const LOADERS = { vandaag: loadVandaag, trends: loadTrends, posts: () => loadPosts(), amsterdam: loadAmsterdam,
    supermarkt: loadSupermarkt, zaken: loadZaken, lijst: loadLijst, tips: loadTips, potentie: loadPotentie,
    mijnposts: loadMijnPosts,
    bronnen: loadSources, beheer: loadBeheer };

  function switchTab(tab) {
    state.tab = tab;
    remember();
    $$(".tabs button").forEach(b => b.setAttribute("aria-selected", b.dataset.tab === tab));
    $$(".panel").forEach(p => (p.hidden = p.dataset.panel !== tab));
    $("#filters").hidden = ["bronnen", "beheer", "vandaag", "lijst", "tips", "potentie", "mijnposts"].includes(tab);
    refresh();
  }

  function refresh() {
    const fn = LOADERS[state.tab];
    if (fn) fn().catch(e => toast("Laden mislukt: " + e.message));
  }

  function init() {
    // Een klik die mislukt (server even weg, ongeldige invoer) geeft een melding in plaats van stilte.
    window.addEventListener("unhandledrejection", e => toast("Er ging iets mis: " + (e.reason?.message || e.reason || "onbekende fout")));
    // Bewaarde keuzes van een oudere versie (een tabblad of periode die niet meer bestaat) negeren.
    if (!LOADERS[state.tab]) state.tab = "vandaag";
    if (!$$("#f-window button").some(b => b.dataset.v === state.window)) state.window = "24u";
    if (![...$("#f-platform").options].some(o => o.value === state.platform)) state.platform = "";
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

    document.addEventListener("click", async e => {
      const star = e.target.closest(".star");
      if (star) {
        e.stopPropagation();
        const d = star.dataset;
        await toggleWatch({ kind: d.kind, ref: d.ref, title: d.title, url: d.url || null, city: d.city || null });
        star.classList.toggle("on", !!state.watch.get(`${d.kind}|${d.ref}`));
        star.textContent = star.classList.contains("on") ? "★" : "☆";
        return;
      }
      const fb = e.target.closest(".fb");
      if (fb) {
        e.stopPropagation();
        await setFeedback(fb.dataset.id, Number(fb.dataset.fb));
        return;
      }
      const zt = e.target.closest("[data-zaak-tip]");
      if (zt) {
        e.stopPropagation();
        await api("/api/tips", { method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ name: zt.dataset.zaakTip, place: zt.dataset.place, list: "Uit de radar" }) });
        toast(`${zt.dataset.zaakTip} staat nu in je tips`);
        zt.remove();
        return;
      }
      const posts = e.target.closest("[data-posts]");
      if (posts) {
        // Precies de posts waarmee een tip in de radar kwam, ook als de naam anders gespeld is.
        state.posts.topic = { name: posts.dataset.label, ids: posts.dataset.posts.split(",").filter(Boolean) };
        $("#p-q").value = "";
        switchTab("posts");
        return;
      }
      const go = e.target.closest("[data-goto]");
      if (go) { switchTab(go.dataset.goto); return; }
      const t = e.target.closest("[data-topic]");
      if (t) {
        // Een knop of link binnen een klikbare rij doet zijn eigen ding, zonder het zijpaneel te openen.
        const inner = e.target.closest("button, a, select, textarea, input");
        if (inner && inner !== t && t.contains(inner)) return;
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
    $("#form-hook").addEventListener("submit", hookCheck);
    $("#btn-shop-test").addEventListener("click", async e => {
      e.target.disabled = true;
      $("#shop-test-result").textContent = "Bezig, dit duurt ongeveer een minuut…";
      try {
        const r = await api("/api/supermarkt/test", { method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ winkel: $("#shop-test-store").value }) });
        $("#shop-test-result").innerHTML = r.gelezen
          ? `✓ ${esc(r.winkel)} werkt: ${r.gelezen} producten, $${r.kosten_usd}.<ul>${r.voorbeelden.map(v =>
            `<li>${esc(v.naam)}${v.prijs != null ? " · € " + String(v.prijs).replace(".", ",") : ""}</li>`).join("")}</ul>`
          : `✗ ${esc(r.winkel)}: ${r.resultaten} resultaten, maar geen productnamen gevonden. Velden: <code>${esc(r.velden.join(", "))}</code>. Stuur dit naar Claude.`;
      } catch (err) {
        $("#shop-test-result").innerHTML = `✗ ${esc(err.message)}<br>Stuur deze melding naar Claude.`;
      } finally { e.target.disabled = false; }
    });
    $("#btn-backup").addEventListener("click", async e => {
      e.target.disabled = true;
      try {
        const r = await api("/api/backup", { method: "POST" });
        toast(r.drive ? "Back-up staat in Google Drive" : `Back-up gemaakt: ${r.path}`);
        loadBeheer();
      } finally { e.target.disabled = false; }
    });
    document.querySelectorAll(".import-file").forEach(i => i.addEventListener("change", () => importFile(i)));
    // tips & routes
    $("#t-view").addEventListener("click", e => {
      const b = e.target.closest("[data-v]");
      if (!b) return;
      state.tipsView = b.dataset.v;
      showTipsView();
    });
    ["#t-q", "#t-list", "#t-region", "#t-status", "#t-radar", "#t-map-routes"].forEach(id => $(id).addEventListener("input", renderTips));
    $("#t-map-wrap").addEventListener("click", async e => {
      if (!e.target.closest("#t-map-geo")) return;
      await api("/api/locaties", { method: "POST" });
      toast("Plaatsen opzoeken gestart; de kaart vult zich vanzelf aan");
      setTimeout(loadTips, 60000);
    });
    ["#r-q", "#r-region", "#r-stops", "#r-status"].forEach(id => $(id).addEventListener("input", renderRoutes));
    $("#tbl-tips").addEventListener("change", async e => {
      const sel = e.target.closest("[data-tip-status]");
      if (!sel) return;
      await api(`/api/tips/${sel.dataset.tipStatus}`, { method: "PATCH", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status: sel.value }) });
      const tip = state.tips.spots.find(x => x.id === Number(sel.dataset.tipStatus));
      if (tip) tip.status = sel.value;
      state.routes = null;
      statusToast(tip?.name || "Tip", sel.value);
      renderTips();  // op 'bezocht' gezet: weg uit de open lijst
      loadWatch();
    });
    $("#tbl-tips").addEventListener("focusout", e => {
      const note = e.target.closest("[data-tip-note]");
      if (note) api(`/api/tips/${note.dataset.tipNote}`, { method: "PATCH", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ note: note.value }) }).catch(() => toast("Notitie niet opgeslagen"));
    });
    $("#tbl-tips").addEventListener("click", async e => {
      const del = e.target.closest("[data-tip-del]");
      if (del && confirm("Deze tip verwijderen?")) {
        await api(`/api/tips/${del.dataset.tipDel}`, { method: "DELETE" });
        loadTips();
      }
    });
    $("#t-routes").addEventListener("change", async e => {
      const sel = e.target.closest("[data-route-status]");
      if (!sel) return;
      await api(`/api/routes/${sel.dataset.routeStatus}`, { method: "PATCH", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status: sel.value }) });
      const route = state.routes.routes.find(x => x.id === Number(sel.dataset.routeStatus));
      if (route) route.status = sel.value;
      statusToast(route?.name || "Route", sel.value);
      renderRoutes();
      loadWatch();
    });
    $("#form-tip").addEventListener("submit", async e => {
      e.preventDefault();
      const data = Object.fromEntries(new FormData(e.target));
      await api("/api/tips", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(data) });
      e.target.reset();
      e.target.hidden = true;
      toast(`Tip toegevoegd: ${data.name}`);
      loadTips();
    });
    $("#t-add-open").addEventListener("click", () => {
      $("#form-tip").hidden = false;
      $("#form-tip [name=name]").focus();
    });
    $("#t-add-close").addEventListener("click", () => { $("#form-tip").hidden = true; });
    $("#t-maps").addEventListener("click", async e => {
      const b = e.target.closest("[data-maps-add]");
      if (!b) return;
      const p = state.newPlaces[Number(b.dataset.mapsAdd)];
      b.disabled = true;
      await api("/api/tips", { method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: p.name, place: p.city || "", list: "Nieuw op Google Maps",
          note: `Nieuw op Google Maps (${p.reviews} reviews${p.rating ? ", " + p.rating + " ★" : ""})` }) });
      toast(`${p.name} staat nu in je tips`);
      loadTips();
    });
    $("#t-suggest").addEventListener("click", async e => {
      const b = e.target.closest("[data-sugg-add]");
      if (!b) return;
      const x = state.suggestions[Number(b.dataset.suggAdd)];
      await api("/api/tips", { method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: x.name, place: x.place, list: "Uit de radar", note: "Uit de radar: " + x.reasons.join(", ") }) });
      toast(`${x.name} staat nu in je tips`);
      loadTips();
    });
    $("#t-proposals-card").addEventListener("click", async e => {
      if (e.target.closest("#t-geo-start")) {
        await api("/api/locaties", { method: "POST" });
        toast("Plaatsen opzoeken gestart");
        setTimeout(loadProposals, 1500);
        return;
      }
      const save = e.target.closest("[data-prop-save]"), rej = e.target.closest("[data-prop-reject]");
      if (save) {
        const r = state.proposals.routes[Number(save.dataset.propSave)];
        save.disabled = true;
        try {
          await api("/api/routes/bewaar", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(r) });
        } finally { save.disabled = false; }
        state.routes = null;
        toast("Route bewaard bij Routes");
        loadProposals();
      } else if (rej) {
        const r = state.proposals.routes[Number(rej.dataset.propReject)];
        await api("/api/routes/afwijzen", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ key: r.key }) });
        toast("Deze route komt niet meer terug");
        loadProposals();
      }
    });
    // viral-potentie
    $("#pot-limit").addEventListener("click", e => {
      const b = e.target.closest("[data-limit]");
      if (!b) return;
      state.potLimit = Number(b.dataset.limit);
      $$("#pot-limit .chip").forEach(x => x.classList.toggle("on", x === b));
      loadPotentie();
    });
    $("#pot-list").addEventListener("change", async e => {
      const sel = e.target.closest("[data-pot-status]");
      if (!sel) return;
      await api(`/api/tips/${sel.dataset.potStatus}`, { method: "PATCH", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status: sel.value }) });
      const tip = state.pot.top.find(x => x.id === Number(sel.dataset.potStatus));
      statusToast(tip?.name || "Tip", sel.value);
      state.routes = null;
      if (DONE.includes(sel.value)) loadPotentie();  // bezocht: weg uit de top
      loadWatch();
    });
    // Mijn plan (in Mijn lijst)
    $("#plan-card").addEventListener("change", async e => {
      const tip = e.target.closest("[data-plan-tip]"), route = e.target.closest("[data-plan-route]");
      if (!tip && !route) return;
      const sel = tip || route;
      await api(tip ? `/api/tips/${tip.dataset.planTip}` : `/api/routes/${route.dataset.planRoute}`,
        { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ status: sel.value }) });
      state.routes = null;
      statusToast(sel.closest("tr, .route").querySelector(".tip-name, h3").textContent, sel.value);
      loadLijst();
    });
    $("#pot-list").addEventListener("click", async e => {
      const add = e.target.closest("[data-pot-add]");
      if (!add) return;
      const t = state.pot.top[Number(add.dataset.potAdd)];
      await api("/api/tips", { method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: t.name, place: t.place, specialty: t.specialty, list: "Uit routes" }) });
      toast("Bewaard als tip");
      loadPotentie();
    });
    // mijn posts
    $("#m-years").addEventListener("click", e => {
      const b = e.target.closest("[data-year]");
      if (b) { state.mpYear = b.dataset.year; loadMijnPosts(); }
    });
    $("#m-dims").addEventListener("click", e => {
      const b = e.target.closest("[data-dim]");
      if (!b) return;
      state.mpDim = b.dataset.dim;
      $$("#m-dims .chip").forEach(x => x.classList.toggle("on", x === b));
      renderMpGroups();
    });
    $("#m-top-by").addEventListener("click", e => {
      const b = e.target.closest("[data-top]");
      if (!b) return;
      state.mpTop = b.dataset.top;
      $$("#m-top-by .chip").forEach(x => x.classList.toggle("on", x === b));
      renderMpTop();
    });
    $("#lijst-filter").addEventListener("click", e => {
      const b = e.target.closest("[data-lf]");
      if (b) { state.lijstFilter = b.dataset.lf; loadLijst(); }
    });
    $("#tbl-lijst").addEventListener("change", async e => {
      const sel = e.target.closest("[data-status]");
      if (sel) {
        await api(`/api/lijst/${sel.dataset.status}`, { method: "PATCH", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ status: sel.value }) });
        toast(`Status: ${sel.value}`);
        loadLijst();
      }
    });
    $("#tbl-lijst").addEventListener("focusout", async e => {
      const note = e.target.closest("[data-note]");
      if (note) {
        state.pendingNote = api(`/api/lijst/${note.dataset.note}`, { method: "PATCH", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ note: note.value }) }).catch(() => toast("Notitie niet opgeslagen"));
      }
    });
    $("#tbl-lijst").addEventListener("click", async e => {
      const del = e.target.closest("[data-wdel]");
      if (del && confirm("Uit je lijst verwijderen?")) {
        await api(`/api/lijst/${del.dataset.wdel}`, { method: "DELETE" });
        loadLijst();
      }
    });
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

    // Ook als de status niet laadt (server net gestart), toch het tabblad tonen in plaats van een lege pagina.
    Promise.all([loadStatus(), loadWatch(), loadFeedback()])
      .catch(e => toast("Status laden mislukt: " + e.message))
      .finally(() => switchTab(state.tab));
    setInterval(poll, 15000);
  }

  init();
})();
