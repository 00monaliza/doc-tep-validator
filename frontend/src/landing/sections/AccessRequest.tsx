import { useContext, useRef, useState } from "react";
import Button from "../../design/Button";
import { requestAccess } from "../../lib/api";
import { LangContext } from "../i18n";
import Block from "./Block";

const FIELD = "min-h-9 border border-control rounded px-2.5 bg-sheet text-ink";

export default function AccessRequest() {
  const { tl } = useContext(LangContext);
  const [state, setState] = useState<"idle" | "sending" | "done" | "error">("idle");
  const [error, setError] = useState("");
  const sending = useRef(false); // a double click arrives before React re-renders the disabled button

  const submit = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (sending.current || state === "done") return;
    sending.current = true;
    setState("sending");
    const f = new FormData(e.currentTarget);
    try {
      await requestAccess({
        email: String(f.get("email") ?? ""), organization: String(f.get("organization") ?? ""),
        comment: String(f.get("comment") ?? ""), website: String(f.get("website") ?? ""),
      });
      setState("done");
    } catch (err) {
      setError((err as Error).message);
      setState("error");
      sending.current = false;
    }
  };

  return (
    <Block id="access" title={tl("access.title")} lead={tl("access.lead")} tracing>
      <form onSubmit={submit} className="relative grid gap-3 max-w-xl">
        <label className="flex flex-col gap-1 text-sm text-ink-2">{tl("access.email")}
          <input name="email" type="email" required autoComplete="email" className={FIELD} />
        </label>
        <label className="flex flex-col gap-1 text-sm text-ink-2">{tl("access.org")}
          <input name="organization" required maxLength={200} autoComplete="organization" className={FIELD} />
        </label>
        <label className="flex flex-col gap-1 text-sm text-ink-2">{tl("access.comment")}
          <textarea name="comment" rows={3} maxLength={1000} className={FIELD + " py-1.5"} />
        </label>
        {/* bot trap: people never see or reach it */}
        <div aria-hidden="true" className="absolute -left-[9999px] w-px h-px overflow-hidden">
          <input name="website" tabIndex={-1} autoComplete="off" />
        </div>
        <Button type="submit" variant="primary" className="justify-self-start" disabled={state === "sending" || state === "done"}>
          {state === "sending" ? tl("access.sending") : tl("access.send")}
        </Button>
        {state === "done" && <p role="status" className="text-green">{tl("access.done")}</p>}
        {state === "error" && <p role="alert" className="text-pencil text-sm">{error}</p>}
      </form>
    </Block>
  );
}
