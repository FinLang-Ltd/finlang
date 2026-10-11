/* FinLang Workbench — shared page chrome (Oct 2026 redesign).
 *
 * Two jobs, both cosmetic: put the lockup into the header, and show the engine
 * status beside the tabs. Every page still works if this file fails to load;
 * nothing here touches a run.
 */
"use strict";
(function () {
  // The lockup fragment ships with a white wordmark for the dark graphics frame.
  // On the light surface the wordmark follows the text colour (navy); the mark's
  // own fill (#0090ff) is untouched — it is never recoloured.
  fetch("lockup.svg").then(r => r.text()).then(t => {
    const host = document.createElement("div");
    host.style.display = "none";
    host.innerHTML = '<svg xmlns="http://www.w3.org/2000/svg"><defs><g id="lkp">' +
      t.replace(/fill="#ffffff"/gi, 'fill="currentColor"') + "</g></defs></svg>";
    document.body.appendChild(host);
  }).catch(() => {});

  const st = document.getElementById("wbstatus");
  if (!st) return;
  fetch("/health").then(r => r.json()).then(h => {
    st.classList.add(h.cli_resolved ? "ok" : "warn");
    st.title = h.cli_resolved
      ? "The engine this page calls was found and answered. Everything runs on this machine."
      : "The server answered, but could not find the FinLang engine to call.";
    st.lastElementChild.textContent = h.cli_resolved
      ? `Engine ${h.version}, running on this machine`
      : `Engine ${h.version}: not found`;
  }).catch(() => {
    st.classList.add("warn");
    st.lastElementChild.textContent = "Engine not reachable";
  });
})();
