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

interface Props {
  checkId: string;
  report: Report;
  refs: Ref[];
  idx: number;
  onIdx: (i: number) => void;
  finding?: Finding;
  showSwitch: boolean;
}

/** One document page with the value circled, plus a switch between the finding's places. */
export default function RefPane({ checkId, report, refs, idx, onIdx, finding, showSwitch }: Props) {
  const wrapRef = useRef<HTMLDivElement>(null);
  const pageRef = useRef<HTMLDivElement>(null);
  const [note, setNote] = useState("");
  const ref = refs[idx];
  const doc = ref && report.documents.find(d => d.section === ref.section);
  const [pageNo, setPageNo] = useState(ref?.page ?? 1);
  const [pages, setPages] = useState(0);
  const [zoom, setZoom] = useState(1); // 1 = page width fits the pane
  useEffect(() => { setPageNo(ref?.page ?? 1); }, [ref]);
  const isPdf = !!doc && doc.file.toLowerCase().endsWith(".pdf");

  useEffect(() => {
    const page = pageRef.current, wrap = wrapRef.current;
    if (!page || !wrap || !ref) return;
    page.replaceChildren();
    setNote("");
    if (!doc || !doc.file.toLowerCase().endsWith(".pdf")) {
      if (doc) setNote("Для DOCX показываем только фрагмент текста выше.");
      return;
    }
    let cancelled = false; // a newer selection cancels an unfinished page render
    (async () => {
      const url = fileUrl(checkId, doc.file);
      pdfCache[url] ??= pdfjs.getDocument(url).promise;
      const pdf = await pdfCache[url];
      if (cancelled) return;
      setPages(pdf.numPages);
      const p = await pdf.getPage(Math.min(Math.max(1, pageNo), pdf.numPages));
      if (cancelled) return;
      const base = p.getViewport({ scale: 1 });
      const scale = Math.min(2, (wrap.clientWidth - 32) / base.width) * zoom;
      const vp = p.getViewport({ scale });
      const ratio = window.devicePixelRatio || 1;
      const canvas = document.createElement("canvas");
      canvas.width = vp.width * ratio; canvas.height = vp.height * ratio;
      canvas.style.width = `${vp.width}px`; canvas.style.height = `${vp.height}px`;
      await p.render({ canvasContext: canvas.getContext("2d")!, viewport: vp, transform: [ratio, 0, 0, ratio, 0, 0] }).promise;
      if (cancelled) return;
      page.replaceChildren(canvas);
      if (ref.bbox && pageNo === (ref.page ?? 1)) { // the circle belongs to the page of the value
        const [x0, top, x1, bottom] = ref.bbox, pad = 5;
        const ring = document.createElement("div");
        ring.className = "pencil-ring";
        Object.assign(ring.style, {
          left: `${x0 * scale - pad}px`, top: `${top * scale - pad}px`,
          width: `${(x1 - x0) * scale + 2 * pad}px`, height: `${(bottom - top) * scale + 2 * pad}px`,
        });
        page.appendChild(ring);
        wrap.scrollTop = Math.max(0, page.offsetTop + top * scale - wrap.clientHeight / 2);
        wrap.scrollLeft = Math.max(0, page.offsetLeft + ((x0 + x1) / 2) * scale - wrap.clientWidth / 2);
      }
    })();
    return () => { cancelled = true; };
  }, [checkId, doc, ref, pageNo, zoom]);

  return (
    <div className="pane">
      <div className="viewer-head">
        <span className="doc">
          {!ref ? "Выберите замечание слева"
            : doc ? `${SECTION[ref.section]} · ${doc.file}` : `${SECTION_FULL[ref.section]}: нет в пакете`}
        </span>
        {showSwitch && refs.length > 1 && (
          <span className="refs">
            {refs.map((r, i) => (
              <button key={i} type="button" aria-pressed={i === idx} onClick={() => onIdx(i)}>
                {r.label ?? SECTION[r.section]}{r.value == null ? " (нет)" : ""}
              </button>
            ))}
          </span>
        )}
      </div>
      {ref && <div className="evidence"><Evidence r={ref} finding={finding} /></div>}
      {isPdf && pages > 0 && (
        <div className="page-bar">
          <button type="button" aria-label="Предыдущая страница" disabled={pageNo <= 1}
            onClick={() => setPageNo(p => p - 1)}>‹</button>
          <span>стр. {pageNo} из {pages}</span>
          <button type="button" aria-label="Следующая страница" disabled={pageNo >= pages}
            onClick={() => setPageNo(p => p + 1)}>›</button>
          {pageNo !== (ref?.page ?? 1) && (
            <button type="button" className="back" onClick={() => setPageNo(ref?.page ?? 1)}>к значению</button>
          )}
          <span className="zoom">
            <button type="button" aria-label="Уменьшить" disabled={zoom <= 0.5}
              onClick={() => setZoom(z => Math.max(0.5, +(z - 0.25).toFixed(2)))}>−</button>
            <button type="button" onClick={() => setZoom(1)} aria-label="По ширине">{Math.round(zoom * 100)} %</button>
            <button type="button" aria-label="Увеличить" disabled={zoom >= 3}
              onClick={() => setZoom(z => Math.min(3, +(z + 0.25).toFixed(2)))}>+</button>
          </span>
        </div>
      )}
      <div className="canvas-wrap" ref={wrapRef}>
        {note && <div className="empty">{note}</div>}
        <div className="page" ref={pageRef} />
      </div>
    </div>
  );
}
