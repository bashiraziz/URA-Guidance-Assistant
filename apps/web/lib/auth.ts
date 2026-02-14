import { betterAuth } from "better-auth";
import { toNextJsHandler } from "better-auth/next-js";
import { headers } from "next/headers";
import { redirect } from "next/navigation";
import { Pool } from "pg";

const pool = new Pool({
  connectionString: process.env.DATABASE_URL
});

export const auth = betterAuth({
  database: pool,
  secret: process.env.BETTER_AUTH_SECRET,
  baseURL: process.env.BETTER_AUTH_URL,
  trustedOrigins: [process.env.BETTER_AUTH_URL || "http://localhost:3000"],
  emailAndPassword: {
    enabled: true
  }
});

export const authHandler = toNextJsHandler(auth);

export async function getServerSession() {
  return auth.api.getSession({
    headers: await headers()
  });
}

export async function requireServerSession() {
  const session = await getServerSession();
  if (!session?.user?.id) {
    redirect("/signin");
  }
  return session;
}
