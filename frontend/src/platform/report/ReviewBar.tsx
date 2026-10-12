import type { ExpertVerdict } from "../../lib/types";
import { t } from "../../lib/i18n";

/** Names of the expert's verdicts (the verdict itself is set in FindingDetail). */
export const EXPERT: Record<ExpertVerdict, string> = { confirmed: t("verdict.confirm"), false_positive: t("verdict.false") };
