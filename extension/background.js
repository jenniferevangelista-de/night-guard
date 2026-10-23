// Relays chat snippets from the page to the Night Guard server running on this computer.
const DEFAULTS = { server: "http://localhost:8765", enabled: true, lang: "en", myName: "" };

chrome.runtime.onInstalled.addListener(async () => {
  const cur = await chrome.storage.local.get(Object.keys(DEFAULTS));
  await chrome.storage.local.set({ ...DEFAULTS, ...cur });
});

chrome.runtime.onMessage.addListener((msg, _sender, reply) => {
  if (msg.type !== "analyze") return;
  (async () => {
    const { server, enabled } = { ...DEFAULTS, ...(await chrome.storage.local.get(["server", "enabled"])) };
    if (!enabled) return reply({ off: true });
    // Only local servers: the extension never sends chats to the internet.
    if (!/^http:\/\/(localhost|127\.0\.0\.1)(:\d+)?$/.test(server)) return reply({ error: "server must be local" });
    try {
      const r = await fetch(`${server}/api/analyze`, {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(msg.body),
      });
      reply(r.ok ? await r.json() : { error: "HTTP " + r.status });
    } catch (e) {
      reply({ error: String(e) });
    }
  })();
  return true; // async reply
});
