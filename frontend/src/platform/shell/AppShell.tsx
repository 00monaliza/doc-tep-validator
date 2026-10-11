import { Outlet } from "react-router";
import { useSession } from "../../app/providers";
import CommandMenu from "./CommandMenu";
import Sidebar, { MobileMenu } from "./Sidebar";

export default function AppShell() {
  const s = useSession();
  return (
    <div className="flex h-full">
      <Sidebar />
      <div className="flex-1 min-w-0 flex flex-col bg-tracing">
        <header className="flex items-center gap-2 md:gap-3 px-3 md:px-4 h-12 bg-sheet border-b border-line">
          <MobileMenu /><CommandMenu /><span className="flex-1" />
          {s.email && <span className="hidden sm:block text-sm text-ink-2 truncate max-w-64" title={s.email}>{s.email}</span>}
        </header>
        <main className="flex-1 min-h-0 overflow-auto"><Outlet /></main>
      </div>
    </div>
  );
}
