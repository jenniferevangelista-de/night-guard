const ids = ["enabled", "server", "lang", "myName"];
chrome.storage.local.get(ids).then(cfg => {
  document.getElementById("enabled").checked = cfg.enabled !== false;
  document.getElementById("server").value = cfg.server || "http://localhost:8765";
  document.getElementById("lang").value = cfg.lang || "en";
  document.getElementById("myName").value = cfg.myName || "";
});
ids.forEach(id => document.getElementById(id).addEventListener("change", async () => {
  const el = document.getElementById(id);
  await chrome.storage.local.set({ [id]: el.type === "checkbox" ? el.checked : el.value.trim() });
  document.getElementById("saved").textContent = "Saved. Reload the chat tab.";
}));
