import { QueryClientProvider } from "@tanstack/react-query";
import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import { ToastProvider } from "../design/Toast";
import { getCapabilities } from "../lib/api";
import { authEnabled, currentEmail, initAuth, onSignedOut, signOut as authSignOut } from "../lib/auth";
import { queryClient } from "../lib/queries";

export interface Session {
  ready: boolean; enabled: boolean; email: string | null; ocr: boolean;
  signOut(): Promise<void>; refresh(): Promise<void>;
}
export const SessionContext = createContext<Session>({
  ready: false, enabled: false, email: null, ocr: true, signOut: async () => {}, refresh: async () => {},
});
export const useSession = () => useContext(SessionContext);

export function Providers({ children }: { children: ReactNode }) {
  const [state, setState] = useState({ ready: false, enabled: false, email: null as string | null, ocr: true });

  const refresh = useCallback(async () => {
    setState(s => ({ ...s, ready: true, enabled: authEnabled() }));
    const email = await currentEmail();
    setState(s => ({ ...s, email }));
  }, []);

  useEffect(() => {
    let off = () => {};
    (async () => {
      const caps = await getCapabilities();
      await initAuth(caps.auth);
      off = onSignedOut(() => setState(s => ({ ...s, email: null })));
      setState(s => ({ ...s, ocr: caps.ocr }));
      await refresh();
    })();
    return () => off();
  }, [refresh]);

  const session: Session = { ...state, signOut: async () => { await authSignOut(); queryClient.clear(); }, refresh };
  return (
    <QueryClientProvider client={queryClient}>
      <SessionContext.Provider value={session}>
        <ToastProvider>{children}</ToastProvider>
      </SessionContext.Provider>
    </QueryClientProvider>
  );
}
