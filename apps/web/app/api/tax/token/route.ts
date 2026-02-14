import { NextResponse } from "next/server";

import { createApiToken } from "@/lib/api-token";
import { getServerSession } from "@/lib/auth";

export async function GET() {
  const session = await getServerSession();
  if (!session?.user?.id) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const token = await createApiToken(session.user.id);
  return NextResponse.json({ token, expires_in: Number(process.env.API_JWT_EXPIRES_SECONDS || "900") });
}
