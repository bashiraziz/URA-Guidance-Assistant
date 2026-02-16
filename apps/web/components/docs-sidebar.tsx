"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import clsx from "clsx";

import type { SectionNode } from "@/lib/docs";

type Props = {
  tree: SectionNode[];
  activePath: string;
};

function isAncestor(node: SectionNode, path: string): boolean {
  if (node.full_path === path) return true;
  return node.children.some((child) => isAncestor(child, path));
}

function flatSearch(nodes: SectionNode[], query: string): SectionNode[] {
  const results: SectionNode[] = [];
  for (const node of nodes) {
    const match = `${node.title} ${node.full_path} ${node.section_ref || ""}`.toLowerCase().includes(query);
    if (match) results.push(node);
    results.push(...flatSearch(node.children, query));
  }
  return results;
}

function TreeNode({
  node,
  activePath,
  defaultOpen,
  collapseKey,
}: {
  node: SectionNode;
  activePath: string;
  defaultOpen: boolean;
  collapseKey: number;
}) {
  const [open, setOpen] = useState(defaultOpen);
  const hasChildren = node.children.length > 0;
  const isActive = node.full_path === activePath;

  // Reset to collapsed when collapseKey changes (user clicked "Collapse All")
  useEffect(() => {
    if (collapseKey > 0) {
      setOpen(false);
    }
  }, [collapseKey]);

  return (
    <div className="tree-node">
      <div className={clsx("tree-link", isActive && "active")}>
        {hasChildren ? (
          <button className="tree-toggle" onClick={() => setOpen(!open)} aria-label={open ? "Collapse" : "Expand"}>
            {open ? "\u25BE" : "\u25B8"}
          </button>
        ) : (
          <span className="tree-toggle-spacer" />
        )}
        <Link href={`/docs/${node.full_path}`} className="tree-link-text">
          {node.section_ref && <span className="tree-ref">{node.section_ref}</span>}
          <span>{node.title}</span>
          {node.is_placeholder && <span className="tree-badge">Coming Soon</span>}
        </Link>
      </div>
      {hasChildren && open && (
        <div className="tree-children">
          {node.children.map((child) => (
            <TreeNode
              key={child.id}
              node={child}
              activePath={activePath}
              defaultOpen={isAncestor(child, activePath)}
              collapseKey={collapseKey}
            />
          ))}
        </div>
      )}
    </div>
  );
}

export default function DocsSidebar({ tree, activePath }: Props) {
  const [query, setQuery] = useState("");
  const [collapseKey, setCollapseKey] = useState(0);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return null;
    return flatSearch(tree, q);
  }, [tree, query]);

  const handleSearchChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    setQuery(e.target.value);
  }, []);

  return (
    <aside className="vault-sidebar">
      <div className="sidebar-top-nav">
        <Link href="/" className="sidebar-nav-link">Home</Link>
        <span className="sidebar-nav-sep">|</span>
        <Link href="/signin" className="sidebar-nav-link">Sign in</Link>
        <span className="sidebar-nav-sep">|</span>
        <Link href="/signup" className="sidebar-nav-link">Sign up</Link>
      </div>
      <h2 style={{ marginTop: 0 }}>URA Knowledge Vault</h2>
      <p style={{ color: "var(--muted)", marginTop: 0, marginBottom: 12 }}>Tax law and URA guidance documents</p>
      <div style={{ display: "flex", gap: 6, marginBottom: 10 }}>
        <input
          value={query}
          onChange={handleSearchChange}
          placeholder="Search docs..."
          style={{
            flex: 1,
            border: "1px solid var(--surface-border)",
            borderRadius: 10,
            padding: "0.5rem",
          }}
        />
        {!filtered && (
          <button
            type="button"
            onClick={() => setCollapseKey((k) => k + 1)}
            className="sidebar-collapse-btn"
            title="Collapse all sections"
          >
            Collapse
          </button>
        )}
      </div>
      {filtered ? (
        filtered.length === 0 ? (
          <p style={{ color: "var(--muted)", fontSize: "0.86rem" }}>No results.</p>
        ) : (
          filtered.map((node) => (
            <Link
              key={node.id}
              className={clsx("doc-link", activePath === node.full_path && "active")}
              href={`/docs/${node.full_path}`}
            >
              <div style={{ fontSize: "0.8rem", color: "var(--muted)" }}>{node.full_path}</div>
              <div>
                {node.title}
                {node.is_placeholder && <span className="tree-badge">Coming Soon</span>}
              </div>
            </Link>
          ))
        )
      ) : (
        tree.map((node) => (
          <TreeNode key={node.id} node={node} activePath={activePath} defaultOpen={isAncestor(node, activePath)} collapseKey={collapseKey} />
        ))
      )}
    </aside>
  );
}
