import Link from "next/link";

import type { BreadcrumbItem } from "@/lib/docs";

type Props = {
  items: BreadcrumbItem[];
};

export default function DocsBreadcrumb({ items }: Props) {
  if (!items.length) return null;

  return (
    <nav className="docs-breadcrumb">
      <Link href="/docs">Home</Link>
      {items.map((item, i) => (
        <span key={item.full_path}>
          <span className="breadcrumb-sep">/</span>
          {i < items.length - 1 ? (
            <Link href={`/docs/${item.full_path}`}>{item.title}</Link>
          ) : (
            <span>{item.title}</span>
          )}
        </span>
      ))}
    </nav>
  );
}
