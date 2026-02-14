import { redirect } from "next/navigation";

import { getDocsTree } from "@/lib/docs";

export default async function DocsIndexPage() {
  const docs = await getDocsTree();
  if (!docs.length) {
    return <main style={{ padding: "2rem" }}>No docs found in `/docs`.</main>;
  }
  const first = docs[0].path.replace(/\.md$/, "");
  redirect(`/docs/${first}`);
}
