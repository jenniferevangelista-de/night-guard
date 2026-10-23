/* Night Guard live overlay: watches a chat and warns the child as messages arrive.
   Used by web/game.html (built-in) and by the browser extension (copied there by tools/sync_extension.py).
   No chat text is stored by this script; it only sends the recent messages to the Night Guard server. */
(function () {
  if (window.NightGuardLive) return;

  const TXT = {
    en: { on: "Guard on", paused: "Guard paused: can't analyze right now", ok: "Got it", tell: "Tell someone", fam: "Your family will know about this. You're not in trouble.",
          title: { high: "Stop! This could be dangerous", medium: "Careful", low: "Heads up" } },
    pt: { on: "Guarda ligado", paused: "Guarda pausado: não consigo analisar agora", ok: "Entendi", tell: "Contar pra alguém", fam: "Sua família vai ficar sabendo. Você não está encrencado.",
          title: { high: "Pare! Isso pode ser perigoso", medium: "Cuidado", low: "Atenção" } },
  };
  const esc = s => String(s).replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

  const CSS = `
  .ng-badge{position:fixed;right:14px;bottom:14px;z-index:2147483646;background:#161d3f;color:#eef1ff;border:1px solid #2d3770;
    border-radius:999px;padding:7px 12px;font:600 13px/1 system-ui,sans-serif;box-shadow:0 4px 18px #0006}
  .ng-badge b{color:#5fd49a}
  .ng-badge.ng-paused{background:#5a2330;border-color:#ff7a8a}.ng-badge.ng-paused b{color:#ffd36e}
  .ng-pop{position:fixed;right:14px;bottom:58px;z-index:2147483647;width:min(380px,calc(100vw - 28px));background:#1d2550;color:#eef1ff;
    border:2px solid #ffb35c;border-radius:16px;padding:16px;font:15px/1.4 system-ui,sans-serif;box-shadow:0 10px 40px #000a;animation:ngin .25s ease-out}
  .ng-pop.high{border-color:#ff7a8a}
  .ng-pop h3{margin:0 0 8px;font-size:18px}
  .ng-pop .ng-kid{font-weight:700;margin:8px 0}
  .ng-pop .ng-q{color:#a6aed6;font-style:italic;font-size:13px}
  .ng-pop .ng-fam{margin-top:10px;padding:8px 10px;border-radius:10px;background:#2a2f5e;border:1px solid #ffd36e;font-size:13px}
  .ng-pop .ng-row{display:flex;gap:8px;margin-top:12px;flex-wrap:wrap}
  .ng-pop button{border:0;border-radius:10px;padding:9px 12px;font:700 14px system-ui,sans-serif;cursor:pointer}
  .ng-pop .ng-a{background:#ffd36e;color:#2a2000}.ng-pop .ng-b{background:transparent;color:#eef1ff;border:1px solid #2d3770}
  @keyframes ngin{from{transform:translateY(10px);opacity:0}to{transform:none;opacity:1}}`;

  function ensureStyle() {
    if (document.getElementById("ng-style")) return;
    const s = document.createElement("style"); s.id = "ng-style"; s.textContent = CSS; document.head.appendChild(s);
  }

  function create({ analyze, app = "Other", lang = "en", tellUrl = null, voiceBase = null }) {
    // voiceBase: folder with the pre-generated spoken alerts (e.g. "/web/audio/pt"); the first new
    // warning is read aloud, since a kid may not be looking at the corner of the screen.
    let audio = null;
    const say = id => { if (!voiceBase) return; try { if (audio) audio.pause(); audio = new Audio(`${voiceBase}/${id}.mp3`); audio.play().catch(() => {}); } catch (e) {} };
    ensureStyle();
    const t = TXT[lang] || TXT.en;
    const badge = document.createElement("div");
    badge.className = "ng-badge";
    document.body.appendChild(badge);
    // The badge tells the truth: if analysis fails, it says the guard is paused, and it goes back
    // to "Guard on" after the next successful check. A failure is never shown as "all fine".
    const setBadge = ok => {
      badge.classList.toggle("ng-paused", !ok);
      badge.innerHTML = ok ? `🛡️ <b>${esc(t.on)}</b>` : `⚠️ <b>${esc(t.paused)}</b>`;
    };
    setBadge(true);

    // Identity of a shown warning: contact + tactic + exact words. Someone insisting with a new
    // message, or the same words from another contact, is warned again; the same message is not.
    const seen = new Set();
    const key = (s, msgs) => {
      const m = Number.isInteger(s.message_index) ? (msgs || [])[s.message_index] : null;
      return `${((m && m.name) || "").trim().toLowerCase()}|${s.id}|${(s.quote || "").trim().toLowerCase()}`;
    };
    let timer = null, busy = false, pending = null;

    function show(res, msgs) {
      const fresh = res.signals.filter(s => !seen.has(key(s, msgs)));
      if (!fresh.length) return;
      fresh.forEach(s => seen.add(key(s, msgs)));
      document.querySelectorAll(".ng-pop").forEach(n => n.remove());
      const pop = document.createElement("div");
      pop.className = "ng-pop " + (res.severity === "high" ? "high" : "");
      pop.innerHTML = `<h3>${res.severity === "high" ? "🛑" : "⚠️"} ${esc(t.title[res.severity] || t.title.low)}</h3>
        ${fresh.map(s => `<div class="ng-kid">${esc(s.kid || s.label)}${voiceBase ? ` <button class="ng-b ng-say" data-say="${esc(s.id)}" style="padding:2px 8px">🔊</button>` : ""}</div>${s.quote ? `<div class="ng-q">“${esc(s.quote)}”</div>` : ""}`).join("")}
        ${res.family_alert ? `<div class="ng-fam">👨‍👩‍👧 ${esc(t.fam)}</div>` : ""}
        <div class="ng-row"><button class="ng-a">${esc(t.ok)}</button>${tellUrl ? `<button class="ng-b">${esc(t.tell)}</button>` : ""}</div>`;
      pop.querySelector(".ng-a").onclick = () => pop.remove();
      const tb = pop.querySelector(".ng-row .ng-b"); if (tb) tb.onclick = () => window.open(tellUrl, "_blank");
      pop.querySelectorAll(".ng-say").forEach(b => b.onclick = () => say(b.dataset.say));
      document.body.appendChild(pop);
      const loudest = fresh.find(s => /^(PERIGO|DANGER)/.test(s.kid || "")) || fresh[0];
      say(loudest.id);
    }

    async function run(messages) {
      if (busy) { pending = messages; return; }
      busy = true;
      const sent = messages.slice(-12);
      try {
        const res = await analyze({ messages: sent, lang, app });
        const ok = res && ["ok", "partial"].includes(res.analysis_status || "ok") && res.severity && res.severity !== "unknown";
        setBadge(!!ok);
        if (ok && res.signals && res.severity !== "none") show(res, sent);
      } catch (e) { setBadge(false); /* server offline: say so, never "all fine" */ }
      busy = false;
      if (pending) { const p = pending; pending = null; run(p); }
    }

    return {
      // Call with the whole visible conversation whenever a new contact message appears.
      update(messages) {
        if (!messages.length || messages[messages.length - 1].from === "me") return;
        clearTimeout(timer); timer = setTimeout(() => run(messages), 1200);
      },
      reset() { seen.clear(); document.querySelectorAll(".ng-pop").forEach(n => n.remove()); },
      destroy() { badge.remove(); document.querySelectorAll(".ng-pop").forEach(n => n.remove()); },
    };
  }

  window.NightGuardLive = { create };
})();
