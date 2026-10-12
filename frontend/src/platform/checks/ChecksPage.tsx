import { Link } from "react-router";
import Button from "../../design/Button";
import EmptyState from "../../design/EmptyState";
import { useToast } from "../../design/Toast";
import { t } from "../../lib/i18n";
import { useChecks, useRenameCheck } from "../../lib/queries";
import ChecksTable from "./ChecksTable";

export default function ChecksPage() {
  const checks = useChecks();
  const rename = useRenameCheck();
  const toast = useToast();
  if (checks.isPending) return <p className="p-6 text-ink-2">{t("common.loading")}</p>;
  if (checks.isError) return <EmptyState title={t("checks.loadFailed")}>{(checks.error as Error).message}</EmptyState>;
  const rows = checks.data;
  return (
    <section className="p-4 md:p-6 flex flex-col gap-4">
      <div className="flex flex-wrap items-center gap-3">
        <h1 className="text-2xl font-semibold flex-1">{t("checks.count", { n: rows.length })}</h1>
        <Link to="/app/new"><Button variant="primary">+ {t("nav.new")}</Button></Link>
      </div>
      {rows.length === 0
        ? <EmptyState title={t("checks.empty")} action={<Link to="/app/new" className="text-blue underline">{t("nav.new")}</Link>}>{t("checks.empty.body")}</EmptyState>
        : <ChecksTable rows={rows} onRename={(id, title) => rename.mutate({ id, title }, { onError: e => toast((e as Error).message, "error") })} />}
    </section>
  );
}
