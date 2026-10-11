import type { ExpertVerdict } from "../../lib/types";

/** Names of the expert's verdicts (the verdict itself is set in FindingDetail). */
export const EXPERT: Record<ExpertVerdict, string> = { confirmed: "Подтверждаю", false_positive: "Ложное" };
