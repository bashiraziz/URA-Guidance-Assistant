import ReactMarkdown from "react-markdown";
import rehypeSanitize from "rehype-sanitize";
import remarkGfm from "remark-gfm";

import DocsSidebar from "@/components/docs-sidebar";
import { getDocByPath, getDocsTree } from "@/lib/docs";

type Props = {
  params: { slug: string[] };
};

export default async function DocPage({ params }: Props) {
  const { slug } = params;
  const docs = await getDocsTree();
  const candidate = `${slug.join("/")}.md`;
  const active = docs.find((d) => d.path === candidate) ? candidate : docs[0]?.path;

  if (!active) {
    return <main style={{ padding: "2rem" }}>No docs found in `/docs`.</main>;
  }

  const doc = await getDocByPath(active);
  return (
    <main className="vault-shell">
      <DocsSidebar docs={docs} activePath={active} />
      <section className="vault-content">
        <div style={{ marginBottom: 12, color: "var(--muted)", fontSize: "0.86rem" }}>
          {doc.category} / {doc.path}
        </div>
        <h1 style={{ marginTop: 0 }}>{doc.title}</h1>
        <article className="doc-markdown">
          <ReactMarkdown remarkPlugins={[remarkGfm]} rehypePlugins={[rehypeSanitize]}>
            {doc.content}
          </ReactMarkdown>
        </article>
      </section>
    </main>
  );
}
