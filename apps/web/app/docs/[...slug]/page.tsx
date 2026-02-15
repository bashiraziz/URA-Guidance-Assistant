import ReactMarkdown from "react-markdown";
import rehypeSanitize from "rehype-sanitize";
import remarkGfm from "remark-gfm";

import DocsBreadcrumb from "@/components/docs-breadcrumb";
import DocsPrevNext from "@/components/docs-prev-next";
import DocsSidebar from "@/components/docs-sidebar";
import { getSectionByPath, getSectionsTree } from "@/lib/docs";

type Props = {
  params: Promise<{ slug: string[] }>;
};

export default async function DocSectionPage({ params }: Props) {
  const { slug } = await params;
  const fullPath = slug.join("/");
  const tree = await getSectionsTree();
  const page = await getSectionByPath(fullPath);

  if (!page) {
    return (
      <main className="vault-shell">
        <DocsSidebar tree={tree} activePath="" />
        <section className="vault-content">
          <h1>Section not found</h1>
          <p>The path <code>{fullPath}</code> does not exist.</p>
        </section>
      </main>
    );
  }

  return (
    <main className="vault-shell">
      <DocsSidebar tree={tree} activePath={page.full_path} />
      <section className="vault-content">
        <DocsBreadcrumb items={page.breadcrumbs} />

        <div style={{ display: "flex", alignItems: "center", gap: "0.75rem", marginBottom: "0.5rem" }}>
          <h1 style={{ marginTop: 0, marginBottom: 0 }}>{page.title}</h1>
          {page.reading_time_minutes > 0 && (
            <span className="reading-time">{page.reading_time_minutes} min read</span>
          )}
        </div>

        {page.section_ref && (
          <div style={{ color: "var(--muted)", fontSize: "0.86rem", marginBottom: "1rem" }}>
            {page.section_ref}
          </div>
        )}

        {page.is_placeholder ? (
          <div className="placeholder-notice">
            <strong>Coming Soon</strong>
            <p>This document has not yet been ingested. It will be available once the source file is provided and processed.</p>
          </div>
        ) : page.content_md ? (
          <article className="doc-markdown">
            <ReactMarkdown remarkPlugins={[remarkGfm]} rehypePlugins={[rehypeSanitize]}>
              {page.content_md}
            </ReactMarkdown>
          </article>
        ) : (
          <p style={{ color: "var(--muted)" }}>
            This is a document group. Select a section from the sidebar to view content.
          </p>
        )}

        <DocsPrevNext prev={page.prev} next={page.next} />
      </section>
    </main>
  );
}
