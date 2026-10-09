export type Section = "PZ" | "AR" | "KR" | "SMETA";
export type Verdict = "MISMATCH" | "MISSING" | "MATCH";

export interface Ref {
  section: Section;
  value: number | string | null;
  raw?: string;
  page?: number;
  bbox?: [number, number, number, number];
  evidence?: string;
  derived?: string;
  label?: string;
}

export interface Finding {
  type: string;
  field: string;
  verdict: Verdict;
  refs: Ref[];
  delta_rel?: number | null;
  notes: string[];
  message?: string;
  object_name?: string;
  low_confidence?: boolean;
  needs_expert?: boolean;
}

export interface TepEntry {
  raw: string;
  value?: number | string;
  page?: number;
  bbox?: [number, number, number, number];
  evidence?: string;
  object?: string;
}

export interface DocumentInfo {
  file: string;
  section: Section | null;
  ocr?: boolean;
}

export interface Report {
  lang: string;
  documents: DocumentInfo[];
  findings: Finding[];
  summary: Record<Verdict, number>;
  completeness: {
    required: Section[];
    present: Section[];
    missing: Section[];
    unrecognised: string[];
    duplicates: string[];
  };
  tep: Partial<Record<Section, Record<string, TepEntry>>>;
  objects?: Record<string, string>;
  pz_building?: string;
  warnings?: string[];
}

export type ExpertVerdict = "confirmed" | "false_positive";
export interface Review { verdict: ExpertVerdict | null; comment: string }
/** Expert reviews keyed by the finding's index in report.findings. */
export type Reviews = Record<string, Review>;

export type CheckStatus =
  | { id: string; status: "pending" }
  | { id: string; status: "error"; error: string }
  | { id: string; status: "done"; report: Report; reviews?: Reviews };
