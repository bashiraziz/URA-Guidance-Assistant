import { NextResponse } from "next/server";
import { randomUUID } from "node:crypto";
import { cookies } from "next/headers";

import { createApiToken } from "@/lib/api-token";
import { getServerSession } from "@/lib/auth";

export async function GET() {
  const session = await getServerSession();
  const ttl = Number(process.env.API_JWT_EXPIRES_SECONDS || "900");

  if (session?.user?.id) {
    const token = await createApiToken(session.user.id, { tier: "user" });
    return NextResponse.json({ token, expires_in: ttl, mode: "user" });
  }

  const cookieStore = await cookies();
  const guestCookieName = "ura_guest_id";
  const existingGuestId = cookieStore.get(guestCookieName)?.value;
  const guestId = existingGuestId || randomUUID();

  const token = await createApiToken(`guest:${guestId}`, { tier: "guest" });
  const response = NextResponse.json({ token, expires_in: ttl, mode: "guest" });
  if (!existingGuestId) {
    response.cookies.set(guestCookieName, guestId, {
      httpOnly: true,
      sameSite: "lax",
      secure: process.env.NODE_ENV === "production",
      path: "/",
      maxAge: 60 * 60 * 24 * 365,
    });
  }
  return response;
}
