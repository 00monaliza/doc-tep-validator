import { createContext, useCallback, useContext, useState, type ReactNode } from "react";

type Tone = "error" | "info";
interface Item { id: number; text: string; tone: Tone }
const Ctx = createContext<(text: string, tone?: Tone) => void>(() => {});

export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<Item[]>([]);
  const push = useCallback((text: string, tone: Tone = "info") => {
    const id = Date.now() + Math.random();
    setItems(xs => [...xs, { id, text, tone }]);
    setTimeout(() => setItems(xs => xs.filter(x => x.id !== id)), 5000);
  }, []);
  return (
    <Ctx.Provider value={push}>
      {children}
      <div role="status" aria-live="polite" className="fixed bottom-4 right-4 z-50 flex flex-col gap-2">
        {items.map(t => (
          <div key={t.id} className={t.tone === "error"
            ? "bg-sheet border border-pencil text-pencil px-3 py-2 rounded shadow"
            : "bg-sheet border border-ink px-3 py-2 rounded shadow"}>{t.text}</div>
        ))}
      </div>
    </Ctx.Provider>
  );
}

export const useToast = () => useContext(Ctx);
