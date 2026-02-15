import Link from "next/link";

import type { PrevNextLink } from "@/lib/docs";

type Props = {
  prev: PrevNextLink | null;
  next: PrevNextLink | null;
};

export default function DocsPrevNext({ prev, next }: Props) {
  if (!prev && !next) return null;

  return (
    <nav className="docs-prev-next">
      {prev ? (
        <Link href={`/docs/${prev.full_path}`} className="prev-link">
          <span className="nav-label">Previous</span>
          <span className="nav-title">{prev.title}</span>
        </Link>
      ) : (
        <span />
      )}
      {next ? (
        <Link href={`/docs/${next.full_path}`} className="next-link">
          <span className="nav-label">Next</span>
          <span className="nav-title">{next.title}</span>
        </Link>
      ) : (
        <span />
      )}
    </nav>
  );
}
