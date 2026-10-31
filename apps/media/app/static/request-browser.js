"use strict";
(() => {
  const frame = document.querySelector(".browser-frame");
  const home = document.querySelector("[data-browser-home]");
  const copy = document.querySelector("[data-copy-request]");
  const request = document.getElementById("browser-request");
  const feedback = document.querySelector("[data-browser-feedback]");

  copy.addEventListener("click", async () => {
    try {
      await navigator.clipboard.writeText(request.value);
      feedback.textContent = "Request copied. Paste it into the visible browser search.";
    } catch (_) {
      request.select();
      feedback.textContent = "Copy is unavailable here. The request text is selected for you.";
    }
  });

  const attach = () => {
    home.disabled = true;
    try {
      const doc = frame.contentDocument;
      if (!doc || doc.querySelector("[data-foxden-media-home-bridge]")) return;
      doc.addEventListener("foxden:media-home-ready", () => { home.disabled = false; });
      doc.addEventListener("foxden:media-home-unavailable", () => {
        feedback.textContent = "Browser controls are unavailable. You can navigate manually.";
      });
      doc.addEventListener("foxden:media-home-result", event => {
        home.disabled = false;
        feedback.textContent = event.detail.ok
          ? "Opening the configured media discovery page…"
          : "The browser is still connecting. Try again in a moment.";
      });
      const script = doc.createElement("script");
      script.type = "module";
      script.src = new URL(home.dataset.bridgeUrl, document.baseURI).href;
      script.dataset.foxdenMediaHomeBridge = "";
      script.addEventListener("error", () => {
        feedback.textContent = "Browser controls could not load. Reload to reconnect.";
      });
      doc.head.appendChild(script);
    } catch (_) {
      feedback.textContent = "Open this page through the Fox Den gateway to use browser controls.";
    }
  };
  frame.addEventListener("load", attach);
  if (frame.contentDocument?.readyState === "complete" && frame.contentDocument.URL !== "about:blank") attach();
  home.addEventListener("click", () => {
    home.disabled = true;
    feedback.textContent = "Returning to media discovery home…";
    frame.contentDocument.dispatchEvent(new frame.contentWindow.CustomEvent("foxden:media-home"));
  });
})();
