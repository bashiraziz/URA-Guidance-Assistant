"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import clsx from "clsx";

import type { DocsNode } from "@/lib/docs";

type Props = {
  docs: DocsNode[];
  activePath: string;
};

export default function DocsSidebar({ docs, activePath }: Props) {
  const [query, setQuery] = useState("");
  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) {
      return docs;
    }
    return docs.filter((doc) => `${doc.title} ${doc.path} ${doc.category}`.toLowerCase().includes(q));
  }, [docs, query]);

  return (
    <aside className="vault-sidebar">
      <h2 style={{ marginTop: 0 }}>URA Knowledge Vault</h2>
      <p style={{ color: "var(--muted)", marginTop: 0, marginBottom: 12 }}>Tax law and URA guidance documents</p>
      <input
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        placeholder="Search docs..."
        style={{
          width: "100%",
          marginBottom: 10,
          border: "1px solid var(--surface-border)",
          borderRadius: 10,
          padding: "0.5rem"
        }}
      />
      {filtered.map((doc) => (
        <Link
          key={doc.path}
          className={clsx("doc-link", activePath === doc.path && "active")}
          href={`/docs/${doc.path.replace(/\.md$/, "")}`}
        >
          <div style={{ fontSize: "0.8rem", color: "var(--muted)" }}>{doc.category}</div>
          <div>{doc.title}</div>
        </Link>
      ))}
    </aside>
  );
}
