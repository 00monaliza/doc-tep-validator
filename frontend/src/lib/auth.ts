import type { SupabaseClient } from "@supabase/supabase-js";

/** Sign-in through Supabase Auth (email + password; accounts are created by the administrator).
 * The server tells whether it needs a login (/api/capabilities): a local run has none. */
let client: SupabaseClient | null = null;

/** What an email link brought in the URL fragment: an invitation or a password reset to finish,
 * or an error (an expired or already used link). Read before the client consumes the fragment. */
export interface AuthRedirect { kind: "invite" | "recovery" | null; error: string | null }
let redirect: AuthRedirect = { kind: null, error: null };

function readRedirect(): AuthRedirect {
  const h = new URLSearchParams(location.hash.slice(1));
  const type = h.get("type");
  const code = h.get("error_code");
  const error = code === "otp_expired"
    ? "Ссылка из письма устарела или уже была открыта. Попросите администратора прислать приглашение заново или нажмите «Забыли пароль?»."
    : h.get("error_description")?.replace(/\+/g, " ") ?? null;
  if (error) history.replaceState(null, "", location.pathname + location.search);
  return { kind: type === "invite" || type === "recovery" ? type : null, error };
}

export async function initAuth(cfg: { url: string; key: string } | null): Promise<void> {
  if (!cfg || client) return;
  redirect = readRedirect();
  const { createClient } = await import("@supabase/supabase-js");
  client = createClient(cfg.url, cfg.key);
  await client.auth.getSession(); // lets the client take the session from an invitation link
}

export const authEnabled = () => client !== null;
export const authRedirect = () => redirect;

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

/** Sets the password of the signed-in user: after an invitation or a reset link. */
export async function setPassword(password: string): Promise<void> {
  if (!client) return;
  const { error } = await client.auth.updateUser({ password });
  if (error) throw new Error(error.message);
  redirect = { kind: null, error: null };
}

/** Emails a link that brings the user back here to set a new password. */
export async function requestPasswordReset(email: string): Promise<void> {
  if (!client) return;
  const { error } = await client.auth.resetPasswordForEmail(email, { redirectTo: location.origin });
  if (error) {
    throw new Error(error.status === 429 ? "Слишком много писем за час, попробуйте позже." : error.message);
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
