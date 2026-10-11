import { MutationCache, QueryCache, QueryClient, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { getCheck, listChecks, renameCheck, Unauthorized } from "./api";

/** Any request refused for login sends the user to /login and back here afterwards. */
export function toLogin(e: unknown): void {
  if (e instanceof Unauthorized && !location.pathname.startsWith("/login"))
    location.assign("/login?next=" + encodeURIComponent(location.pathname + location.search));
}

export const queryClient = new QueryClient({
  queryCache: new QueryCache({ onError: toLogin }),
  mutationCache: new MutationCache({ onError: toLogin }),
  defaultOptions: { queries: { retry: (n, e) => !(e instanceof Unauthorized) && n < 2, refetchOnWindowFocus: false } },
});

export const useChecks = () => useQuery({ queryKey: ["checks"], queryFn: listChecks });

export const useCheck = (id: string) => useQuery({
  queryKey: ["check", id],
  queryFn: () => getCheck(id),
  refetchInterval: q => (q.state.data && ["receiving", "pending"].includes(q.state.data.status) ? 1000 : false),
});

export function useRenameCheck() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, title }: { id: string; title: string }) => renameCheck(id, title),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["checks"] }); },
  });
}
