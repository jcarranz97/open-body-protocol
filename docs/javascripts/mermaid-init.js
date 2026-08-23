/*
 * Mermaid rendering for the TAMALAB docs.
 *
 * Why this file exists: Material for MkDocs 9.7 has a built-in Mermaid
 * integration, but on the sibling project (Piezario) it swapped every fence
 * for an empty <div class="mermaid"></div> and never injected an SVG. So we
 * emit the fences as plain divs (see mkdocs.yml -> fence_div_format) and
 * drive Mermaid ourselves. Material's integration keys on
 * <pre class="mermaid">, which we never produce, so the two cannot collide.
 *
 * It also re-renders on the light/dark palette toggle, which is the one
 * thing you lose by not using the built-in integration.
 */
(function () {
  "use strict";

  var SELECTOR = "div.mermaid";

  function isDark() {
    var scheme = document.body.getAttribute("data-md-color-scheme");
    if (scheme) {
      return scheme === "slate";
    }
    return window.matchMedia("(prefers-color-scheme: dark)").matches;
  }

  function configure() {
    window.mermaid.initialize({
      startOnLoad: false,
      // "base" + explicit variables keeps the diagrams on TAMALAB's indigo
      // rather than Mermaid's default lavender, in both palettes.
      theme: "base",
      themeVariables: isDark()
        ? {
            background: "#0a0a0a",
            primaryColor: "#312e81",
            primaryTextColor: "#f5f5f5",
            primaryBorderColor: "#6366f1",
            secondaryColor: "#1f2937",
            tertiaryColor: "#171717",
            lineColor: "#a1a1aa",
            textColor: "#f5f5f5",
            mainBkg: "#1e1b3a",
            nodeBorder: "#6366f1",
            clusterBkg: "#171717",
            clusterBorder: "#3f3f46",
            noteBkgColor: "#292524",
            noteTextColor: "#f5f5f5",
            noteBorderColor: "#57534e",
            // ER attribute rows have their own fills; without these they
            // default to near-white and the attribute text vanishes.
            attributeBackgroundColorOdd: "#1c1917",
            attributeBackgroundColorEven: "#262322",
          }
        : {
            background: "#ffffff",
            primaryColor: "#e0e7ff",
            primaryTextColor: "#1a1a1a",
            primaryBorderColor: "#4f46e5",
            secondaryColor: "#f4f4f5",
            tertiaryColor: "#fafafa",
            lineColor: "#52525b",
            textColor: "#1a1a1a",
            mainBkg: "#eef2ff",
            nodeBorder: "#4f46e5",
            clusterBkg: "#fafafa",
            clusterBorder: "#d4d4d8",
            noteBkgColor: "#fef3c7",
            noteTextColor: "#1a1a1a",
            noteBorderColor: "#d4d4d8",
            attributeBackgroundColorOdd: "#ffffff",
            attributeBackgroundColorEven: "#eef2ff",
          },
      flowchart: { htmlLabels: true, curve: "basis", useMaxWidth: true },
      sequence: { useMaxWidth: true, wrap: true, width: 160 },
      state: { useMaxWidth: true },
      er: { useMaxWidth: false, entityPadding: 12, minEntityWidth: 120 },
      securityLevel: "loose",
    });
  }

  function render() {
    if (!window.mermaid) {
      return;
    }
    var nodes = document.querySelectorAll(SELECTOR);
    if (!nodes.length) {
      return;
    }
    // Stash the original source the first time round: rendering replaces the
    // element's contents with an SVG, so a re-render (palette toggle) has
    // nothing left to parse unless we kept it.
    Array.prototype.forEach.call(nodes, function (el) {
      if (el.dataset.mermaidSource === undefined) {
        el.dataset.mermaidSource = el.textContent;
      }
      el.removeAttribute("data-processed");
      el.innerHTML = el.dataset.mermaidSource;
    });
    configure();
    window.mermaid.run({ querySelector: SELECTOR, suppressErrors: false });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", render);
  } else {
    render();
  }

  // Material's palette toggle flips data-md-color-scheme on <body>.
  new MutationObserver(function (mutations) {
    for (var i = 0; i < mutations.length; i++) {
      if (mutations[i].attributeName === "data-md-color-scheme") {
        render();
        return;
      }
    }
  }).observe(document.body, { attributes: true });
})();
