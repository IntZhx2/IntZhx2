import { marked } from "marked";
import DOMPurify from "dompurify";
import hljs from "highlight.js/lib/core";
import python from "highlight.js/lib/languages/python";
import javascript from "highlight.js/lib/languages/javascript";
import typescript from "highlight.js/lib/languages/typescript";
import json from "highlight.js/lib/languages/json";
hljs.registerLanguage("python", python);
hljs.registerLanguage("javascript", javascript);
hljs.registerLanguage("typescript", typescript);
hljs.registerLanguage("json", json);
const renderer = new marked.Renderer();
renderer.code = ({ text, lang }) => {
  const language = lang?.split(" ")[0] || "";
  const content = hljs.getLanguage(language)
    ? hljs.highlight(text, { language }).value
    : hljs.highlightAuto(text).value;
  return `<pre><code class="hljs">${content}</code></pre>`;
};
export function markdown(text: string) {
  return DOMPurify.sanitize(
    marked.parse(text, { renderer, breaks: true, async: false }),
    { FORBID_TAGS: ["img", "style", "form", "input"], FORBID_ATTR: ["style"] },
  );
}
