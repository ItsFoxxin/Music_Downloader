const result = ok => document.dispatchEvent(new CustomEvent("foxden:media-home-result", {detail:{ok}}));
try {
  const source = [...document.querySelectorAll('script[type="module"]')]
    .map(script => script.textContent).join("\n");
  const match = source.match(/import\s+UI\s+from\s+["']([^"']+)["']/);
  if (!match) throw new Error("Viewer UI module unavailable");
  const moduleUrl = new URL(match[1], document.baseURI);
  if (moduleUrl.origin !== location.origin || !moduleUrl.pathname.endsWith("/app/ui.js")) {
    throw new Error("Unexpected viewer UI module");
  }
  const {default:UI} = await import(moduleUrl.href);
  let busy = false;
  document.addEventListener("foxden:media-home", async () => {
    if (busy) return;
    if (!UI.connected || !UI.rfb || UI.rfb.viewOnly) return result(false);
    busy = true;
    const rfb = UI.rfb;
    try {
      const destination = new URL(window.frameElement.dataset.homeUrl);
      if (destination.protocol !== "https:" || destination.username || destination.password) {
        throw new Error("Invalid media browser home");
      }
      rfb.sendKey(0xff1b, "Escape");
      rfb.sendKey(0xffe3, "ControlLeft", true);
      try { rfb.sendKey(0x6c, "KeyL"); }
      finally { rfb.sendKey(0xffe3, "ControlLeft", false); }
      await new Promise(resolve => setTimeout(resolve, 150));
      if (!UI.connected || UI.rfb !== rfb) throw new Error("Viewer disconnected");
      for (const character of destination.href) rfb.sendKey(character.codePointAt(0));
      rfb.sendKey(0xff0d, "Enter");
      result(true);
    } catch (_) {
      result(false);
    } finally {
      busy = false;
    }
  });
  document.dispatchEvent(new CustomEvent("foxden:media-home-ready"));
} catch (_) {
  document.dispatchEvent(new CustomEvent("foxden:media-home-unavailable"));
}
