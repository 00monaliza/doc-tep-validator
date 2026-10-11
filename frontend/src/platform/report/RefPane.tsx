import * as pdfjs from "pdfjs-dist";
import workerUrl from "pdfjs-dist/build/pdf.worker.min.mjs?url";
import { useEffect, useRef, useState } from "react";
import Button from "../../design/Button";
import { fileLink } from "../../lib/api";
import { SECTION, SECTION_FULL } from "../../lib/labels";
import type { Finding, Ref, Report } from "../../lib/types";
import { t } from "../../lib/i18n";

pdfjs.GlobalWorkerOptions.workerSrc = workerUrl;
const pdfCache: Record<string, Promise<pdfjs.PDFDocumentProxy>> = {};

function Evidence({ r, finding }: { r: Ref; finding?: Finding }) {
  if (r.value == null) return <>{finding?.message ?? ""} {t("doc.noValue")}</>;
  const txt = r.evidence ?? "";
  const raw = r.raw ?? "";
  const at = raw ? txt.lastIndexOf(raw) : -1; // mark the last occurrence: extractors read the last number of a row
  return (
    <>
      {r.derived && t("doc.computed", { how: r.derived })}
      {at >= 0 ? <>{txt.slice(0, at)}<mark className="bg-transparent text-pencil font-semibold">{raw}</mark>{txt.slice(at + raw.length)}</> : txt}
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
      if (doc) setNote(t("doc.docxOnly"));
      return;
    }
    let cancelled = false; // a newer selection cancels an unfinished page render
    (async () => {
      const key = `${checkId}/${doc.file}`;
      // the link is signed for 10 minutes: the whole file is read at once, not in ranges later
      pdfCache[key] ??= fileLink(checkId, doc.file)
        .then(url => pdfjs.getDocument({ url, disableRange: true, disableStream: true }).promise)
        .catch(e => { delete pdfCache[key]; throw e; });
      const pdf = await pdfCache[key];
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
    })().catch(e => { if (!cancelled) setNote((e as Error).message); });
    return () => { cancelled = true; };
  }, [checkId, doc, ref, pageNo, zoom]);

  return (
    <div className="flex flex-col min-h-0 min-w-0">
      <div className="flex items-center gap-2 px-3 py-2 border-b border-line bg-sheet">
        <span className="flex-1 min-w-0 truncate font-cond font-semibold">
          {!ref ? t("doc.pick")
            : doc ? `${SECTION[ref.section]} · ${doc.file}` : t("doc.notInPackage", { section: SECTION_FULL[ref.section] })}
        </span>
        {showSwitch && refs.length > 1 && (
          <span className="flex gap-1">
            {refs.map((r, i) => (
              <Button key={i} size="sm" variant={i === idx ? "primary" : "secondary"} aria-pressed={i === idx} onClick={() => onIdx(i)}>
                {r.label ?? SECTION[r.section]}{r.value == null ? t("doc.none") : ""}
              </Button>
            ))}
          </span>
        )}
      </div>
      {ref && <div className="px-3 py-2 text-sm text-ink-2 border-b border-line bg-sheet"><Evidence r={ref} finding={finding} /></div>}
      {isPdf && pages > 0 && (
        <div className="flex flex-wrap items-center gap-1.5 px-3 py-1 border-b border-line text-sm text-ink-2 bg-sheet">
          <Button size="sm" aria-label={t("doc.prev")} disabled={pageNo <= 1}
            onClick={() => setPageNo(p => p - 1)}>‹</Button>
          <span className="whitespace-nowrap">{t("common.pageOf", { page: pageNo, pages })}</span>
          <Button size="sm" aria-label={t("doc.next")} disabled={pageNo >= pages}
            onClick={() => setPageNo(p => p + 1)}>›</Button>
          {pageNo !== (ref?.page ?? 1) && (
            <Button size="sm" variant="ghost" className="text-pencil" onClick={() => setPageNo(ref?.page ?? 1)}>{t("doc.toValue")}</Button>
          )}
          <span className="ml-auto flex gap-1">
            <Button size="sm" aria-label={t("doc.zoomOut")} disabled={zoom <= 0.5}
              onClick={() => setZoom(z => Math.max(0.5, +(z - 0.25).toFixed(2)))}>−</Button>
            <Button size="sm" onClick={() => setZoom(1)} aria-label={t("doc.fit")}>{Math.round(zoom * 100)} %</Button>
            <Button size="sm" aria-label={t("doc.zoomIn")} disabled={zoom >= 3}
              onClick={() => setZoom(z => Math.min(3, +(z + 0.25).toFixed(2)))}>+</Button>
          </span>
        </div>
      )}
      <div className="relative flex-1 overflow-auto p-4 bg-doc" ref={wrapRef}>
        {note && <p className="p-4 text-ink-2">{note}</p>}
        <div className="relative mx-auto w-fit bg-white shadow-[0_0_0_1px_var(--line)]" ref={pageRef} />
      </div>
    </div>
  );
}
