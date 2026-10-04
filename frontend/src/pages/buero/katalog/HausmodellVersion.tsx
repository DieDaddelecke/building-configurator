/**
 * Büro: eine Version eines Haustyps aus IFC (docs/PLAN_HAUSMODELL.md 3.6, HM3): Lesestand des Imports, Vorschau,
 * Befunde, Entwurf mit den Angaben des Büros, Prüfung gegen die Katalogversion über `engine` und Freigabe durch
 * einen Menschen. Veröffentlichte Versionen sind unveränderlich (L4); Änderungen laufen über eine neue Datei.
 */

import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, useOutletContext, useParams } from "react-router";

import {
  importing,
  useHouseAction,
  useHouseVersion,
  useSaveDecisions,
  type FacadeRole,
  type HouseAction,
  type HouseDraftDecisions,
  type HouseImportReport,
  type HouseTemplateVersionOut,
} from "../../../api/haus";
import type { components } from "../../../api/schema";
import { Befunde } from "../../../haus/import/Befunde";
import { canEditHouse, HausStatusmarke, zeitpunkt } from "../../../haus/import/bausteine";
import { Entwurf, label, nameIncomplete } from "../../../haus/import/Entwurf";
import { ROLE_COLORS, Vorschau } from "../../../haus/import/Vorschau";
import { KatalogFehler, number } from "../../../katalog/bausteine";

type Staff = components["schemas"]["StaffInfo"];
type Step = "save" | HouseAction;

/** Die Datei selbst war nicht lesbar: Nur eine neue oder erneut hochgeladene Datei hilft. */
const READ_FAILURES = new Set([
  "file_unreadable",
  "schema_unsupported",
  "reader_timeout",
  "reader_limit",
  "reader_failed",
  "import_failed",
]);

export const readFailed = (report: HouseImportReport) => report.findings.some((f) => READ_FAILURES.has(f.code));

/** Angaben vergleichen, unabhängig von der Reihenfolge der Schlüssel. */
export function stableJson(value: unknown): string {
  return JSON.stringify(value, (_key, inner: unknown) =>
    inner && typeof inner === "object" && !Array.isArray(inner)
      ? Object.fromEntries(Object.entries(inner).sort(([a], [b]) => (a < b ? -1 : a > b ? 1 : 0)))
      : inner,
  );
}

const editableStatus = (version: HouseTemplateVersionOut) => version.status === "draft" || version.status === "reviewed";

/** Name statt Konto-ID; `cli` und Unbekanntes so, wie es gespeichert ist. */
const person = (version: HouseTemplateVersionOut, actor: string | null) =>
  actor === null ? "–" : (version.people[actor] ?? actor);

function Verlauf({ version }: { version: HouseTemplateVersionOut }) {
  const { t, i18n } = useTranslation();
  const events = (
    [
      ["created", version.created_at, version.created_by],
      ["reviewed", version.reviewed_at, version.reviewed_by],
      ["published", version.published_at, version.published_by],
      ["rejected", version.rejected_at, version.rejected_by],
      ["retired", version.retired_at, version.retired_by],
    ] as const
  ).filter(([, at]) => at !== null);
  return (
    <ul className="m-0 p-0 list-none flex gap-x-4 gap-y-1 flex-wrap text-xs t-mute">
      {events.map(([kind, at, by]) => (
        <li key={kind}>
          {t(`house.version.event.${kind}`, { at: zeitpunkt(at as string, i18n.language), by: person(version, by) })}
        </li>
      ))}
    </ul>
  );
}

function Kopfzeile({ version, staff }: { version: HouseTemplateVersionOut; staff: Staff }) {
  const { t, i18n } = useTranslation();
  const name = version.template ? label(version.template.name, i18n.language) : version.slug;
  const hint =
    version.status === "published"
      ? t("house.version.lockedPublished")
      : version.status === "rejected"
        ? t("house.version.lockedRejected")
        : version.status === "retired"
          ? t("house.version.lockedRetired")
          : null;
  return (
    <div className="flex flex-col gap-2">
      <Link className="link text-sm" to="/buero/katalog/hausmodell">
        {t("house.version.back")}
      </Link>
      <div className="flex items-baseline gap-3 flex-wrap">
        <h2 className="f-display text-3xl font-semibold m-0">{name}</h2>
        <span className="f-mono t-mute">
          {version.slug} · v{version.version}
        </span>
        <HausStatusmarke status={version.status} />
        {version.current && <span className="text-sm t-accent">{t("house.list.current")}</span>}
      </div>
      <p className="m-0 text-sm t-mute">
        {t("house.version.file", {
          name: version.ifc_file_name,
          size:
            version.ifc_size_bytes < 1024 * 1024
              ? t("house.version.kb", { value: number(version.ifc_size_bytes / 1024, i18n.language, 0) })
              : t("house.version.mb", { value: number(version.ifc_size_bytes / (1024 * 1024), i18n.language, 1) }),
        })}{" "}
        · <span className="f-mono">{version.ifc_sha256.slice(0, 12)}</span>
      </p>
      <Verlauf version={version} />
      {hint && <p className="m-0 text-sm t-mute max-w-prose">{hint}</p>}
      {!canEditHouse(staff) && <p className="m-0 text-sm t-mute">{t("house.readOnly")}</p>}
      {editableStatus(version) && !version.catalog.current && (
        <p className="m-0 text-sm t-warn max-w-prose">{t("house.version.catalogChanged")}</p>
      )}
    </div>
  );
}

function Importstand({ version }: { version: HouseTemplateVersionOut }) {
  const { t } = useTranslation();
  const job = version.job;
  if (importing(version)) {
    return (
      <p role="status" className="karte p-4 m-0 text-sm">
        {job?.status === "running" ? t("house.import.running") : t("house.import.queued")}
        {job && job.attempts > 1 && (
          <span className="t-mute"> · {t("house.import.attempt", { attempt: job.attempts, max: job.max_attempts })}</span>
        )}
      </p>
    );
  }
  return <p className="karte p-4 m-0 text-sm t-alert">{t("house.import.missing")}</p>;
}

function Kennwerte({ summary }: { summary: HouseImportReport["summary"] }) {
  const { t, i18n } = useTranslation();
  const m = (value: number | null) => (value === null ? "–" : number(value, i18n.language, 2));
  const rows: [string, string][] = [
    [t("house.summary.storeys"), String(summary.storeys)],
    [t("house.summary.size"), `${m(summary.inner_width)} × ${m(summary.inner_depth)} m`],
    [t("house.summary.area"), summary.inner_area === null ? "–" : `${m(summary.inner_area)} m²`],
    [t("house.summary.rooms"), t("house.summary.roomsValue", { rooms: summary.rooms, zones: summary.zones })],
    [
      t("house.summary.walls"),
      t("house.summary.wallsValue", { exterior: summary.exterior_walls, interior: summary.interior_walls }),
    ],
    [t("house.summary.openings"), t("house.summary.openingsValue", { windows: summary.windows, doors: summary.doors })],
    [t("house.summary.roofLevels"), String(summary.roof_levels)],
  ];
  return (
    <dl className="m-0 grid grid-cols-[auto_1fr] gap-x-6 gap-y-1 text-sm">
      {rows.map(([name, value]) => (
        <div key={name} className="contents">
          <dt className="t-mute">{name}</dt>
          <dd className="m-0 num">{value}</dd>
        </div>
      ))}
    </dl>
  );
}

function Legende() {
  const { t } = useTranslation();
  return (
    <ul className="m-0 p-0 list-none flex gap-4 flex-wrap text-xs t-mute" aria-label={t("house.preview.legend")}>
      {(Object.keys(ROLE_COLORS) as FacadeRole[]).map((role) => (
        <li key={role} className="flex items-center gap-1">
          <span aria-hidden="true" className="inline-block w-4 h-0.5" style={{ background: ROLE_COLORS[role] }} />
          {t(`catalog.facadeRole.${role}`)}
        </li>
      ))}
      <li className="flex items-center gap-1">
        <span aria-hidden="true" className="inline-block w-4 border-t bd-ink" />
        {t("house.preview.window")}
      </li>
      <li className="flex items-center gap-1">
        <span aria-hidden="true" className="inline-block w-4 border-t border-dashed bd-ink" />
        {t("house.preview.door")}
      </li>
      <li className="flex items-center gap-1">
        <span aria-hidden="true" className="inline-block w-3 h-3 bg-warn" />
        {t("house.preview.unassigned")}
      </li>
    </ul>
  );
}

function Kompatibilitaet({ version }: { version: HouseTemplateVersionOut }) {
  const { t, i18n } = useTranslation();
  const result = version.compatibility;
  return (
    <section aria-labelledby="haus-pruefung" className="flex flex-col gap-3">
      <h3 id="haus-pruefung" className="m-0 text-lg font-medium">
        {t("house.check.title")}
      </h3>
      {result === null ? (
        <p className="m-0 text-sm t-mute max-w-prose">{t("house.check.none")}</p>
      ) : (
        <>
          <p className={`m-0 text-sm ${result.supported ? "t-accent" : "t-alert"}`} data-testid="pruefergebnis">
            {result.supported ? t("house.check.supported") : t("house.check.unsupported")}
          </p>
          <p className="m-0 text-xs t-mute">
            {t("house.check.meta", {
              catalog: result.catalog_version,
              domain: result.domain_version,
              at: zeitpunkt(result.checked_at, i18n.language),
              by: person(version, result.checked_by),
            })}
            {result.approved_at &&
              ` · ${t("house.check.approved", {
                at: zeitpunkt(result.approved_at, i18n.language),
                by: person(version, result.approved_by),
              })}`}
          </p>
          {result.issues.length > 0 && (
            <>
              <p className="m-0 text-sm t-mute max-w-prose">{t("house.check.issuesIntro")}</p>
              <ul className="m-0 p-0 list-none flex flex-col gap-1 text-sm">
                {result.issues.map((issue, i) => (
                  <li key={`${issue.code}-${i}`} className="border bd-alert bg-alert p-2 flex flex-col gap-1">
                    {/* Text aus dem Code (E-HM-33); einen neuen Code ohne Text zeigt die Liste roh */}
                    <span>{t(`house.check.issue.${issue.code}`, { defaultValue: issue.code })}</span>
                    <span className="f-mono text-xs t-mute">
                      {[issue.code, issue.slot_id, issue.element_id, issue.ref_id].filter(Boolean).join(" · ")}
                    </span>
                  </li>
                ))}
              </ul>
            </>
          )}
        </>
      )}
    </section>
  );
}

interface AktionenProps {
  version: HouseTemplateVersionOut;
  /** Ungespeicherte Angaben im Entwurf: erst speichern, dann prüfen. */
  changed: boolean;
  pending: boolean;
  onRun: (step: HouseAction) => void;
}

function Aktionen({ version, changed, pending, onRun }: AktionenProps) {
  const { t, i18n } = useTranslation();
  const report = version.report;
  const name = version.template ? label(version.template.name, i18n.language) : version.slug;
  const confirm = (step: HouseAction, key: string) => {
    if (window.confirm(t(key, { name, version: version.version }))) onRun(step);
  };
  const usable = report !== null && !readFailed(report);
  const checkable = editableStatus(version) && usable;
  const open = report !== null && !report.publishable;
  const publishable =
    version.status === "reviewed" && version.catalog.current && version.compatibility?.supported === true && !changed;
  const hint = !checkable
    ? null
    : changed
      ? t("house.actions.saveFirst")
      : open
        ? t("house.actions.openPoints")
        : version.status === "reviewed" && !version.catalog.current
          ? t("house.actions.checkAgain")
          : null;
  if (!editableStatus(version) && version.status !== "published") return null;
  return (
    <div className="flex gap-3 flex-wrap items-center border-t bd pt-6">
      {checkable && (
        <button
          type="button"
          className={version.status === "draft" ? "btn btn-primary" : "btn btn-ghost"}
          disabled={pending || changed || open}
          onClick={() => onRun("check")}
        >
          {version.status === "reviewed" ? t("house.actions.recheck") : t("house.actions.check")}
        </button>
      )}
      {version.status === "reviewed" && (
        <button
          type="button"
          className="btn btn-primary"
          disabled={pending || !publishable}
          onClick={() => confirm("publish", "house.actions.publishConfirm")}
        >
          {t("house.actions.publish")}
        </button>
      )}
      {editableStatus(version) && (
        <button
          type="button"
          className="btn btn-ghost"
          disabled={pending}
          onClick={() => confirm("reject", "house.actions.rejectConfirm")}
        >
          {t("house.actions.reject")}
        </button>
      )}
      {version.status === "published" && (
        <button
          type="button"
          className="btn btn-ghost"
          disabled={pending}
          onClick={() => confirm("retire", "house.actions.retireConfirm")}
        >
          {t("house.actions.retire")}
        </button>
      )}
      {hint && <span className="text-sm t-warn">{hint}</span>}
    </div>
  );
}

interface ArbeitsbereichProps {
  version: HouseTemplateVersionOut;
  report: HouseImportReport;
  staff: Staff;
  pending: boolean;
  saving: boolean;
  saved: boolean;
  onSave: (decisions: HouseDraftDecisions) => void;
  onRun: (step: HouseAction) => void;
}

/** Vorschau, Befunde und Entwurf; neu aufgebaut, sobald sich die gespeicherten Angaben ändern. */
function Arbeitsbereich({ version, report, staff, pending, saving, saved, onSave, onRun }: ArbeitsbereichProps) {
  const { t, i18n } = useTranslation();
  const [draft, setDraft] = useState<HouseDraftDecisions>(version.decisions);
  const [highlighted, setHighlighted] = useState<ReadonlySet<string>>(() => new Set());
  const highlight = (ids: string[]) => setHighlighted(new Set(ids));
  const editable = canEditHouse(staff) && editableStatus(version);
  const changed = stableJson(draft) !== stableJson(version.decisions);
  const template = version.template;
  const failed = readFailed(report);
  const roomNames = Object.fromEntries(version.catalog.room_types.map((type) => [type.id, label(type.name, i18n.language)]));

  return (
    <>
      <div className="grid gap-6 lg:grid-cols-2 items-start">
        {template ? (
          <figure className="m-0 karte p-3 flex flex-col gap-2">
            <Vorschau
              template={template}
              report={report}
              roomNames={roomNames}
              roles={draft.facade_roles}
              highlighted={highlighted}
            />
            <Legende />
            <figcaption className="text-xs t-mute">{t("house.preview.caption")}</figcaption>
          </figure>
        ) : (
          <p className="karte p-4 m-0 text-sm t-alert">
            {failed ? t("house.import.failedHint") : t("house.preview.none")}
          </p>
        )}
        <div className="flex flex-col gap-6">
          {!failed && (
            <section aria-labelledby="haus-kennwerte" className="flex flex-col gap-3">
              <h3 id="haus-kennwerte" className="m-0 text-lg font-medium">
                {t("house.summary.title")}
              </h3>
              <Kennwerte summary={report.summary} />
            </section>
          )}
          <section aria-labelledby="haus-befunde" className="flex flex-col gap-3">
            <h3 id="haus-befunde" className="m-0 text-lg font-medium">
              {t("house.report.findings")}
            </h3>
            {report.publishable ? (
              <p className="m-0 text-sm t-accent">{t("house.report.publishable")}</p>
            ) : (
              <p className="m-0 text-sm t-warn">{t("house.report.blocked")}</p>
            )}
            <Befunde findings={report.findings} template={template} onHighlight={highlight} />
          </section>
        </div>
      </div>

      {!failed && (
        <section aria-labelledby="haus-entwurf" className="flex flex-col gap-6">
          <div className="flex flex-col gap-1">
            <h3 id="haus-entwurf" className="m-0 text-xl font-medium">
              {t("house.draft.title")}
            </h3>
            <p className="m-0 text-sm t-mute max-w-prose">{t("house.draft.intro")}</p>
          </div>
          <Entwurf
            template={template}
            report={report}
            catalog={version.catalog}
            saved={version.decisions}
            draft={draft}
            onChange={setDraft}
            editable={editable}
            onHighlight={highlight}
          />
          {editable && (
            <div className="flex gap-3 items-center flex-wrap">
              <button
                type="button"
                className="btn btn-primary"
                disabled={!changed || nameIncomplete(draft) || saving}
                onClick={() => onSave(draft)}
              >
                {saving ? t("house.draft.saving") : t("house.draft.save")}
              </button>
              <button
                type="button"
                className="btn btn-ghost"
                disabled={!changed || saving}
                onClick={() => setDraft(version.decisions)}
              >
                {t("house.draft.reset")}
              </button>
              {changed ? (
                <span className="text-sm t-warn">
                  {version.status === "reviewed" ? t("house.draft.unsavedReviewed") : t("house.draft.unsaved")}
                </span>
              ) : (
                saved && <span className="text-sm t-accent">{t("house.draft.saved")}</span>
              )}
            </div>
          )}
        </section>
      )}

      {!failed && <Kompatibilitaet version={version} />}
      {canEditHouse(staff) && <Aktionen version={version} changed={changed} pending={pending} onRun={onRun} />}
    </>
  );
}

function VersionDetail({ version, staff }: { version: HouseTemplateVersionOut; staff: Staff }) {
  const save = useSaveDecisions(version.slug, version.version);
  const check = useHouseAction(version.slug, version.version, "check");
  const publish = useHouseAction(version.slug, version.version, "publish");
  const reject = useHouseAction(version.slug, version.version, "reject");
  const retire = useHouseAction(version.slug, version.version, "retire");
  const [last, setLast] = useState<Step | null>(null);
  const actions = { check, publish, reject, retire };
  const steps = { save, ...actions };
  const pending = Object.values(steps).some((step) => step.isPending);
  const error = last ? steps[last].error : null;

  const run = (step: HouseAction) => {
    setLast(step);
    actions[step].mutate();
  };

  return (
    <div className="flex flex-col gap-8">
      <Kopfzeile version={version} staff={staff} />
      {version.report === null ? (
        <>
          <Importstand version={version} />
          {canEditHouse(staff) && <Aktionen version={version} changed={false} pending={pending} onRun={run} />}
        </>
      ) : (
        <Arbeitsbereich
          key={stableJson(version.decisions)}
          version={version}
          report={version.report}
          staff={staff}
          pending={pending}
          saving={save.isPending}
          saved={last === "save" && save.isSuccess}
          onSave={(decisions) => {
            setLast("save");
            save.mutate(decisions);
          }}
          onRun={run}
        />
      )}
      {error && <KatalogFehler error={error} />}
    </div>
  );
}

export function HausmodellVersion() {
  const { t } = useTranslation();
  const staff = useOutletContext<Staff>();
  const { slug = "", version = "" } = useParams();
  const versionNumber = Number(version);
  const query = useHouseVersion(slug, versionNumber);
  if (!Number.isInteger(versionNumber) || versionNumber < 1) {
    return <p className="t-mute">{t("house.version.notFound")}</p>;
  }
  return (
    <>
      {query.isPending && <p className="t-mute">{t("loading")}</p>}
      {query.isError && <KatalogFehler error={query.error} />}
      {query.data && (
        <VersionDetail key={`${query.data.slug}-${query.data.version}`} version={query.data} staff={staff} />
      )}
    </>
  );
}
