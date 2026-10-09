import type { SupabaseClient } from "@supabase/supabase-js";

/** Sign-in through Supabase Auth (email + password; accounts are created by the administrator).
 * The server tells whether it needs a login (/api/capabilities): a local run has none. */
let client: SupabaseClient | null = null;

export async function initAuth(cfg: { url: string; key: string } | null): Promise<void> {
  if (!cfg || client) return;
  const { createClient } = await import("@supabase/supabase-js");
  client = createClient(cfg.url, cfg.key);
}

export const authEnabled = () => client !== null;

export async function currentEmail(): Promise<string | null> {
  if (!client) return null;
  const { data } = await client.auth.getSession();
  return data.session?.user.email ?? null;
}

export async function accessToken(): Promise<string | null> {
  if (!client) return null;
  const { data } = await client.auth.getSession(); // refreshes an expired token by itself
  return data.session?.access_token ?? null;
}

export async function signIn(email: string, password: string): Promise<void> {
  if (!client) return;
  const { error } = await client.auth.signInWithPassword({ email, password });
  if (error) {
    throw new Error(error.message === "Invalid login credentials" ? "Неверная почта или пароль." : error.message);
  }
}

export async function signOut(): Promise<void> {
  await client?.auth.signOut();
}

/** Called when the session ends (sign-out, expired refresh token, another tab signed out). */
export function onSignedOut(cb: () => void): () => void {
  if (!client) return () => {};
  const { data } = client.auth.onAuthStateChange(event => { if (event === "SIGNED_OUT") cb(); });
  return () => data.subscription.unsubscribe();
}
