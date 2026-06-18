// Server-only: read the Knowledge + Recursive Learning vault markdown and render to HTML.
import fs from "fs";
import path from "path";
import { marked } from "marked";

// Order files for nice reading flow (others appended alphabetically).
const ORDER = {
  knowledge: ["README.md", "media_buyer_playbook.md", "metric_benchmarks.md", "metric_glossary.md", "meta_platform_2026.md", "sources_and_updates.md"],
  learning: ["README.md", "decision_log.md", "lessons_learned.md"],
};

function loadVault(dir) {
  const base = path.join(process.cwd(), "content", dir);
  let files = [];
  try { files = fs.readdirSync(base).filter((f) => f.endsWith(".md")); } catch { return []; }
  const ordered = [...(ORDER[dir] || []).filter((f) => files.includes(f)), ...files.filter((f) => !(ORDER[dir] || []).includes(f))];
  return ordered.map((f) => {
    const md = fs.readFileSync(path.join(base, f), "utf8");
    return { file: f, html: marked.parse(md) };
  });
}

export function getVaults() {
  return {
    knowledge: loadVault("knowledge"),
    learning: loadVault("learning"),
  };
}
