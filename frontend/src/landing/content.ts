// Facts shown on the landing. Each comes from the repository; keep the source next to it.

/** The discrepancy types the pipeline reports today (src/crossvalidation emits these; taxonomy has more). */
export const CHECK_TYPES = [
  "AREA_PZ_VS_AR_EXPLICATION", "MATERIAL_VOLUME_KR_VS_LOCAL_ESTIMATE", "COST_OBJECT_ESTIMATE_VS_SUMMARY",
  "MISSING_MANDATORY_TEP", "TEP_CROSS_SECTION_MISMATCH", "TABLE_TOTAL_MISMATCH", "VALUE_CROSS_SECTION_MISMATCH",
  "PARAMETER_CONTRADICTION", "TEP_CALCULATION_METHOD", "GEOMETRY_INCONSISTENCY", "COPY_PASTE_LABEL",
] as const;
export type DiscrepancyKey = (typeof CHECK_TYPES)[number];

/** Checks that are limited on scans (README: «на сканах … отсутствие показателей не проверяется», table totals). */
export const SCAN_LIMITED: readonly DiscrepancyKey[] = ["TABLE_TOTAL_MISMATCH", "MISSING_MANDATORY_TEP"];

export const FACTS = {
  sections: 4, // ПЗ, АР, КР, смета — src/ner/common/taxonomy.py, Section
  tepFields: 8, // src/ner/data/tep_lexicon.json → fields
  checkTypes: CHECK_TYPES.length,
  retentionDays: 7, // api/main.py RETENTION_DAYS (default), Vercel Cron cleanup
} as const;

export const METRICS = {
  // README.md, «Проверка на скрытых формулировках», таблица «Ступени»: + эмбеддинги, F1 по слотам, v3-test
  extraction: { ru: "0,97", kz: "0,81", set: "v3-test" },
  // README.md, «итог — один прогон на seeds 9000–9099», строка «все типы», столбцы S2 RU / S2 KZ, v4-test
  detectors: { ru: "1,00", kz: "1,00", set: "v4-test" },
  // README.md, «Реальная ОПЗ (единственный документ, dev)»: ТЭП, размеченные находки, ложных — 0
  real: { tep: "8 из 10", findings: "4 из 10", falsePositives: 0 },
} as const;

/** The value both language samples and the scene show (the demo package's total area in ПЗ). */
export const SAMPLE_AREA = "1 247,79";
