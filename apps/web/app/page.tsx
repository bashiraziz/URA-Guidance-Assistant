import Link from "next/link";

import ChatWidget from "@/components/chat-widget";
import { getDocsTree, getSectionsTree } from "@/lib/docs";
import type { SectionNode } from "@/lib/docs";

function collectDocs(nodes: SectionNode[]): { title: string; path: string; category: string }[] {
  const result: { title: string; path: string; category: string }[] = [];
  for (const node of nodes) {
    if (node.level === 1) {
      result.push({ title: node.title, path: node.full_path, category: node.full_path.split("/")[0] || "" });
    }
    result.push(...collectDocs(node.children));
  }
  return result;
}

export default async function HomePage() {
  const tree = await getSectionsTree();
  const docs = tree.length > 0 ? collectDocs(tree) : (await getDocsTree()).map((d) => ({ title: d.title, path: d.path, category: d.category }));
  const featured = docs.slice(0, 8);
  const categories = Array.from(new Set(docs.map((d) => d.category)));

  return (
    <main className="landing-shell">
      <aside className="landing-sidebar">
        <div className="sidebar-top-nav">
          <Link href="/signin" className="sidebar-nav-link">Sign in</Link>
          <span className="sidebar-nav-sep">|</span>
          <Link href="/signup" className="sidebar-nav-link">Sign up</Link>
        </div>
        <p className="landing-eyebrow">Reference</p>
        <h2>Uganda Tax Guides</h2>
        <p className="landing-muted">
          Browse the full corpus or ask questions in guest mode. Sign in to unlock higher limits and conversation
          history.
        </p>
        <nav className="landing-doc-nav">
          {featured.map((doc) => (
            <Link key={doc.path} href={`/docs/${doc.path}`} className="landing-doc-link">
              {doc.title}
            </Link>
          ))}
        </nav>
      </aside>

      <section className="landing-content">
        <header className="landing-hero">
          <p className="landing-eyebrow">URA Guidance Assistant</p>
          <h1>Find Clear Answers Fast.</h1>
          <p className="landing-muted">
            Search VAT, PAYE, filing, and exemptions with evidence-backed guidance from the curated documentation set.
          </p>
          <div className="landing-actions">
            <Link href="/docs" className="landing-btn primary">
              Open Docs
            </Link>
            <Link href="/signup" className="landing-btn">
              Create Account
            </Link>
            <Link href="/signin" className="landing-btn">
              Sign In
            </Link>
          </div>
        </header>

        <section className="landing-card-grid">
          <article className="landing-card">
            <h3>Guest Access</h3>
            <p>Use Ask URA Tax without registering.</p>
            <p className="landing-muted">Guest limits are lower and conversation history is disabled.</p>
          </article>
          <article className="landing-card">
            <h3>Signed-In Access</h3>
            <p>Higher request and token quotas.</p>
            <p className="landing-muted">Conversation history is available for registered users.</p>
          </article>
          <article className="landing-card">
            <h3>Coverage</h3>
            <p>{docs.length} source docs indexed.</p>
            <p className="landing-muted">{categories.length} topical categories.</p>
          </article>
        </section>

        <section className="landing-categories">
          <h2>Categories</h2>
          <div className="landing-category-list">
            {categories.map((category) => (
              <span key={category} className="landing-pill">
                {category}
              </span>
            ))}
          </div>
        </section>
      </section>

      <ChatWidget />
    </main>
  );
}
