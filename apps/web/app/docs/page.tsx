import { redirect } from "next/navigation";

import { findFirstLeaf, getSectionsTree } from "@/lib/docs";

export default async function DocsIndexPage() {
  const tree = await getSectionsTree();
  if (!tree.length) {
    return <main style={{ padding: "2rem" }}>No docs found.</main>;
  }
  const first = findFirstLeaf(tree);
  if (first) {
    redirect(`/docs/${first.full_path}`);
  }
  redirect(`/docs/${tree[0].full_path}`);
}
