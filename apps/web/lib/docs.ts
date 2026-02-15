import { Pool } from "pg";

const connStr = process.env.DATABASE_URL || "";
const pool = new Pool({
  connectionString: connStr.includes("uselibpqcompat")
    ? connStr
    : connStr.includes("?")
      ? `${connStr}&uselibpqcompat=true`
      : `${connStr}?uselibpqcompat=true`
});

/* ---------- Legacy types (kept for landing page) ---------- */

export type DocsNode = {
  path: string;
  title: string;
  category: string;
};

/* ---------- Section types ---------- */

export type SectionNode = {
  id: string;
  slug: string;
  full_path: string;
  title: string;
  level: number;
  section_ref: string | null;
  word_count: number;
  reading_time_minutes: number;
  is_placeholder: boolean;
  children: SectionNode[];
};

export type BreadcrumbItem = {
  title: string;
  full_path: string;
};

export type PrevNextLink = {
  title: string;
  full_path: string;
};

export type SectionPage = {
  id: string;
  full_path: string;
  title: string;
  section_ref: string | null;
  content_md: string;
  level: number;
  word_count: number;
  reading_time_minutes: number;
  is_placeholder: boolean;
  breadcrumbs: BreadcrumbItem[];
  prev: PrevNextLink | null;
  next: PrevNextLink | null;
};

/* ---------- Legacy flat doc list (for landing page) ---------- */

export async function getDocsTree(): Promise<DocsNode[]> {
  try {
    const result = await pool.query<DocsNode>(
      `SELECT source_key AS path, title, COALESCE(category, 'General') AS category
       FROM sources ORDER BY source_key`
    );
    if (result.rowCount && result.rowCount > 0) return result.rows;
  } catch {
    // fallback
  }
  try {
    const fallback = await pool.query<DocsNode>(
      `SELECT doc_path AS path, title, COALESCE(category, 'General') AS category
       FROM source_documents ORDER BY doc_path`
    );
    return fallback.rows;
  } catch {
    return [];
  }
}

/* ---------- Hierarchical section tree ---------- */

type RawSection = {
  id: string;
  parent_id: string | null;
  slug: string;
  full_path: string;
  title: string;
  level: number;
  section_ref: string | null;
  word_count: number;
  reading_time_minutes: number;
  is_placeholder: boolean;
  sort_order: number;
};

export async function getSectionsTree(): Promise<SectionNode[]> {
  try {
    const result = await pool.query<RawSection>(
      `SELECT id::text, parent_id::text, slug, full_path, title, level,
              section_ref, word_count, reading_time_minutes, is_placeholder, sort_order
       FROM doc_sections
       ORDER BY level, sort_order, title`
    );

    const nodesById = new Map<string, SectionNode>();
    const roots: SectionNode[] = [];

    for (const row of result.rows) {
      nodesById.set(row.id, { ...row, children: [] });
    }

    for (const row of result.rows) {
      const node = nodesById.get(row.id)!;
      if (row.parent_id && nodesById.has(row.parent_id)) {
        nodesById.get(row.parent_id)!.children.push(node);
      } else {
        roots.push(node);
      }
    }

    return roots;
  } catch {
    return [];
  }
}

/* ---------- Section page ---------- */

export async function getSectionByPath(fullPath: string): Promise<SectionPage | null> {
  try {
    const result = await pool.query(
      `SELECT id::text, full_path, title, section_ref, content_md, level,
              word_count, reading_time_minutes, is_placeholder, parent_id::text
       FROM doc_sections
       WHERE full_path = $1
       LIMIT 1`,
      [fullPath]
    );

    if (!result.rowCount) return null;
    const row = result.rows[0];

    // Build breadcrumbs
    const breadcrumbs: BreadcrumbItem[] = [];
    let currentParentId = row.parent_id;
    while (currentParentId) {
      const parentResult = await pool.query(
        `SELECT id::text, full_path, title, parent_id::text FROM doc_sections WHERE id = $1`,
        [currentParentId]
      );
      if (!parentResult.rowCount) break;
      const parent = parentResult.rows[0];
      breadcrumbs.unshift({ title: parent.title, full_path: parent.full_path });
      currentParentId = parent.parent_id;
    }
    breadcrumbs.push({ title: row.title, full_path: row.full_path });

    // Prev/Next via DFS
    const tree = await getSectionsTree();
    const flat = flattenDfs(tree);
    const idx = flat.findIndex((n) => n.full_path === fullPath);

    return {
      id: row.id,
      full_path: row.full_path,
      title: row.title,
      section_ref: row.section_ref,
      content_md: row.content_md || "",
      level: row.level,
      word_count: row.word_count,
      reading_time_minutes: row.reading_time_minutes,
      is_placeholder: row.is_placeholder,
      breadcrumbs,
      prev: idx > 0 ? { title: flat[idx - 1].title, full_path: flat[idx - 1].full_path } : null,
      next: idx >= 0 && idx < flat.length - 1 ? { title: flat[idx + 1].title, full_path: flat[idx + 1].full_path } : null,
    };
  } catch {
    return null;
  }
}

function flattenDfs(nodes: SectionNode[]): SectionNode[] {
  const result: SectionNode[] = [];
  for (const node of nodes) {
    result.push(node);
    result.push(...flattenDfs(node.children));
  }
  return result;
}

/* ---------- First leaf (for redirect) ---------- */

export function findFirstLeaf(nodes: SectionNode[]): SectionNode | null {
  for (const node of nodes) {
    if (node.children.length === 0) return node;
    const child = findFirstLeaf(node.children);
    if (child) return child;
  }
  return null;
}
