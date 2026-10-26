/* Small, deliberately limited Markdown renderer. Raw HTML is always text.
 * Parse source tokens once: generated HTML never goes through inline rewrites.
 * No DOM or dependencies, so the same renderer can be tested in Node.
 */
(function (root) {
  "use strict";

  function escapeHtml(value) {
    return String(value ?? "").replace(/[&<>"']/g, (ch) => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
    })[ch]);
  }

  function safeHref(value) {
    // Reject browser-normalized controls, whitespace and backslash authority tricks.
    // Entities are not decoded here; escaping & prevents a second HTML interpretation.
    if (!value || /[\s\u0000-\u001f\u007f-\u009f\\]/u.test(value)) return null;
    if (/^\/(?!\/)/.test(value) || /^[#?]/.test(value)) return value;
    if (!/^(https?:\/\/|mailto:)/i.test(value)) return null;
    try {
      const url = new URL(value);
      if (["http:", "https:"].includes(url.protocol) && url.hostname) return value;
      if (url.protocol === "mailto:" && url.pathname && !/%0[ad]/i.test(value)) return value;
    } catch (_) { /* Invalid URLs stay readable as plain text. */ }
    return null;
  }

  function closingDelimiter(text, start, open, close) {
    let depth = 1;
    for (let i = start; i < text.length; i++) {
      if (text[i] === "\\") { i++; continue; }
      if (text[i] === open) depth++;
      if (text[i] === close && --depth === 0) return i;
    }
    return -1;
  }

  function codeSpan(text, start) {
    const marker = text.slice(start).match(/^`+/)[0];
    let end = text.indexOf(marker, start + marker.length);
    while (end !== -1 && (text[end - 1] === "`" || text[end + marker.length] === "`")) {
      end = text.indexOf(marker, end + marker.length);
    }
    return { marker, end };
  }

  function emphasisEnd(text, start, marker) {
    for (let i = start; i < text.length; i++) {
      if (text[i] === "\\") { i++; continue; }
      if (text[i] === "`") {
        const span = codeSpan(text, i);
        if (span.end !== -1) { i = span.end + span.marker.length - 1; continue; }
      }
      if (text[i] === "[") {
        const labelEnd = closingDelimiter(text, i + 1, "[", "]");
        if (labelEnd !== -1 && text[labelEnd + 1] === "(") {
          const hrefEnd = closingDelimiter(text, labelEnd + 2, "(", ")");
          if (hrefEnd !== -1) { i = hrefEnd; continue; }
        }
      }
      if (text.startsWith(marker, i)) return i;
    }
    return -1;
  }

  function inline(text, allowLinks = true, depth = 0) {
    if (depth > 16) return escapeHtml(text);
    let html = "";
    for (let i = 0; i < text.length;) {
      if (text[i] === "\\" && i + 1 < text.length) {
        html += escapeHtml(text[i + 1]);
        i += 2;
        continue;
      }
      if (text[i] === "`") {
        const { marker, end } = codeSpan(text, i);
        if (end !== -1) {
          html += `<code class="md-inline-code">${escapeHtml(text.slice(i + marker.length, end))}</code>`;
          i = end + marker.length;
          continue;
        }
      }
      if (allowLinks && text[i] === "[") {
        const labelEnd = closingDelimiter(text, i + 1, "[", "]");
        if (labelEnd !== -1 && text[labelEnd + 1] === "(") {
          const hrefEnd = closingDelimiter(text, labelEnd + 2, "(", ")");
          if (hrefEnd !== -1) {
            const href = safeHref(text.slice(labelEnd + 2, hrefEnd));
            const label = inline(text.slice(i + 1, labelEnd), false, depth + 1);
            html += href === null ? label : `<a href="${escapeHtml(href)}" target="_blank" rel="noopener noreferrer" class="md-link">${label}</a>`;
            i = hrefEnd + 1;
            continue;
          }
        }
      }
      const marker = text.startsWith("**", i) ? "**" : text[i] === "*" ? "*" : null;
      if (marker) {
        const end = emphasisEnd(text, i + marker.length, marker);
        if (end > i + marker.length) {
          const tag = marker === "**" ? "strong" : "em";
          html += `<${tag}>${inline(text.slice(i + marker.length, end), allowLinks, depth + 1)}</${tag}>`;
          i = end + marker.length;
          continue;
        }
      }
      html += escapeHtml(text[i++]);
    }
    return html;
  }

  function render(raw) {
    const lines = String(raw ?? "").replace(/\r\n?/g, "\n").split("\n");
    const output = [];
    let list = null;
    function closeList() {
      if (list) output.push(`</${list}>`);
      list = null;
    }
    for (let i = 0; i < lines.length; i++) {
      const line = lines[i];
      const fence = line.match(/^\s{0,3}(`{3,}|~{3,})(.*)$/);
      if (fence) {
        closeList();
        const code = [];
        const closing = new RegExp(`^\\s{0,3}${fence[1][0]}{${fence[1].length},}\\s*$`);
        while (++i < lines.length && !closing.test(lines[i])) code.push(lines[i]);
        const language = fence[2].trim();
        const attr = /^[\w-]+$/.test(language) ? ` class="lang-${language}"` : "";
        output.push(`<pre class="code-block"><code${attr}>${escapeHtml(code.join("\n"))}</code></pre>`);
        continue;
      }
      if (line.trim().startsWith("|") && line.trim().endsWith("|")) {
        closeList();
        const rows = [];
        do {
          rows.push(lines[i].trim().slice(1, -1).split("|").map((cell) => cell.trim()));
          i++;
        } while (i < lines.length && /^\s*\|.*\|\s*$/.test(lines[i]));
        i--;
        const header = rows.shift();
        if (rows[0] && rows[0].every((cell) => /^:?-+:?$/.test(cell))) rows.shift();
        output.push('<div class="table-container"><table class="md-table"><thead><tr>' +
          header.map((cell) => `<th>${inline(cell)}</th>`).join("") + '</tr></thead><tbody>' +
          rows.map((row) => '<tr>' + row.map((cell) => `<td>${inline(cell)}</td>`).join("") + '</tr>').join("") +
          '</tbody></table></div>');
        continue;
      }
      const item = line.match(/^\s*(?:([-*+•])|\d+\.)\s+(.*)$/);
      if (item) {
        const type = item[1] ? "ul" : "ol";
        if (list !== type) { closeList(); output.push(`<${type} class="md-${type}">`); list = type; }
        output.push(`<li>${inline(item[2])}</li>`);
        continue;
      }
      closeList();
      const heading = line.match(/^(#{1,6})\s+(.*)$/);
      const quote = line.match(/^>\s?(.*)$/);
      if (/^(?:-{3,}|\*{3,}|_{3,})$/.test(line.trim())) output.push('<hr class="md-hr" />');
      else if (heading) {
        const level = heading[1].length;
        output.push(`<h${level} class="md-h${level}">${inline(heading[2])}</h${level}>`);
      } else if (quote) output.push(`<blockquote class="md-quote">${inline(quote[1])}</blockquote>`);
      else if (line.trim()) output.push(`<p class="md-p">${inline(line)}</p>`);
    }
    closeList();
    return output.join("\n");
  }

  const api = Object.freeze({ render, escapeHtml, safeHref });
  if (typeof module === "object" && module.exports) module.exports = api;
  else root.SafeMarkdown = api;
})(typeof globalThis === "object" ? globalThis : this);
