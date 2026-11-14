/* Landing-page behaviour: a live scoring demo against /demo/analyze and the
   sample-set list from /demo/samples. All API data is inserted with
   textContent / createElement - never as markup. */
(function () {
  "use strict";

  var MAX_CHARS = 5000;
  var LABEL_TEXT = { positive: "Positive", neutral: "Neutral", negative: "Negative" };
  var LABEL_GLYPH = { positive: "\u25B2", neutral: "\u25A0", negative: "\u25BC" };

  function el(tag, className, text) {
    var node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined && text !== null) node.textContent = String(text);
    return node;
  }

  function chip(label) {
    var key = LABEL_TEXT[label] ? label : "neutral";
    var span = el("span", "rl-chip rl-chip--" + key);
    span.appendChild(el("span", "rl-glyph", LABEL_GLYPH[key]));
    span.appendChild(document.createTextNode(LABEL_TEXT[key]));
    return span;
  }

  function score(value) {
    var n = Number(value) || 0;
    return (n >= 0 ? "+" : "") + n.toFixed(2);
  }

  function gauge(value) {
    var n = Math.max(-1, Math.min(1, Number(value) || 0));
    var width = Math.abs(n) * 50;
    var wrap = el("div", "rl-gauge");
    var track = el("div", "rl-gauge-track");
    track.setAttribute("role", "img");
    track.setAttribute("aria-label", "Sentiment score " + score(n) + " on a -1 to 1 scale");
    track.appendChild(el("div", "rl-gauge-zero"));
    var fill = el("div", "rl-gauge-fill rl-gauge-fill--" + (n >= 0 ? "positive" : "negative"));
    fill.style.left = (n >= 0 ? 50 : 50 - width).toFixed(2) + "%";
    fill.style.width = width.toFixed(2) + "%";
    track.appendChild(fill);
    wrap.appendChild(track);
    var axis = el("div", "rl-gauge-axis");
    axis.appendChild(el("span", null, "-1 negative"));
    axis.appendChild(el("span", null, "0"));
    axis.appendChild(el("span", null, "positive +1"));
    wrap.appendChild(axis);
    return wrap;
  }

  function wordList(fired) {
    if (!fired || !fired.length) {
      return el("p", "rl-meta", "No lexicon words fired - the review reads neutral.");
    }
    var list = el("ul", "rl-words");
    fired.forEach(function (item) {
      var value = Number(item.value) || 0;
      var kind = value > 0 ? "positive" : value < 0 ? "negative" : "neutral";
      var li = el("li", "rl-word rl-word--" + kind);
      li.appendChild(document.createTextNode(String(item.word) + " "));
      var small = el("small", null, score(value) + (item.negated ? " \u00b7 negated" : ""));
      li.appendChild(small);
      list.appendChild(li);
    });
    return list;
  }

  function aspectTable(aspects) {
    var items = (aspects && aspects.aspects) || [];
    var mentioned = items.filter(function (item) { return item.mentions; });
    if (!mentioned.length) {
      var empty = el("div", "rl-empty");
      empty.appendChild(el("strong", null, "No aspects detected"));
      empty.appendChild(document.createTextNode("This review did not mention price, quality or shipping."));
      return empty;
    }
    var table = el("table", "rl-table rl-table-stacked");
    var head = el("thead");
    var headRow = el("tr");
    ["Aspect", "Verdict", "Mentions", "Matched clause"].forEach(function (title) {
      headRow.appendChild(el("th", null, title));
    });
    head.appendChild(headRow);
    table.appendChild(head);
    var body = el("tbody");
    items.forEach(function (item) {
      var row = el("tr");
      var name = el("td");
      name.setAttribute("data-label", "Aspect");
      name.appendChild(el("strong", null, item.aspect.charAt(0).toUpperCase() + item.aspect.slice(1)));
      row.appendChild(name);
      var verdict = el("td");
      verdict.setAttribute("data-label", "Verdict");
      if (item.mentions) {
        verdict.appendChild(chip(item.label));
      } else {
        verdict.appendChild(el("span", "rl-chip rl-chip--muted", "Not mentioned"));
      }
      row.appendChild(verdict);
      var mentions = el("td", "num", item.mentions);
      mentions.setAttribute("data-label", "Mentions");
      row.appendChild(mentions);
      var why = el("td", "rl-excerpt", (item.excerpts || []).join("; ") || "-");
      why.setAttribute("data-label", "Matched clause");
      row.appendChild(why);
      body.appendChild(row);
    });
    table.appendChild(body);
    return table;
  }

  function resultCard(result) {
    var card = el("section", "rl-card rl-result");
    card.appendChild(el("span", "rl-section-label", "Result"));
    var header = el("div", "rl-card-header");
    var scoreRow = el("div", "rl-score-row");
    scoreRow.appendChild(chip(result.label));
    scoreRow.appendChild(el("span", "rl-score", score(result.score)));
    scoreRow.appendChild(el("span", "rl-meta", "sentiment score"));
    header.appendChild(scoreRow);
    header.appendChild(el("p", "rl-meta", "Scored live by this server \u00b7 nothing stored"));
    card.appendChild(header);
    card.appendChild(gauge(result.score));
    card.appendChild(el("h3", "rl-h3", "Lexicon words that fired"));
    card.appendChild(wordList(result.fired));
    card.appendChild(el("h3", "rl-h3", "Aspects"));
    card.appendChild(aspectTable(result.aspects));
    card.appendChild(el("h3", "rl-h3", "Review"));
    card.appendChild(el("p", "rl-body", result.review_text));
    return card;
  }

  function sampleCard(entry) {
    var card = el("article", "rl-card rl-sample-card");
    var header = el("div", "rl-card-header");
    header.appendChild(el("h3", "rl-h2", entry.name));
    header.appendChild(el("span", "rl-chip rl-chip--muted rl-num", entry.review_count + " reviews"));
    card.appendChild(header);
    card.appendChild(el("p", "rl-body", entry.description));
    return card;
  }

  function loadSamples() {
    var target = document.getElementById("rl-samples");
    if (!target || !window.fetch) return;
    fetch("/demo/samples", { headers: { Accept: "application/json" } })
      .then(function (response) {
        if (!response.ok) throw new Error("HTTP " + response.status);
        return response.json();
      })
      .then(function (payload) {
        var sets = (payload && payload.samples) || [];
        if (!sets.length) return;
        target.replaceChildren();
        sets.forEach(function (entry) { target.appendChild(sampleCard(entry)); });
      })
      .catch(function () {
        /* the server-rendered cards stay in place */
      });
  }

  function wireDemo() {
    var form = document.getElementById("rl-demo-form");
    var input = document.getElementById("rl-demo-text");
    var button = document.getElementById("rl-demo-submit");
    var counter = document.getElementById("rl-demo-counter");
    var error = document.getElementById("rl-demo-error");
    var result = document.getElementById("rl-demo-result");
    if (!form || !input || !button || !counter || !error || !result) return;

    var busy = false;

    function updateCounter() {
      var length = input.value.length;
      counter.textContent = length.toLocaleString() + " / " + MAX_CHARS.toLocaleString() + " characters";
    }

    function showError(message) {
      error.textContent = message;
      error.hidden = false;
    }

    function clearError() {
      error.textContent = "";
      error.hidden = true;
    }

    input.addEventListener("input", updateCounter);
    updateCounter();

    form.addEventListener("submit", function (event) {
      event.preventDefault();
      if (busy) return;
      var text = input.value.trim();
      if (!text) {
        showError("Paste a review to analyze");
        input.focus();
        return;
      }
      if (text.length > MAX_CHARS) {
        showError("Review is too long (5,000 characters max)");
        return;
      }
      busy = true;
      clearError();
      button.disabled = true;
      button.textContent = "Scoring\u2026";
      fetch("/demo/analyze", {
        method: "POST",
        headers: { "Content-Type": "application/json", Accept: "application/json" },
        body: JSON.stringify({ text: text }),
      })
        .then(function (response) {
          return response.json().then(function (body) {
            if (!response.ok) {
              throw new Error((body && body.detail) || "Could not score that review");
            }
            return body;
          });
        })
        .then(function (payload) {
          result.replaceChildren(resultCard(payload));
        })
        .catch(function (err) {
          showError(err.message || "Could not score that review");
        })
        .finally(function () {
          busy = false;
          button.disabled = false;
          button.textContent = "Score this review";
        });
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", function () { wireDemo(); loadSamples(); });
  } else {
    wireDemo();
    loadSamples();
  }
})();
