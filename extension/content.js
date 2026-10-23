// Night Guard content script: reads the visible chat and lets the local guard react to new contact messages.
// Adapters: the BlockQuest demo (reliable), Discord web and WhatsApp Web (experimental: their page
// structure can change at any time).
document.documentElement.dataset.nightGuardExt = "1"; // tells the demo page not to start its built-in guard

const ADAPTERS = [
  {
    app: "Roblox", // fictional BlockQuest demo page
    test: () => /\/game/.test(location.pathname),
    read: () => [...document.querySelectorAll("[data-ng-from]")].map(el => ({
      from: el.dataset.ngFrom, name: el.dataset.ngName || "", text: el.querySelector("[data-ng-text]")?.textContent || "",
    })),
  },
  {
    app: "Discord",
    test: () => location.hostname === "discord.com",
    read: (myName) => {
      let author = "";
      return [...document.querySelectorAll('li[id^="chat-messages-"]')].map(li => {
        const a = li.querySelector('h3 span[class*="username"]');
        if (a) author = a.textContent.trim(); // grouped messages reuse the last author
        const text = li.querySelector('div[id^="message-content-"]')?.textContent || "";
        return { from: myName && author === myName ? "me" : "them", name: author, text };
      });
    },
  },
  {
    app: "WhatsApp",
    test: () => location.hostname === "web.whatsapp.com",
    read: () => [...document.querySelectorAll("div.message-in, div.message-out")].map(el => ({
      from: el.classList.contains("message-out") ? "me" : "them", name: "",
      text: [...el.querySelectorAll("span.selectable-text")].map(s => s.textContent).join(" "),
    })),
  },
];

(async function main() {
  const adapter = ADAPTERS.find(a => a.test());
  if (!adapter) return;
  const cfg = await chrome.storage.local.get(["lang", "myName", "enabled"]);
  if (cfg.enabled === false) return;
  await new Promise(r => (document.body ? r() : addEventListener("DOMContentLoaded", r, { once: true })));

  const analyze = body => new Promise((resolve, reject) =>
    chrome.runtime.sendMessage({ type: "analyze", body }, res => (res && !res.error && !res.off ? resolve(res) : reject(res))));
  const guard = NightGuardLive.create({ analyze, app: adapter.app, lang: cfg.lang || "en" });

  let lastKey = "", lastConvo = location.pathname + location.search;
  const scan = () => {
    // Opening another conversation (new URL) starts a fresh warning memory for that contact.
    const convo = location.pathname + location.search;
    if (convo !== lastConvo) { lastConvo = convo; lastKey = ""; guard.reset(); }
    const msgs = adapter.read(cfg.myName || "").filter(m => m.text.trim()).slice(-12);
    const key = msgs.map(m => m.from + ":" + m.text).join("|");
    if (key !== lastKey) { lastKey = key; guard.update(msgs); }
  };
  let t = null;
  new MutationObserver(() => { clearTimeout(t); t = setTimeout(scan, 700); })
    .observe(document.body, { childList: true, subtree: true, characterData: true });
  scan();
})();
