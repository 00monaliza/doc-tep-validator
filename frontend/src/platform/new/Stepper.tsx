import { t } from "../../lib/i18n";

const STEPS = ["new.step.files", "new.step.sections", "new.step.run"] as const;

export default function Stepper({ current }: { current: 0 | 1 | 2 }) {
  return (
    <ol className="flex gap-2" aria-label={t("new.steps")}>
      {STEPS.map((k, i) => (
        <li key={k} aria-current={i === current ? "step" : undefined}
          className={"flex-1 border-t-[3px] pt-1 text-sm " + (i < current ? "border-green text-green" : i === current ? "border-blue text-blue font-semibold" : "border-line text-ink-2")}>
          {i + 1} · {t(k)}
        </li>
      ))}
    </ol>
  );
}
