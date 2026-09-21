/*
 * The only code in the frame that is not lockrot's.
 *
 * report.js reads #lockrot-data once, at load, and renders straight away: there is no entry point
 * to call again with another document. So the document has to be in the DOM before the renderer
 * runs, and this file is what puts it there — it announces the frame is ready, waits for the page
 * that embedded it to post a document, writes it into the empty script tag, and only then appends
 * lib.js and report.js, in that order, because report.js reads LockrotLib at its first line.
 *
 * The frame is sandboxed without allow-same-origin, so its origin is opaque: it cannot read
 * lockrot.dev's DOM or storage, and its CSP forbids it every kind of network access. That is the
 * point — a flaw in the thousand lines of string concatenation next door cannot carry the reader's
 * dependency inventory anywhere. Nothing here may widen that.
 */
(function () {
  "use strict";

  var rendered = false;

  function tell(message) {
    // The parent's origin is not knowable from inside an opaque origin, and "*" is safe in this
    // direction: these messages carry a status, never the document.
    try {
      window.parent.postMessage(message, "*");
    } catch (err) {
      /* no parent to tell */
    }
  }

  function fail(reason) {
    tell({ lockrot: "error", reason: reason });
  }

  function load(src) {
    return new Promise(function (resolve, reject) {
      var script = document.createElement("script");
      script.src = src;
      script.onload = function () { resolve(); };
      script.onerror = function () { reject(new Error(src + " did not load")); };
      document.body.appendChild(script);
    });
  }

  function render(payload) {
    var slot = document.getElementById("lockrot-data");
    if (!slot) {
      fail("the renderer's data element is missing");
      return;
    }
    // Serialised here rather than taken as text: structured clone has already parsed it, so what
    // reaches the renderer is a value this frame produced, not a string the parent composed.
    try {
      slot.textContent = JSON.stringify(payload);
    } catch (err) {
      fail("the document cannot be serialised: " + err.message);
      return;
    }

    load("lib.js")
      .then(function () { return load("report.js"); })
      .then(function () { tell({ lockrot: "rendered" }); })
      .catch(function (err) { fail(err.message); });
  }

  window.addEventListener("message", function (event) {
    // The embedder is the only window that may speak to this frame. Comparing the source window
    // is what works from an opaque origin, where the parent's origin string is not ours to pin.
    if (event.source !== window.parent) return;
    var message = event.data;
    if (!message || message.lockrot !== "render") return;

    if (rendered) {
      // report.js has no second pass, so a new document means a new frame. The parent reloads.
      fail("this frame has already rendered; reload it for another document");
      return;
    }
    rendered = true;
    render(message.payload);
  });

  tell({ lockrot: "ready" });
})();
