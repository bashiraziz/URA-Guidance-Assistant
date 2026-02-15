import { SignJWT } from "jose";

const encoder = new TextEncoder();

export async function createApiToken(userId: string, claims: Record<string, unknown> = {}): Promise<string> {
  const secret = process.env.API_JWT_SECRET;
  if (!secret) {
    throw new Error("Missing API_JWT_SECRET");
  }
  const issuer = process.env.API_JWT_ISSUER || "ura-guidance-web";
  const audience = process.env.API_JWT_AUDIENCE || "ura-guidance-api";
  const ttl = Number(process.env.API_JWT_EXPIRES_SECONDS || "900");

  return await new SignJWT(claims)
    .setProtectedHeader({ alg: "HS256" })
    .setSubject(userId)
    .setIssuer(issuer)
    .setAudience(audience)
    .setIssuedAt()
    .setExpirationTime(`${ttl}s`)
    .sign(encoder.encode(secret));
}
