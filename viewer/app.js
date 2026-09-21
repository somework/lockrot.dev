/*
 * The viewer's own half: it reads a document from the reader, or from the link the reader
 * followed, and hands it to the sandboxed frame that renders it.
 *
 * Nothing here parses the report or draws anything. The rules it does hold to:
 *
 *   - a document that arrived in a link is never fetched, and never rendered, without the reader
 *     acting first, because a link is the one input a stranger chooses;
 *   - #url= is https only, and the host is shown before the request is made — the request comes
 *     from the reader's browser and their network, so the choice is theirs;
 *   - what the reader pastes is never written into the address bar, and a link carrying a document
 *     is built only when asked and never copied to the clipboard on its own;
 *   - every input is capped before it is parsed, and the compressed one is capped while it is
 *     being decompressed, because a few kilobytes of gzip expand to gigabytes.
 */
(function () {
  "use strict";

  // A 200-package report is about 160 KB of JSON, and the single-file page around 250 KB. These
  // are far above anything real and far below what hurts to hold in memory.
  var MAX_TEXT = 24 * 1024 * 1024;
  var MAX_INFLATED = 8 * 1024 * 1024;
  // Slack and Telegram cut a message around 4,000 characters, and a browser's own limit is far
  // higher but not infinite. Past this a link is worth warning about rather than forbidding.
  var LINK_COMFORTABLE = 4000;

  // How long to wait for the renderer before saying so. It loads two local files and draws; a
  // second is generous. This exists because the alternative to a message is an empty stage and no
  // explanation, which is what a blocked script or a renderer that threw would otherwise look like.
  var RENDER_PATIENCE = 8000;

  var el = function (id) { return document.getElementById(id); };
  var frame = el("frame");
  var bundle = null;
  var frameReady = false;
  var pending = null;
  var watchdog = null;

  /* ---------- telling the reader what went wrong ---------- */

  function problem(text) {
    var box = el("problem");
    box.textContent = text;
    box.hidden = false;
  }

  function clearProblem() {
    el("problem").hidden = true;
  }

  /* ---------- the shape of a lockrot document ---------- */

  // Two things are called a report. `--format=json` writes the document itself; the page written
  // by `--format=html` carries that document under a `report` key, beside the release branches the
  // page draws. The renderer wants the second shape, so the first is wrapped.
  function asBundle(parsed) {
    if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
      throw new Error("that is not a lockrot document: the JSON is not an object");
    }
    if (parsed.report && typeof parsed.report === "object") {
      return parsed;
    }
    if (parsed.lockrot && Array.isArray(parsed.findings)) {
      return { report: parsed };
    }
    throw new Error(
      "that JSON is not a lockrot report: it has neither a report key nor the findings and " +
      "lockrot keys a report opens with"
    );
  }

  // The payload of a --format=html page sits on one line in a script tag, and lockrot escapes every
  // "</" inside it, so the first closing tag after it really is the end of the payload.
  var PAYLOAD = /<script id="lockrot-data" type="application\/json">([\s\S]*?)<\/script>/;

  function documentFrom(text) {
    var trimmed = text.replace(/^﻿/, "").trim();
    if (trimmed === "") throw new Error("there is nothing to render: the input is empty");

    var json = trimmed;
    if (trimmed.charAt(0) === "<") {
      var found = PAYLOAD.exec(trimmed);
      if (!found) {
        throw new Error(
          "that looks like a web page but carries no lockrot payload. A report page written by " +
          "--format=html has one; an ordinary page does not."
        );
      }
      json = found[1];
    }

    var parsed;
    try {
      parsed = JSON.parse(json);
    } catch (err) {
      throw new Error("that is not valid JSON: " + err.message);
    }
    return asBundle(parsed);
  }

  /* ---------- handing it to the frame ---------- */

  function show(document_, where) {
    bundle = document_;
    el("originWhere").textContent = where;
    el("intro").hidden = true;
    el("ask").hidden = true;
    el("sharePanel").hidden = true;
    el("report").hidden = false;
    send();
  }

  function send() {
    if (!bundle) return;
    if (!frameReady) { pending = true; return; }
    pending = null;
    clearTimeout(watchdog);
    watchdog = setTimeout(function () {
      problem(
        "the renderer did not come back. The document was handed to it, but nothing was drawn — " +
        "reload the page, and if it happens again the document is one this renderer cannot read."
      );
    }, RENDER_PATIENCE);
    frame.contentWindow.postMessage({ lockrot: "render", payload: bundle }, "*");
  }

  // Readiness is taken from the frame's own load event as well as from its greeting. The greeting
  // is sent once, while this file is the last script in the page: on a warm cache the frame can
  // finish loading and speak before the listener below exists, and a greeting nobody heard would
  // leave the stage empty for good, with nothing said. The load event cannot be missed that way,
  // and by the time it fires the frame's listener is in place — its script is part of its markup.
  function ready() {
    if (frameReady) return;
    frameReady = true;
    if (pending) send();
  }

  frame.addEventListener("load", ready);

  window.addEventListener("message", function (event) {
    if (event.source !== frame.contentWindow) return;
    var message = event.data;
    if (!message || typeof message.lockrot !== "string") return;
    if (message.lockrot === "ready") {
      ready();
    } else if (message.lockrot === "rendered") {
      clearTimeout(watchdog);
      clearProblem();
    } else if (message.lockrot === "error") {
      clearTimeout(watchdog);
      problem("the renderer could not show the document: " + String(message.reason));
      el("intro").hidden = false;
    }
  });

  /* ---------- what the reader hands over ---------- */

  function fromText(text, where) {
    clearProblem();
    if (text.length > MAX_TEXT) {
      problem("that input is " + Math.round(text.length / 1048576) + " MB, which is far larger " +
        "than any lockrot report; nothing was parsed");
      return;
    }
    try {
      show(documentFrom(text), where);
    } catch (err) {
      problem(err.message);
    }
  }

  function fromFile(file) {
    if (!file) return;
    if (file.size > MAX_TEXT) {
      problem("that file is " + Math.round(file.size / 1048576) + " MB, which is far larger than " +
        "any lockrot report; it was not read");
      return;
    }
    file.text().then(function (text) {
      fromText(text, "Read from the file " + file.name + ", which you chose on this machine.");
    }, function (err) {
      problem("that file could not be read: " + err.message);
    });
  }

  el("render").addEventListener("click", function () {
    fromText(el("json").value, "Pasted into this page by you.");
  });

  el("pick").addEventListener("click", function () { el("file").click(); });
  el("file").addEventListener("change", function () { fromFile(el("file").files[0]); });

  var drop = el("drop");
  ["dragenter", "dragover"].forEach(function (name) {
    drop.addEventListener(name, function (event) {
      event.preventDefault();
      drop.classList.add("over");
    });
  });
  ["dragleave", "drop"].forEach(function (name) {
    drop.addEventListener(name, function () { drop.classList.remove("over"); });
  });
  drop.addEventListener("drop", function (event) {
    event.preventDefault();
    fromFile(event.dataTransfer && event.dataTransfer.files[0]);
  });

  el("again").addEventListener("click", function () {
    // report.js renders once, at load, so another document means another frame.
    bundle = null;
    frameReady = false;
    pending = null;
    clearTimeout(watchdog);
    // The address still carries the document that was just closed, and a refresh would bring it
    // back over whatever is opened next. Replaced rather than assigned, so this does not read as a
    // new link and send the page round the hashchange reload below.
    if (location.hash) {
      try {
        history.replaceState(null, "", location.pathname);
      } catch (err) { /* an address this page may not rewrite */ }
    }
    frame.src = frame.src;
    el("report").hidden = true;
    el("intro").hidden = false;
    el("json").value = "";
    clearProblem();
  });

  /* ---------- a link that carries the document ---------- */

  function base64url(bytes) {
    var binary = "";
    for (var i = 0; i < bytes.length; i += 1) binary += String.fromCharCode(bytes[i]);
    return btoa(binary).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
  }

  function unbase64url(text) {
    var padded = text.replace(/-/g, "+").replace(/_/g, "/");
    while (padded.length % 4) padded += "=";
    var binary = atob(padded);
    var bytes = new Uint8Array(binary.length);
    for (var i = 0; i < binary.length; i += 1) bytes[i] = binary.charCodeAt(i);
    return bytes;
  }

  function gzip(text) {
    if (typeof CompressionStream !== "function") {
      return Promise.reject(new Error("this browser cannot compress; a link cannot be built here"));
    }
    var stream = new Blob([text]).stream().pipeThrough(new CompressionStream("gzip"));
    return new Response(stream).arrayBuffer().then(function (buffer) {
      return new Uint8Array(buffer);
    });
  }

  // Read the decompressed document a chunk at a time and stop at the cap. Decompressing first and
  // measuring afterwards is how a few kilobytes of gzip become gigabytes of memory.
  function gunzip(bytes) {
    if (typeof DecompressionStream !== "function") {
      return Promise.reject(new Error("this browser cannot read a compressed link"));
    }
    var reader = new Blob([bytes]).stream()
      .pipeThrough(new DecompressionStream("gzip"))
      .getReader();
    var decoder = new TextDecoder();
    var text = "";
    var size = 0;

    function pump() {
      return reader.read().then(function (step) {
        if (step.done) {
          text += decoder.decode();
          return text;
        }
        size += step.value.length;
        if (size > MAX_INFLATED) {
          reader.cancel();
          throw new Error(
            "the document in that link expands past " + (MAX_INFLATED / 1048576) +
            " MB, which no lockrot report does; it was not read to the end"
          );
        }
        text += decoder.decode(step.value, { stream: true });
        return pump();
      });
    }
    return pump();
  }

  el("share").addEventListener("click", function () {
    var panel = el("sharePanel");
    if (!panel.hidden) { panel.hidden = true; return; }
    gzip(JSON.stringify(bundle)).then(function (packed) {
      var url = location.origin + location.pathname + "#data=" + base64url(packed);
      el("shareUrl").value = url;
      el("shareWarn").textContent =
        "This link is " + url.length.toLocaleString() + " characters and carries the whole " +
        "document inside it. Anyone who opens it sees every package, version and advisory in " +
        "this report" +
        (url.length > LINK_COMFORTABLE
          ? ". It is also longer than Slack and Telegram allow in one message, so it may be cut."
          : ".");
      panel.hidden = false;
    }, function (err) {
      problem(err.message);
    });
  });

  /* ---------- what the link asked for ---------- */

  function hashValue(name) {
    var hash = location.hash.replace(/^#/, "");
    var parts = hash.split("&");
    for (var i = 0; i < parts.length; i += 1) {
      if (parts[i].indexOf(name + "=") === 0) return parts[i].slice(name.length + 1);
    }
    return null;
  }

  function fromLinkData(encoded) {
    var bytes;
    try {
      bytes = unbase64url(encoded);
    } catch (err) {
      problem("the document in that link is not readable: its encoding is damaged");
      return;
    }
    gunzip(bytes).then(function (text) {
      try {
        show(documentFrom(text), "Carried inside the link you followed. It was not fetched from " +
          "anywhere: the whole document was in the address.");
      } catch (err) {
        problem(err.message);
      }
    }, function (err) {
      problem(err.message);
    });
  }

  function askFor(raw) {
    var url;
    try {
      url = new URL(raw);
    } catch (err) {
      problem("that link names an address that is not a URL, so nothing was requested");
      return;
    }
    if (url.protocol !== "https:") {
      problem("that link points at " + url.protocol + "//, and only https is fetched");
      return;
    }
    el("askHost").textContent = url.host;
    el("askUrl").textContent = url.href;
    el("intro").hidden = true;
    el("ask").hidden = false;

    el("askGo").addEventListener("click", function () {
      el("ask").hidden = true;
      // No credentials, no referrer: the target learns nothing about the reader beyond the request
      // itself, and a report behind a session is not silently pulled out of it.
      fetch(url.href, { credentials: "omit", referrerPolicy: "no-referrer", redirect: "follow" })
        .then(function (response) {
          if (!response.ok) throw new Error(url.host + " answered " + response.status);
          return response.text();
        })
        .then(function (text) {
          fromText(text, "Fetched by your browser from " + url.host + ", after you asked for it.");
        })
        .catch(function (err) {
          el("intro").hidden = false;
          problem("that document could not be fetched: " + err.message +
            ". A host that does not send CORS headers cannot be read by a browser, whoever asks.");
        });
    }, { once: true });

    el("askNo").addEventListener("click", function () {
      el("ask").hidden = true;
      el("intro").hidden = false;
    }, { once: true });
  }

  // A link pasted into the address bar of a viewer that is already open changes only the fragment,
  // which navigates nothing: without this, following a shared link from this page looks broken.
  // Reloading rather than re-reading the hash in place starts the frame over too, and the frame is
  // the one thing that cannot be asked to render twice.
  window.addEventListener("hashchange", function () { location.reload(); });

  var data = hashValue("data");
  var remote = hashValue("url");
  if (data) {
    fromLinkData(data);
  } else if (remote) {
    askFor(decodeURIComponent(remote));
  }
})();
