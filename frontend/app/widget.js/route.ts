import { NextResponse } from "next/server";

export function GET() {
  const script = String.raw`
(function () {
  var script = document.currentScript;
  if (!script) return;

  var scriptUrl = new URL(script.src);
  var origin = scriptUrl.origin;
  var slug = script.dataset.slug || scriptUrl.searchParams.get("slug");
  var targetSelector = script.dataset.target || scriptUrl.searchParams.get("target");
  if (!slug) {
    console.warn("cipher widget: missing profile slug");
    return;
  }

  var host = targetSelector ? document.querySelector(targetSelector) : null;
  if (!host) {
    host = document.createElement("div");
    script.parentNode.insertBefore(host, script.nextSibling);
  }
  host.setAttribute("data-cipher-widget-mounted", "true");

  var root = host.attachShadow ? host.attachShadow({ mode: "open" }) : host;
  root.innerHTML = '<style>' +
    ':host{all:initial;color-scheme:light dark}' +
    '.cw{box-sizing:border-box;width:100%;max-width:560px;border:1px solid #d8dee4;border-radius:8px;background:#fff;color:#17202a;font-family:Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;padding:18px;box-shadow:0 16px 40px rgba(15,23,42,.10)}' +
    '.cw *{box-sizing:border-box}' +
    '.eyebrow{display:inline-flex;border:1px solid #d8dee4;border-radius:999px;color:#57606a;font-size:12px;font-weight:600;padding:4px 8px;margin-bottom:10px}' +
    'h3{font-size:18px;line-height:1.25;margin:0 0 6px;color:#0f172a}' +
    'p{font-size:14px;line-height:1.55;margin:0;color:#57606a}' +
    '.form{display:grid;gap:10px;margin-top:14px}' +
    'textarea{width:100%;min-height:92px;border:1px solid #d8dee4;border-radius:8px;color:#17202a;background:#fff;font:inherit;font-size:14px;line-height:1.45;padding:11px;resize:vertical}' +
    'button{align-items:center;background:#166534;border:0;border-radius:8px;color:#fff;cursor:pointer;display:inline-flex;font:inherit;font-size:14px;font-weight:700;justify-content:center;min-height:42px;padding:0 14px}' +
    'button:disabled{cursor:not-allowed;opacity:.55}' +
    '.answer{border-top:1px solid #d8dee4;display:grid;gap:12px;margin-top:16px;padding-top:14px}' +
    '.meta{display:flex;flex-wrap:wrap;gap:8px}' +
    '.pill{border:1px solid #d8dee4;border-radius:999px;color:#57606a;font-size:12px;font-weight:600;padding:4px 8px;text-transform:capitalize}' +
    'ul{display:grid;gap:8px;margin:0;padding-left:18px}' +
    'li{color:#334155;font-size:13px;line-height:1.45}' +
    '.cols{display:grid;gap:14px;grid-template-columns:1fr 1fr}' +
    '.label{color:#0f172a;font-size:13px;font-weight:700;margin-bottom:8px}' +
    '.error{border:1px solid #f1a8a8;border-radius:8px;color:#991b1b;margin-top:12px;padding:10px}' +
    '@media (prefers-color-scheme:dark){.cw{background:#0b1220;border-color:#263241;color:#e5edf6;box-shadow:none}.eyebrow,.pill{border-color:#263241;color:#9aa8b8}h3,.label{color:#f8fafc}p,li{color:#b5c1cf}textarea{background:#0f172a;border-color:#263241;color:#f8fafc}button{background:#3dd68c;color:#062015}.answer{border-color:#263241}.error{border-color:#7f1d1d;color:#fecaca}}' +
    '@media (max-width:520px){.cols{grid-template-columns:1fr}}' +
    '</style>' +
    '<div class="cw">' +
    '<div class="eyebrow">cipher recruiter check</div>' +
    '<h3>Ask if this candidate fits a role</h3>' +
    '<p>Use verified profile evidence to check role fit, confidence, evidence, and interview follow-ups.</p>' +
    '<div class="form">' +
    '<textarea aria-label="Recruiter question" placeholder="Is this candidate qualified for a backend new grad role?"></textarea>' +
    '<button type="button">Ask</button>' +
    '</div>' +
    '<div class="mount" aria-live="polite"></div>' +
    '</div>';

  var textarea = root.querySelector("textarea");
  var button = root.querySelector("button");
  var mount = root.querySelector(".mount");

  function escapeHtml(value) {
    return String(value || "").replace(/[&<>"']/g, function (char) {
      return ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[char];
    });
  }

  function renderAnswer(data) {
    var evidence = (data.evidence || []).map(function (item) { return "<li>" + escapeHtml(item) + "</li>"; }).join("");
    var questions = (data.verification_questions || []).map(function (item) { return "<li>" + escapeHtml(item) + "</li>"; }).join("");
    mount.innerHTML = '<div class="answer">' +
      '<div class="meta"><span class="pill">' + escapeHtml((data.recommendation || "").replace("_", " ")) + '</span><span class="pill">' + escapeHtml(data.confidence) + ' confidence</span></div>' +
      '<p>' + escapeHtml(data.answer) + '</p>' +
      '<div class="cols"><div><div class="label">Evidence</div><ul>' + evidence + '</ul></div><div><div class="label">Verify</div><ul>' + questions + '</ul></div></div>' +
      '</div>';
  }

  function renderError(message) {
    mount.innerHTML = '<div class="error">' + escapeHtml(message) + '</div>';
  }

  button.addEventListener("click", function () {
    var question = textarea.value.trim();
    if (!question) return;
    button.disabled = true;
    button.textContent = "Checking...";
    mount.innerHTML = "";
    fetch(origin + "/api/public/profiles/" + encodeURIComponent(slug) + "/ask", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ question: question })
    })
      .then(function (response) {
        if (!response.ok) throw new Error("Unable to answer this question right now.");
        return response.json();
      })
      .then(renderAnswer)
      .catch(function (error) { renderError(error.message || "Unable to answer this question right now."); })
      .finally(function () {
        button.disabled = false;
        button.textContent = "Ask";
      });
  });
})();
`;

  return new NextResponse(script, {
    headers: {
      "content-type": "application/javascript; charset=utf-8",
      "cache-control": "public, max-age=300",
    },
  });
}
