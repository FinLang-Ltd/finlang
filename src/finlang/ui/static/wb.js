/* FinLang Workbench — shared page chrome (Oct 2026 redesign).
 *
 * Puts the lockup into the header, shows the engine status beside the tabs,
 * and holds flReason - the one place every screen turns an engine refusal into
 * words. The lockup and status fail soft; the failure messages need this file.
 */
"use strict";
/* The engine's reason for a refusal, in its own words: the last FATAL line of
   its output, else its last error line, else the API's short message - never
   the JSON wrapper. Shared by every screen so a failure reads the same
   wherever it happens. */
function flReason(body){
  const det = body && body.detail;
  const d = typeof det === "string" ? det
          : det && det.stderr ? det.stderr : JSON.stringify(det, null, 2);
  // FastAPI's own validation errors: a list of {loc, msg}
  if (Array.isArray(det))
    return det.map(x => (Array.isArray(x.loc) ? x.loc.filter(p => p !== "body").join(".") + ": " : "") +
                        (x.msg || JSON.stringify(x))).join("; ");
  const lines = String(d).split("\n").map(l => l.trim()).filter(Boolean);
  const fatal = lines.filter(l => /^FATAL: /.test(l)).pop();
  if (fatal) return fatal.slice(7);
  const err = lines.filter(l => !/warning:/i.test(l) &&
    /error|unknown|missing|cannot|invalid|not found|no such/i.test(l)).pop();
  return err || (det && det.message) || String(d);
}
/* A request that never got an answer the page can read: unreachable server,
   or a reply that isn't the API's JSON. One wording for every screen. */
function flUnreachable(e){
  return `The Workbench server didn't give a usable answer (${String(e && e.message || e)}). ` +
         "Check that finlang-ui is still running, then try again.";
}
/* r.json() whose failure IS a failure: a reply that isn't the API's JSON (an
   HTML error page, a proxy page - even one sent with HTTP 200) throws, so every
   caller's catch says the server didn't answer, and nothing renders it as a
   result. Returning an error-shaped body instead let an HTTP 200 page read as
   success ("every row was claimed by a rule"). */
/* An HTTP error the API answered in JSON (its timeout is 504 {"detail":
   "Subprocess exceeded 300s timeout."}): the engine's reason in words, plus
   what to do next - never the JSON itself. */
function flFailure(body, status){
  const why = flReason(body).trim();
  const advice = status === 504
    ? "The engine took too long to answer. Try again; if it keeps happening, restart finlang-ui."
    : "Try again; if it keeps happening, restart finlang-ui.";
  return why + (/[.!?]$/.test(why) ? " " : ". ") + advice;
}
/* The rule names a /rules/validate success can show: every rule it counts,
   from the engine's structured rules (rule_names is parsed from the CLI's
   printout and drops a name starting with "...", splits names at commas, stops
   at ten). null when the reply cannot name what it counts: no count, rules
   missing or short, or a name with nothing visible in it (blank, a soft
   hyphen, a control character). Shared, so every screen that shows this reply
   names rules the same way - a check made on one screen only left the other
   ticking drafts it could not name (adversarial pass, 2 Nov). */
function flRuleNames(b){
  if (!b || typeof b.rule_count !== "number" || !Array.isArray(b.rules) || b.rules.length !== b.rule_count)
    return null;
  const names = b.rules.map(x => x && x.name);
  // A selector or a braille blank alone draws no ink. Test the whole list
  // before either screen truncates it, and return the names as written.
  const visibleCharacter = /[^\p{C}\p{Z}\s\p{Default_Ignorable_Code_Point}\u2800]/u;
  return names.every(n => typeof n === "string" && visibleCharacter.test(n)) ? names : null;
}
async function flJson(r){
  try { return await r.json(); }
  catch (e){ throw new Error(`HTTP ${r.status}, not a FinLang reply`); }
}
/* the engine status in the header: checked on load, and again whenever a
   request fails to reach the server - so the header never says "running"
   beside a run that could not reach it */
function flStatus(){
  const st = document.getElementById("wbstatus");
  if (!st) return;
  st.classList.remove("ok", "warn");
  fetch("/health").then(r => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json(); }).then(h => {
    st.classList.add(h.cli_resolved ? "ok" : "warn");
    st.title = h.cli_resolved
      ? "The engine this page calls was found and answered. Everything runs on this machine."
      : "The server answered, but could not find the FinLang engine to call.";
    st.lastElementChild.textContent = h.cli_resolved
      ? `Engine ${h.version}, running on this machine`
      : `Engine ${h.version}: not found`;
  }).catch(() => {
    st.classList.add("warn");
    st.title = "The page could not reach the Workbench server.";
    st.lastElementChild.textContent = "Engine not reachable";
  });
}
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

  flStatus();
})();
