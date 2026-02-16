import { betterAuth } from "better-auth";
import { toNextJsHandler } from "better-auth/next-js";
import { headers } from "next/headers";
import { redirect } from "next/navigation";
import { Pool } from "pg";
import { Resend } from "resend";

const connStr = process.env.DATABASE_URL || "";
const pool = new Pool({
  connectionString: connStr.includes("uselibpqcompat")
    ? connStr
    : connStr.includes("?")
      ? `${connStr}&uselibpqcompat=true`
      : `${connStr}?uselibpqcompat=true`
});

const resend = process.env.RESEND_API_KEY ? new Resend(process.env.RESEND_API_KEY) : null;
const fromEmail = process.env.RESEND_FROM_EMAIL || "URA Guidance <noreply@ura-guidance.com>";

export const auth = betterAuth({
  database: pool,
  secret: process.env.BETTER_AUTH_SECRET,
  baseURL: process.env.BETTER_AUTH_URL,
  trustedOrigins: [process.env.BETTER_AUTH_URL || "http://localhost:3000"],
  emailAndPassword: {
    enabled: true,
    sendResetPassword: resend
      ? async ({ user, url }) => {
          await resend.emails.send({
            from: fromEmail,
            to: user.email,
            subject: "Reset your URA Guidance password",
            html: `<p>Hi ${user.name || "there"},</p><p>Click the link below to reset your password:</p><p><a href="${url}">Reset Password</a></p><p>If you didn't request this, you can safely ignore this email.</p>`,
          });
        }
      : undefined,
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
