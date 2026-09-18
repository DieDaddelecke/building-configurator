/**
 * Büro: ein Typstand (Plan H1 4.2): Kennwerte und Prüfhinweise, Umriss mit Fassadenrollen, Eingang und Garagentor,
 * Axonometrie als Vorschau, RE2020, Grundriss-PDF, Veröffentlichen und Zurückziehen. Veröffentlichte Stände sind
 * unveränderlich (L4): dort ist alles gesperrt, Änderungen laufen über einen neuen Import.
 */

import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, useOutletContext, useParams } from "react-router";

import {
  useDraftPriceCatalog,
  usePackages,
  usePublishType,
  useRetireType,
  useSetFacadeRoles,
  useSetPlacement,
  useTypeVersion,
  type TypeVersionOut,
} from "../../../api/catalog";
import type { components } from "../../../api/schema";
import { Axonometrie } from "../../../katalog/Axonometrie";
import { canEditCatalog, KatalogFehler, number, spanne, Statusmarke } from "../../../katalog/bausteine";
import { readPlacement, type FacadeRole, type Placement, type Ring, type Roles } from "../../../katalog/geometrie";
import { Grundriss, ROLE_COLORS } from "../../../katalog/Grundriss";
import { Energie, Fassadenrollen, PlanDokument, Platzierung } from "../../../katalog/TypFormulare";

type Staff = components["schemas"]["StaffInfo"];

const toRoles = (stored: Record<string, string>): Roles =>
  Object.fromEntries(Object.entries(stored).map(([edge, role]) => [Number(edge), role as FacadeRole]));

const toStored = (roles: Roles): Record<string, FacadeRole> =>
  Object.fromEntries(Object.entries(roles).map(([edge, role]) => [edge, role]));

const toPayload = (value: Placement | null) => (value ? { edge: value.edge, position: value.position } : null);

function Pruefhinweise({ version }: { version: TypeVersionOut }) {
  const { t } = useTranslation();
  if (version.consistency_warnings.length === 0) {
    return <p className="m-0 text-sm t-mute">{t("catalog.type.checks.none")}</p>;
  }
  return (
    <ul className="m-0 p-0 list-none flex flex-col gap-2">
      {version.consistency_warnings.map((finding) => (
        <li
          key={finding.code}
          className={`border p-3 text-sm ${finding.level === "error" ? "bd-alert bg-alert" : "bd-warn bg-warn"}`}
        >
          <strong className={finding.level === "error" ? "t-alert" : "t-warn"}>
            {t(`catalog.type.checks.${finding.level}`)}
          </strong>{" "}
          {finding.detail}
          {finding.level === "error" && <div className="t-mute">{t("catalog.type.checks.blocksPublish")}</div>}
        </li>
      ))}
    </ul>
  );
}

function Kennwerte({ version }: { version: TypeVersionOut }) {
  const { t, i18n } = useTranslation();
  const rows: [string, string][] = [
    [t("catalog.type.storeys"), version.storeys],
    [
      t("catalog.type.roof"),
      [
        t(`catalog.roofForm.${version.roof_form}`),
        version.pitch_deg != null ? `${number(version.pitch_deg, i18n.language)}°` : null,
        version.ridge_direction ? t(`catalog.ridgeDirection.${version.ridge_direction}`) : null,
      ]
        .filter(Boolean)
        .join(" · "),
    ],
    [t("catalog.type.ridgeHeight"), `${number(version.ridge_height_m, i18n.language, 2)} m`],
    [t("catalog.type.eaveHeight"), `${number(version.eave_height_m, i18n.language, 2)} m`],
    [t("catalog.type.livingArea"), `${number(version.living_area_m2, i18n.language)} m²`],
    [t("catalog.type.rooms"), version.rooms_text],
    [t("catalog.type.footprintFacade"), `${number(version.footprint_facade_area_m2, i18n.language)} m²`],
    [t("catalog.type.footprintProjection"), `${number(version.footprint_projection_area_m2, i18n.language)} m²`],
    [t("catalog.type.basePrice"), spanne(version.base_price_min_cents, version.base_price_max_cents, i18n.language)],
  ];
  return (
    <dl className="m-0 grid grid-cols-[auto_1fr] gap-x-6 gap-y-1 text-sm">
      {rows.map(([label, value]) => (
        <div key={label} className="contents">
          <dt className="t-mute">{label}</dt>
          <dd className="m-0 num">{value}</dd>
        </div>
      ))}
    </dl>
  );
}

function Raeume({ version }: { version: TypeVersionOut }) {
  const { t, i18n } = useTranslation();
  const total = version.rooms.reduce((sum, room) => sum + room.area_m2, 0);
  return (
    <table className="w-full text-sm border-collapse">
      <thead>
        <tr className="text-left border-b bd-strong">
          <th scope="col" className="py-2 pr-3 font-medium">{t("catalog.type.room.name")}</th>
          <th scope="col" className="py-2 pr-3 font-medium">{t("catalog.type.room.category")}</th>
          <th scope="col" className="py-2 pr-3 font-medium">{t("catalog.type.room.storey")}</th>
          <th scope="col" className="py-2 font-medium text-right">{t("catalog.type.room.area")}</th>
        </tr>
      </thead>
      <tbody>
        {version.rooms.map((room, i) => (
          <tr key={`${room.name}-${i}`} className="border-b bd">
            <td className="py-2 pr-3">{room.name}</td>
            <td className="py-2 pr-3">{t(`catalog.roomCategory.${room.category}`, { defaultValue: room.category })}</td>
            <td className="py-2 pr-3 f-mono">{room.storey}</td>
            <td className="py-2 text-right num">{number(room.area_m2, i18n.language)} m²</td>
          </tr>
        ))}
      </tbody>
      <tfoot>
        <tr>
          <th scope="row" colSpan={3} className="py-2 pr-3 text-left font-medium">{t("catalog.type.room.total")}</th>
          <td className="py-2 text-right num font-medium">{number(total, i18n.language)} m²</td>
        </tr>
      </tfoot>
    </table>
  );
}

function Legende() {
  const { t } = useTranslation();
  return (
    <ul className="m-0 p-0 list-none flex gap-4 flex-wrap text-xs t-mute" aria-label={t("catalog.type.legend")}>
      {(Object.keys(ROLE_COLORS) as FacadeRole[]).map((role) => (
        <li key={role} className="flex items-center gap-1">
          <span aria-hidden="true" className="inline-block w-4 h-0.5" style={{ background: ROLE_COLORS[role] }} />
          {t(`catalog.facadeRole.${role}`)}
        </li>
      ))}
    </ul>
  );
}

function TypDetail({ version, staff }: { version: TypeVersionOut; staff: Staff }) {
  const { t, i18n } = useTranslation();
  const slug = version.slug;
  const ring = version.footprint_facade as Ring;
  const editable = canEditCatalog(staff) && (version.status === "draft" || version.status === "review");
  const [roles, setRoles] = useState<Roles>(() => toRoles(version.facade_roles));
  const [entrance, setEntrance] = useState<Placement | null>(() => readPlacement(version.entrance));
  const [garageDoor, setGarageDoor] = useState<Placement | null>(() => readPlacement(version.garage_door));
  const [highlighted, setHighlighted] = useState<number | null>(null);

  const saveRoles = useSetFacadeRoles(slug, version.version);
  const savePlacement = useSetPlacement(slug, version.version);
  const publish = usePublishType(slug, version.version);
  const retire = useRetireType(slug, version.version);
  const packages = usePackages();
  const prices = useDraftPriceCatalog();

  const hasError = version.consistency_warnings.some((finding) => finding.level === "error");
  const canRetire = canEditCatalog(staff) && version.status !== "retired";
  const mutationError = saveRoles.error ?? savePlacement.error ?? publish.error ?? retire.error;

  return (
    <div className="flex flex-col gap-8">
      <div className="flex flex-col gap-2">
        <Link className="link text-sm" to="/buero/katalog">
          {t("catalog.type.back")}
        </Link>
        <div className="flex items-baseline gap-3 flex-wrap">
          <h2 className="f-display text-3xl font-semibold m-0">{version.name}</h2>
          <span className="f-mono t-mute">
            {slug} · v{version.version}
          </span>
          <Statusmarke status={version.status} />
        </div>
        {!editable && canEditCatalog(staff) && version.status === "published" && (
          <p className="m-0 text-sm t-mute max-w-prose">{t("catalog.type.lockedPublished")}</p>
        )}
        {!canEditCatalog(staff) && <p className="m-0 text-sm t-mute">{t("catalog.readOnly")}</p>}
      </div>

      <div className="grid gap-6 lg:grid-cols-2 items-start">
        <figure className="m-0 karte p-3 flex flex-col gap-2">
          <Grundriss
            facade={ring}
            projection={version.footprint_projection as Ring}
            roles={roles}
            entrance={entrance}
            garageDoor={garageDoor}
            highlighted={highlighted}
          />
          <Legende />
          <figcaption className="text-xs t-mute">{t("catalog.type.planCaption")}</figcaption>
        </figure>
        <figure className="m-0 karte p-3 flex flex-col gap-2">
          <Axonometrie version={version} />
          <figcaption className="text-xs t-mute">{t("catalog.type.axoCaption")}</figcaption>
        </figure>
      </div>

      <section aria-labelledby="typ-kennwerte" className="grid gap-6 lg:grid-cols-2 items-start">
        <div className="flex flex-col gap-3">
          <h3 id="typ-kennwerte" className="m-0 text-lg font-medium">{t("catalog.type.values")}</h3>
          <Kennwerte version={version} />
        </div>
        <div className="flex flex-col gap-3">
          <h3 className="m-0 text-lg font-medium">{t("catalog.type.checks.title")}</h3>
          <Pruefhinweise version={version} />
        </div>
      </section>

      <section aria-labelledby="typ-raeume" className="flex flex-col gap-3">
        <h3 id="typ-raeume" className="m-0 text-lg font-medium">{t("catalog.type.room.title")}</h3>
        <Raeume version={version} />
      </section>

      <Fassadenrollen
        ring={ring}
        roles={roles}
        onChange={setRoles}
        onHighlight={setHighlighted}
        editable={editable}
        saving={saveRoles.isPending}
        saved={saveRoles.isSuccess}
        onSave={() => saveRoles.mutate(toStored(roles))}
      />

      <Platzierung
        edgeCount={ring.length}
        entrance={entrance}
        garageDoor={garageDoor}
        onEntrance={setEntrance}
        onGarageDoor={setGarageDoor}
        editable={editable}
        saving={savePlacement.isPending}
        saved={savePlacement.isSuccess}
        onSave={() => savePlacement.mutate({ entrance: toPayload(entrance), garage_door: toPayload(garageDoor) })}
      />

      {packages.isSuccess && prices.isSuccess ? (
        <Energie
          typeSlug={slug}
          packages={packages.data}
          assessments={prices.data.energy_assessments}
          language={i18n.language}
          editable={canEditCatalog(staff)}
        />
      ) : (
        <p className="t-mute">{t("loading")}</p>
      )}

      {canEditCatalog(staff) && <PlanDokument slug={slug} />}

      {mutationError && <KatalogFehler error={mutationError} />}

      {(editable || canRetire) && (
        <div className="flex gap-3 flex-wrap items-center border-t bd pt-6">
          {editable && (
            <button
              type="button"
              className="btn btn-primary"
              disabled={hasError || publish.isPending}
              onClick={() => {
                if (window.confirm(t("catalog.type.publishConfirm", { name: version.name, version: version.version }))) {
                  publish.mutate();
                }
              }}
            >
              {t("catalog.type.publish")}
            </button>
          )}
          {canRetire && (
            <button
              type="button"
              className="btn btn-ghost"
              disabled={retire.isPending}
              onClick={() => {
                if (window.confirm(t("catalog.type.retireConfirm", { name: version.name, version: version.version }))) {
                  retire.mutate();
                }
              }}
            >
              {t("catalog.type.retire")}
            </button>
          )}
          {editable && hasError && <span className="text-sm t-alert">{t("catalog.type.publishBlocked")}</span>}
        </div>
      )}
    </div>
  );
}

export function KatalogTyp() {
  const { t } = useTranslation();
  const staff = useOutletContext<Staff>();
  const { slug = "", version = "" } = useParams();
  const query = useTypeVersion(slug, Number(version));
  return (
    <>
      {query.isPending && <p className="t-mute">{t("loading")}</p>}
      {query.isError && <KatalogFehler error={query.error} />}
      {query.data && <TypDetail key={query.data.id} version={query.data} staff={staff} />}
    </>
  );
}
