import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

const PROTECTED_PREFIXES = ["/account"];
const POSSIBLE_SESSION_COOKIES = ["better-auth.session_token", "__Secure-better-auth.session_token"];

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;
  if (!PROTECTED_PREFIXES.some((prefix) => pathname.startsWith(prefix))) {
    return NextResponse.next();
  }

  const hasSession = POSSIBLE_SESSION_COOKIES.some((name) => request.cookies.get(name)?.value);
  if (hasSession) {
    return NextResponse.next();
  }

  const login = request.nextUrl.clone();
  login.pathname = "/signin";
  login.searchParams.set("next", pathname);
  return NextResponse.redirect(login);
}

export const config = {
  matcher: ["/account/:path*"]
};
