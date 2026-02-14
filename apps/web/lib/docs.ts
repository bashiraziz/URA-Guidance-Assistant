import fs from "node:fs/promises";
import path from "node:path";
import matter from "gray-matter";

export type DocsNode = {
  path: string;
  title: string;
  category: string;
};

const DOCS_ROOT = path.resolve(process.cwd(), "..", "..", "docs");

export async function getDocsTree(): Promise<DocsNode[]> {
  const out: DocsNode[] = [];
  async function walk(dir: string) {
    const entries = await fs.readdir(dir, { withFileTypes: true });
    for (const entry of entries) {
      const fullPath = path.join(dir, entry.name);
      if (entry.isDirectory()) {
        await walk(fullPath);
        continue;
      }
      if (!entry.name.endsWith(".md")) {
        continue;
      }
      const relative = path.relative(DOCS_ROOT, fullPath).replaceAll("\\", "/");
      const source = await fs.readFile(fullPath, "utf-8");
      const parsed = matter(source);
      out.push({
        path: relative,
        title: String(parsed.data.title || entry.name.replace(/\.md$/, "")),
        category: String(parsed.data.category || "General")
      });
    }
  }
  await walk(DOCS_ROOT);
  return out.sort((a, b) => a.path.localeCompare(b.path));
}

export async function getDocByPath(docPath: string) {
  const safePath = path.resolve(DOCS_ROOT, docPath);
  if (!safePath.startsWith(DOCS_ROOT)) {
    throw new Error("Invalid docs path");
  }
  const source = await fs.readFile(safePath, "utf-8");
  const parsed = matter(source);
  return {
    path: docPath,
    title: String(parsed.data.title || path.basename(docPath, ".md")),
    category: String(parsed.data.category || "General"),
    content: parsed.content
  };
}
