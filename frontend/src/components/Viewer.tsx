import * as pdfjs from "pdfjs-dist";
import workerUrl from "pdfjs-dist/build/pdf.worker.min.mjs?url";
import { useEffect, useRef, useState } from "react";
import { fileUrl } from "../api";
import { SECTION, SECTION_FULL } from "../labels";
import type { Finding, Ref, Report } from "../types";

pdfjs.GlobalWorkerOptions.workerSrc = workerUrl;
const pdfCache: Record<string, Promise<pdfjs.PDFDocumentProxy>> = {};

function Evidence({ r, finding }: { r: Ref; finding?: Finding }) {
  if (r.value == null) return <>{finding?.message ?? ""} В документе этого значения нет.</>;
  const txt = r.evidence ?? "";
  const raw = r.raw ?? "";
  const at = raw ? txt.lastIndexOf(raw) : -1; // mark the last occurrence: extractors read the last number of a row
  return (
    <>
      {r.derived && `Вычислено: ${r.derived}. `}
      {at >= 0 ? <>{txt.slice(0, at)}<mark>{raw}</mark>{txt.slice(at + raw.length)}</> : txt}
    </>
  );
}

interface Props { checkId: string; report: Report; selection: { refs: Ref[]; finding?: Finding } | null }

export default function Viewer({ checkId, report, selection }: Props) {
  const [idx, setIdx] = useState(0);
  const wrapRef = useRef<HTMLDivElement>(null);
  const pageRef = useRef<HTMLDivElement>(null);
  const [pageNote, setPageNote] = useState("");

  // start on the first ref that actually has a value
  useEffect(() => {
    const refs = selection?.refs ?? [];
    const first = refs.findIndex(r => r.value != null);
    setIdx(refs[0]?.value == null && first >= 0 ? first : 0);
  }, [selection]);

  const ref = selection?.refs[idx];
  const doc = ref && report.documents.find(d => d.section === ref.section);

  useEffect(() => {
    const page = pageRef.current, wrap = wrapRef.current;
    if (!page || !wrap || !ref) return;
    page.replaceChildren();
    setPageNote("");
    if (!doc || !doc.file.toLowerCase().endsWith(".pdf")) {
      if (doc) setPageNote("Для DOCX показываем только фрагмент текста выше.");
      return;
    }
    let cancelled = false; // a newer selection cancels an unfinished page render
    (async () => {
      const url = fileUrl(checkId, doc.file);
      pdfCache[url] ??= pdfjs.getDocument(url).promise;
      const pdf = await pdfCache[url];
      const p = await pdf.getPage(ref.page ?? 1);
      if (cancelled) return;
      const base = p.getViewport({ scale: 1 });
      const scale = Math.min(2, (wrap.clientWidth - 32) / base.width);
      const vp = p.getViewport({ scale });
      const ratio = window.devicePixelRatio || 1;
      const canvas = document.createElement("canvas");
      canvas.width = vp.width * ratio; canvas.height = vp.height * ratio;
      canvas.style.width = `${vp.width}px`; canvas.style.height = `${vp.height}px`;
      await p.render({ canvasContext: canvas.getContext("2d")!, viewport: vp, transform: [ratio, 0, 0, ratio, 0, 0] }).promise;
      if (cancelled) return;
      page.replaceChildren(canvas);
      if (ref.bbox) {
        const [x0, top, x1, bottom] = ref.bbox, pad = 5;
        const ring = document.createElement("div");
        ring.className = "pencil-ring";
        Object.assign(ring.style, {
          left: `${x0 * scale - pad}px`, top: `${top * scale - pad}px`,
          width: `${(x1 - x0) * scale + 2 * pad}px`, height: `${(bottom - top) * scale + 2 * pad}px`,
        });
        page.appendChild(ring);
        wrap.scrollTop = Math.max(0, page.offsetTop + top * scale - wrap.clientHeight / 2);
      }
    })();
    return () => { cancelled = true; };
  }, [checkId, doc, ref]);

  const refs = selection?.refs ?? [];
  return (
    <section className="panel" aria-label="Документ">
      <div className="viewer-head">
        <span className="doc">
          {!ref ? "Выберите замечание слева"
            : doc ? `${SECTION[ref.section]} · ${doc.file}` : `${SECTION_FULL[ref.section]}: нет в пакете`}
        </span>
        {refs.length > 1 && (
          <span className="refs">
            {refs.map((r, i) => (
              <button key={i} type="button" aria-pressed={i === idx} onClick={() => setIdx(i)}>
                {r.label ?? SECTION[r.section]}{r.value == null ? " (нет)" : ""}
              </button>
            ))}
          </span>
        )}
      </div>
      {ref && <div className="evidence"><Evidence r={ref} finding={selection?.finding} /></div>}
      <div className="canvas-wrap" ref={wrapRef}>
        {pageNote && <div className="empty">{pageNote}</div>}
        <div className="page" ref={pageRef} />
      </div>
    </section>
  );
}
