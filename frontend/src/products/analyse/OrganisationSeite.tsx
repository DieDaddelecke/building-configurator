/**
 * Seite „Organisation“ (AN6, docs/PLAN_AN6_MANDANTEN.md 3.7): Verbrauch für alle Mitglieder; Mitglieder,
 * Erscheinungsbild und API-Schlüssel nur für die Rolle `admin`. Rechte prüft der Server; die Seite blendet nur
 * aus, was ein Mitglied nicht darf. Budget und Kontingent setzt der Betreiber (Abo), nicht die Organisation.
 */

import { useId, useState, type FormEvent, type ReactNode } from "react";
import { useTranslation } from "react-i18next";

import {
  logoUrl,
  useAddMember,
  useApiKeys,
  useChangeMemberRole,
  useCreateApiKey,
  useMembers,
  useOrganisation,
  useRemoveLogo,
  useRemoveMember,
  useRevokeApiKey,
  useUpdateOrganisation,
  useUploadLogo,
  useUsage,
  type ApiKeyCreatedOut,
  type OrganisationOut,
  type OrganisationRole,
} from "../../api/organisation";
import { useSession } from "../../api/session";
import { Kopf } from "../../components/Kopf";
import { formatNumber } from "../../site/geo";
import { fehlerText } from "./fehler";

const PREFIX = "analyse.organisation";
const ROLLEN: readonly OrganisationRole[] = ["member", "admin"];
const ADRESSZEILEN = 4;
const SCHLUESSEL_TAGE = 365;
const SCHLUESSEL_TAGE_MAX = 730;
/** WCAG AA für Text auf Weiß; der Server prüft dieselbe Grenze (3.5). */
export const MIN_KONTRAST = 4.5;

/** Kontrast einer Farbe `#rrggbb` zu Weiß nach WCAG 2.1. */
export function kontrastZuWeiss(farbe: string): number | null {
  if (!/^#[0-9a-fA-F]{6}$/.test(farbe)) return null;
  const kanal = (index: number) => {
    const wert = parseInt(farbe.slice(index, index + 2), 16) / 255;
    return wert <= 0.03928 ? wert / 12.92 : ((wert + 0.055) / 1.055) ** 2.4;
  };
  const helligkeit = 0.2126 * kanal(1) + 0.7152 * kanal(3) + 0.0722 * kanal(5);
  return 1.05 / (helligkeit + 0.05);
}

function monat(value: string, language: string): string {
  return new Date(`${value}-01T00:00:00Z`).toLocaleDateString(language, {
    month: "long",
    year: "numeric",
    timeZone: "UTC",
  });
}

function datum(value: string | null | undefined, language: string): string {
  return value ? new Date(value).toLocaleDateString(language) : "–";
}

function Abschnitt({ id, titel, children }: { id: string; titel: string; children: ReactNode }) {
  return (
    <section aria-labelledby={id} className="flex flex-col gap-4">
      <h2 id={id} className="eyebrow m-0">
        {titel}
      </h2>
      <div className="karte p-5 flex flex-col gap-5">{children}</div>
    </section>
  );
}

function Balken({ wert, grenze }: { wert: number; grenze: number | null }) {
  if (grenze === null || grenze <= 0) return null;
  const anteil = Math.min(1, wert / grenze);
  return (
    <div className="h-1.5 w-full bg-paper border bd" aria-hidden="true">
      <div className={`h-full ${anteil >= 1 ? "bg-alert" : "bg-accent"}`} style={{ width: `${anteil * 100}%` }} />
    </div>
  );
}

// ---------------------------------------------------------------------------
// Verbrauch (3.4)
// ---------------------------------------------------------------------------

function Verbrauch() {
  const { t, i18n } = useTranslation();
  const usage = useUsage();
  const data = usage.data;
  const aktuell = data?.months[0];
  const dollar = (value: number) => `${formatNumber(value, i18n.language, 2)} $`;

  return (
    <Abschnitt id="org-verbrauch" titel={t(`${PREFIX}.usage.title`)}>
      {usage.isPending && <p className="t-mute m-0">{t("loading")}</p>}
      {usage.isError && <p className="t-alert m-0">{t("error.generic")}</p>}
      {data && aktuell && (
        <>
          <div className="grid gap-5 sm:grid-cols-2">
            <div className="flex flex-col gap-2">
              <span className="text-sm t-mute">{t(`${PREFIX}.usage.cost`)}</span>
              <span className="f-mono num t-ink" data-testid="usage-cost">
                {data.budget_month_usd === null
                  ? dollar(aktuell.cost_usd)
                  : t(`${PREFIX}.usage.ofLimit`, { value: dollar(aktuell.cost_usd), limit: dollar(data.budget_month_usd) })}
              </span>
              <Balken wert={aktuell.cost_usd} grenze={data.budget_month_usd} />
              {data.budget_month_usd === null && <span className="text-xs t-mute">{t(`${PREFIX}.usage.noLimit`)}</span>}
            </div>
            <div className="flex flex-col gap-2">
              <span className="text-sm t-mute">{t(`${PREFIX}.usage.ocr`)}</span>
              <span className="f-mono num t-ink" data-testid="usage-ocr">
                {data.ocr_pages_month === null
                  ? t(`${PREFIX}.usage.pages`, { count: aktuell.ocr_pages })
                  : t(`${PREFIX}.usage.pagesOfLimit`, { count: aktuell.ocr_pages, limit: data.ocr_pages_month })}
              </span>
              <Balken wert={aktuell.ocr_pages} grenze={data.ocr_pages_month} />
            </div>
          </div>
          <p className="text-xs t-mute m-0">{t(`${PREFIX}.usage.hint`)}</p>
          <div className="overflow-x-auto">
            <table className="w-full text-sm border-collapse">
              <caption className="sr-only">{t(`${PREFIX}.usage.history`)}</caption>
              <thead>
                <tr className="text-left border-b bd-strong">
                  <th scope="col" className="py-2 pr-4 font-medium">{t(`${PREFIX}.usage.month`)}</th>
                  <th scope="col" className="py-2 pr-4 font-medium text-right">{t(`${PREFIX}.usage.cost`)}</th>
                  <th scope="col" className="py-2 font-medium text-right">{t(`${PREFIX}.usage.ocr`)}</th>
                </tr>
              </thead>
              <tbody>
                {data.months.map((entry) => (
                  <tr key={entry.month} className="border-b bd">
                    <td className="py-2 pr-4">{monat(entry.month, i18n.language)}</td>
                    <td className="py-2 pr-4 text-right f-mono num">{dollar(entry.cost_usd)}</td>
                    <td className="py-2 text-right f-mono num">{entry.ocr_pages}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </Abschnitt>
  );
}

// ---------------------------------------------------------------------------
// Mitglieder (3.1)
// ---------------------------------------------------------------------------

function Mitglieder({ selbst }: { selbst: string }) {
  const { t, i18n } = useTranslation();
  const members = useMembers(true);
  const add = useAddMember();
  const change = useChangeMemberRole();
  const remove = useRemoveMember();
  const [email, setEmail] = useState("");
  const [rolle, setRolle] = useState<OrganisationRole>("member");
  const [entfernen, setEntfernen] = useState<string | null>(null);
  const emailId = useId();
  const rolleId = useId();
  const fehler = add.error ?? change.error ?? remove.error;

  const hinzufuegen = (event: FormEvent) => {
    event.preventDefault();
    add.mutate({ email: email.trim(), role: rolle }, { onSuccess: () => setEmail("") });
  };

  return (
    <Abschnitt id="org-mitglieder" titel={t(`${PREFIX}.members.title`)}>
      {members.isPending && <p className="t-mute m-0">{t("loading")}</p>}
      {members.isError && <p className="t-alert m-0">{t("error.generic")}</p>}
      {members.data && (
        <ul className="m-0 p-0 list-none">
          {members.data.map((member) => (
            <li
              key={member.id}
              className="flex flex-col gap-2 py-3 border-t bd first:border-t-0 first:pt-0 sm:flex-row sm:items-center sm:justify-between"
            >
              <span className="text-sm min-w-0">
                <span className="t-ink break-words">{member.display_name ?? member.email}</span>
                {member.display_name && <span className="block t-mute break-words">{member.email}</span>}
                <span className="block text-xs t-mute">
                  {!member.active
                    ? t(`${PREFIX}.members.inactive`)
                    : member.signed_in
                      ? t(`${PREFIX}.members.lastLogin`, { date: datum(member.last_login_at, i18n.language) })
                      : t(`${PREFIX}.members.notYet`)}
                </span>
              </span>
              <span className="flex flex-wrap items-center gap-2">
                <select
                  className="field w-auto py-1"
                  aria-label={t(`${PREFIX}.members.roleFor`, { email: member.email })}
                  value={member.role}
                  disabled={change.isPending}
                  onChange={(event) =>
                    change.mutate({ userId: member.id, role: event.target.value as OrganisationRole })
                  }
                >
                  {ROLLEN.map((value) => (
                    <option key={value} value={value}>
                      {t(`${PREFIX}.role.${value}`)}
                    </option>
                  ))}
                </select>
                {member.id !== selbst &&
                  (entfernen === member.id ? (
                    <>
                      <button
                        type="button"
                        className="btn btn-ghost"
                        onClick={() => remove.mutate(member.id, { onSettled: () => setEntfernen(null) })}
                        disabled={remove.isPending}
                      >
                        {t(`${PREFIX}.members.confirmRemove`)}
                      </button>
                      <button type="button" className="link text-sm" onClick={() => setEntfernen(null)}>
                        {t(`${PREFIX}.cancel`)}
                      </button>
                    </>
                  ) : (
                    <button type="button" className="btn btn-ghost" onClick={() => setEntfernen(member.id)}>
                      {t(`${PREFIX}.members.remove`)}
                    </button>
                  ))}
              </span>
            </li>
          ))}
        </ul>
      )}
      <form className="flex flex-col gap-3 border-t bd pt-4" onSubmit={hinzufuegen}>
        <h3 className="m-0 text-base font-medium t-ink">{t(`${PREFIX}.members.add`)}</h3>
        <div className="flex flex-col gap-3 sm:flex-row sm:items-end">
          <div className="flex flex-col gap-1 flex-1 min-w-0">
            <label htmlFor={emailId} className="text-sm t-mute">
              {t(`${PREFIX}.members.email`)}
            </label>
            <input
              id={emailId}
              className="field"
              type="email"
              required
              autoComplete="off"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
            />
          </div>
          <div className="flex flex-col gap-1">
            <label htmlFor={rolleId} className="text-sm t-mute">
              {t(`${PREFIX}.members.role`)}
            </label>
            <select
              id={rolleId}
              className="field"
              value={rolle}
              onChange={(event) => setRolle(event.target.value as OrganisationRole)}
            >
              {ROLLEN.map((value) => (
                <option key={value} value={value}>
                  {t(`${PREFIX}.role.${value}`)}
                </option>
              ))}
            </select>
          </div>
          <button type="submit" className="btn btn-primary" disabled={add.isPending}>
            {t(`${PREFIX}.members.submit`)}
          </button>
        </div>
        <p className="text-xs t-mute m-0">{t(`${PREFIX}.members.hint`)}</p>
      </form>
      {fehler && (
        <p className="text-sm t-alert m-0" role="alert">
          {fehlerText(t, fehler, PREFIX)}
        </p>
      )}
    </Abschnitt>
  );
}

// ---------------------------------------------------------------------------
// Erscheinungsbild (3.5)
// ---------------------------------------------------------------------------

interface Entwurf {
  display_name: string;
  address: string;
  phone: string;
  email: string;
  website: string;
  registration: string;
  accent_color: string;
}

function entwurfAus(org: OrganisationOut): Entwurf {
  return {
    display_name: org.display_name,
    address: org.address_lines.join("\n"),
    phone: org.phone ?? "",
    email: org.email ?? "",
    website: org.website ?? "",
    registration: org.registration ?? "",
    accent_color: org.accent_color ?? "",
  };
}

function adresszeilen(address: string): string[] {
  return address
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean)
    .slice(0, ADRESSZEILEN);
}

/** Kopf der ersten Berichtsseite, wie ihn der Server setzt (report.py `_brand`). */
function Vorschau({ entwurf, org }: { entwurf: Entwurf; org: OrganisationOut }) {
  const { t } = useTranslation();
  const kontrast = kontrastZuWeiss(entwurf.accent_color);
  const farbe = kontrast !== null && kontrast >= MIN_KONTRAST ? entwurf.accent_color : "#1c2220";
  const kontakt = [entwurf.phone, entwurf.email, entwurf.website].map((v) => v.trim()).filter(Boolean).join(" · ");
  const zeilen = [...adresszeilen(entwurf.address), kontakt, entwurf.registration.trim()].filter(Boolean);
  return (
    <figure className="m-0 flex flex-col gap-2">
      <figcaption className="text-sm t-mute">{t(`${PREFIX}.branding.preview`)}</figcaption>
      {/* Der Bericht ist immer hell; die Vorschau auch, unabhängig vom Farbschema der Seite */}
      <div
        className="border bd p-4 flex flex-col-reverse gap-4 sm:flex-row sm:justify-between"
        style={{ background: "#ffffff", color: "#1c2220" }}
        data-testid="branding-preview"
      >
        <div className="min-w-0">
          <div className="text-xs uppercase tracking-wide" style={{ color: "#59625e" }}>
            {t(`${PREFIX}.branding.previewEyebrow`)}
          </div>
          <div className="text-lg font-semibold" style={{ color: farbe, borderBottom: `2px solid ${farbe}` }}>
            {t(`${PREFIX}.branding.previewTitle`)}
          </div>
        </div>
        <div className="flex flex-col gap-1 sm:items-end sm:text-right text-xs min-w-0">
          {org.has_logo && (
            <img src={logoUrl(org.branding_revision)} alt="" className="max-h-12 max-w-40 object-contain" />
          )}
          <span className="text-sm font-semibold break-words">{entwurf.display_name.trim() || org.display_name}</span>
          {zeilen.map((zeile) => (
            <span key={zeile} className="break-words" style={{ color: "#59625e" }}>
              {zeile}
            </span>
          ))}
        </div>
      </div>
    </figure>
  );
}

function Feld({
  label,
  value,
  onChange,
  type = "text",
  maxLength,
  hinweis,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  type?: string;
  maxLength?: number;
  hinweis?: string;
}) {
  const id = useId();
  return (
    <div className="flex flex-col gap-1 min-w-0">
      <label htmlFor={id} className="text-sm t-mute">
        {label}
      </label>
      <input
        id={id}
        className="field"
        type={type}
        value={value}
        maxLength={maxLength}
        onChange={(event) => onChange(event.target.value)}
      />
      {hinweis && <span className="text-xs t-mute">{hinweis}</span>}
    </div>
  );
}

function ErscheinungsbildFormular({ org }: { org: OrganisationOut }) {
  const { t, i18n } = useTranslation();
  const update = useUpdateOrganisation();
  const upload = useUploadLogo();
  const removeLogo = useRemoveLogo();
  const [entwurf, setEntwurf] = useState<Entwurf>(() => entwurfAus(org));
  const adresseId = useId();
  const farbeId = useId();
  const logoId = useId();
  const set = (field: keyof Entwurf) => (value: string) => setEntwurf((alt) => ({ ...alt, [field]: value }));
  const farbe = entwurf.accent_color.trim().toLowerCase();
  const kontrast = farbe ? kontrastZuWeiss(farbe) : null;
  const farbeUngueltig = farbe !== "" && (kontrast === null || kontrast < MIN_KONTRAST);
  const fehler = update.error ?? upload.error ?? removeLogo.error;

  const speichern = (event: FormEvent) => {
    event.preventDefault();
    update.mutate({
      display_name: entwurf.display_name.trim() || org.display_name,
      address_lines: adresszeilen(entwurf.address),
      phone: entwurf.phone,
      email: entwurf.email,
      website: entwurf.website,
      registration: entwurf.registration,
      accent_color: farbe || null,
    });
  };

  return (
    <>
      <p className="t-mute text-sm m-0">{t(`${PREFIX}.branding.intro`)}</p>
      <form className="grid gap-4 sm:grid-cols-2" onSubmit={speichern}>
        <Feld
          label={t(`${PREFIX}.branding.displayName`)}
          value={entwurf.display_name}
          onChange={set("display_name")}
          maxLength={200}
        />
        <Feld
          label={t(`${PREFIX}.branding.registration`)}
          value={entwurf.registration}
          onChange={set("registration")}
          maxLength={120}
          hinweis={t(`${PREFIX}.branding.registrationHint`)}
        />
        <div className="flex flex-col gap-1 sm:row-span-2 min-w-0">
          <label htmlFor={adresseId} className="text-sm t-mute">
            {t(`${PREFIX}.branding.address`)}
          </label>
          <textarea
            id={adresseId}
            className="field"
            rows={ADRESSZEILEN}
            value={entwurf.address}
            onChange={(event) => set("address")(event.target.value)}
          />
          <span className="text-xs t-mute">{t(`${PREFIX}.branding.addressHint`, { count: ADRESSZEILEN })}</span>
        </div>
        <Feld label={t(`${PREFIX}.branding.phone`)} value={entwurf.phone} onChange={set("phone")} type="tel" maxLength={40} />
        <Feld label={t(`${PREFIX}.branding.email`)} value={entwurf.email} onChange={set("email")} type="email" maxLength={320} />
        <Feld label={t(`${PREFIX}.branding.website`)} value={entwurf.website} onChange={set("website")} maxLength={200} />
        <div className="flex flex-col gap-1 min-w-0">
          <label htmlFor={farbeId} className="text-sm t-mute">
            {t(`${PREFIX}.branding.accent`)}
          </label>
          <div className="flex gap-2">
            <input
              type="color"
              className="h-11 w-12 border bd-strong bg-sheet p-1 flex-none"
              aria-label={t(`${PREFIX}.branding.accentPicker`)}
              value={kontrast === null ? "#2b45b0" : farbe}
              onChange={(event) => set("accent_color")(event.target.value)}
            />
            <input
              id={farbeId}
              className="field f-mono"
              placeholder="#2b45b0"
              maxLength={7}
              value={entwurf.accent_color}
              aria-invalid={farbeUngueltig}
              onChange={(event) => set("accent_color")(event.target.value)}
            />
          </div>
          <span className={`text-xs ${farbeUngueltig ? "t-alert" : "t-mute"}`}>
            {farbeUngueltig
              ? t(`${PREFIX}.branding.accentTooLight`, { min: formatNumber(MIN_KONTRAST, i18n.language, 1) })
              : t(`${PREFIX}.branding.accentHint`)}
          </span>
        </div>
        <div className="flex flex-wrap items-center gap-3 sm:col-span-2">
          <button type="submit" className="btn btn-primary" disabled={update.isPending || farbeUngueltig}>
            {t(`${PREFIX}.branding.save`)}
          </button>
          {update.isSuccess && (
            <span className="text-sm t-mute" role="status">
              {t(`${PREFIX}.branding.saved`)}
            </span>
          )}
        </div>
      </form>

      <div className="flex flex-col gap-2 border-t bd pt-4">
        <label htmlFor={logoId} className="text-sm t-mute">
          {t(`${PREFIX}.branding.logo`)}
        </label>
        <div className="flex flex-wrap items-center gap-3">
          <input
            id={logoId}
            type="file"
            accept="image/png,image/jpeg"
            className="text-sm max-w-full"
            disabled={upload.isPending}
            onChange={(event) => {
              const file = event.target.files?.[0];
              if (file) upload.mutate(file);
              event.target.value = "";
            }}
          />
          {org.has_logo && (
            <button type="button" className="btn btn-ghost" onClick={() => removeLogo.mutate()} disabled={removeLogo.isPending}>
              {t(`${PREFIX}.branding.removeLogo`)}
            </button>
          )}
        </div>
        <span className="text-xs t-mute">{t(`${PREFIX}.branding.logoHint`)}</span>
      </div>

      {fehler && (
        <p className="text-sm t-alert m-0" role="alert">
          {fehlerText(t, fehler, PREFIX)}
        </p>
      )}
      <Vorschau entwurf={entwurf} org={org} />
    </>
  );
}

function Erscheinungsbild() {
  const { t } = useTranslation();
  const organisation = useOrganisation();
  return (
    <Abschnitt id="org-erscheinungsbild" titel={t(`${PREFIX}.branding.title`)}>
      {organisation.isPending && <p className="t-mute m-0">{t("loading")}</p>}
      {organisation.isError && <p className="t-alert m-0">{t("error.generic")}</p>}
      {/* Ohne `key`: Ein neues Logo lässt ungespeicherte Eingaben stehen */}
      {organisation.data && <ErscheinungsbildFormular org={organisation.data} />}
    </Abschnitt>
  );
}

// ---------------------------------------------------------------------------
// API-Schlüssel (3.6)
// ---------------------------------------------------------------------------

function NeuerSchluessel({ created, onClose }: { created: ApiKeyCreatedOut; onClose: () => void }) {
  const { t } = useTranslation();
  const [kopiert, setKopiert] = useState(false);
  const kopieren = () => {
    void navigator.clipboard?.writeText(created.token).then(() => setKopiert(true));
  };
  return (
    <div className="border bd-accent bg-tint p-4 flex flex-col gap-3" role="status">
      <p className="m-0 text-sm t-ink font-medium">{t(`${PREFIX}.keys.createdTitle`, { name: created.name })}</p>
      <code className="f-mono text-sm break-all bg-sheet border bd p-2" data-testid="api-key-token">
        {created.token}
      </code>
      <p className="m-0 text-xs t-mute">{t(`${PREFIX}.keys.createdHint`)}</p>
      <div className="flex flex-wrap gap-3">
        <button type="button" className="btn btn-primary" onClick={kopieren}>
          {kopiert ? t(`${PREFIX}.keys.copied`) : t(`${PREFIX}.keys.copy`)}
        </button>
        <button type="button" className="btn btn-ghost" onClick={onClose}>
          {t(`${PREFIX}.keys.done`)}
        </button>
      </div>
    </div>
  );
}

function ApiSchluessel() {
  const { t, i18n } = useTranslation();
  const keys = useApiKeys(true);
  const create = useCreateApiKey();
  const revoke = useRevokeApiKey();
  const [name, setName] = useState("");
  const [schreiben, setSchreiben] = useState(false);
  const [tage, setTage] = useState(SCHLUESSEL_TAGE);
  const [neu, setNeu] = useState<ApiKeyCreatedOut | null>(null);
  const [widerrufen, setWiderrufen] = useState<string | null>(null);
  const nameId = useId();
  const tageId = useId();
  const fehler = create.error ?? revoke.error;

  const anlegen = (event: FormEvent) => {
    event.preventDefault();
    create.mutate(
      { name: name.trim(), scopes: schreiben ? ["read", "write"] : ["read"], days: tage },
      {
        onSuccess: (created) => {
          setNeu(created);
          setName("");
        },
      },
    );
  };

  return (
    <Abschnitt id="org-schluessel" titel={t(`${PREFIX}.keys.title`)}>
      <p className="t-mute text-sm m-0">{t(`${PREFIX}.keys.intro`)}</p>
      {neu && <NeuerSchluessel created={neu} onClose={() => setNeu(null)} />}

      {keys.isPending && <p className="t-mute m-0">{t("loading")}</p>}
      {keys.isError && <p className="t-alert m-0">{t("error.generic")}</p>}
      {keys.data?.length === 0 && <p className="t-mute text-sm m-0">{t(`${PREFIX}.keys.empty`)}</p>}
      {keys.data && keys.data.length > 0 && (
        <ul className="m-0 p-0 list-none">
          {keys.data.map((key) => (
            <li
              key={key.id}
              className="flex flex-col gap-2 py-3 border-t bd first:border-t-0 first:pt-0 sm:flex-row sm:items-center sm:justify-between"
            >
              <span className="text-sm min-w-0">
                <span className={key.revoked_at ? "t-mute line-through" : "t-ink"}>{key.name}</span>
                <span className="block f-mono text-xs t-mute">
                  emp_{key.prefix}_… · {t(`${PREFIX}.keys.scope.${key.scopes.includes("write") ? "write" : "read"}`)}
                </span>
                <span className="block text-xs t-mute">
                  {key.revoked_at
                    ? t(`${PREFIX}.keys.revokedOn`, { date: datum(key.revoked_at, i18n.language) })
                    : t(`${PREFIX}.keys.meta`, {
                        created: datum(key.created_at, i18n.language),
                        used: datum(key.last_used_at, i18n.language),
                        expires: datum(key.expires_at, i18n.language),
                      })}
                </span>
              </span>
              {!key.revoked_at &&
                (widerrufen === key.id ? (
                  <span className="flex flex-wrap items-center gap-2">
                    <button
                      type="button"
                      className="btn btn-ghost"
                      onClick={() => revoke.mutate(key.id, { onSettled: () => setWiderrufen(null) })}
                      disabled={revoke.isPending}
                    >
                      {t(`${PREFIX}.keys.confirmRevoke`)}
                    </button>
                    <button type="button" className="link text-sm" onClick={() => setWiderrufen(null)}>
                      {t(`${PREFIX}.cancel`)}
                    </button>
                  </span>
                ) : (
                  <button type="button" className="btn btn-ghost self-start sm:self-auto" onClick={() => setWiderrufen(key.id)}>
                    {t(`${PREFIX}.keys.revoke`)}
                  </button>
                ))}
            </li>
          ))}
        </ul>
      )}

      <form className="flex flex-col gap-3 border-t bd pt-4" onSubmit={anlegen}>
        <h3 className="m-0 text-base font-medium t-ink">{t(`${PREFIX}.keys.new`)}</h3>
        <div className="flex flex-col gap-3 sm:flex-row sm:items-end">
          <div className="flex flex-col gap-1 flex-1 min-w-0">
            <label htmlFor={nameId} className="text-sm t-mute">
              {t(`${PREFIX}.keys.name`)}
            </label>
            <input
              id={nameId}
              className="field"
              required
              minLength={2}
              maxLength={80}
              value={name}
              onChange={(event) => setName(event.target.value)}
            />
          </div>
          <div className="flex flex-col gap-1 sm:w-32">
            <label htmlFor={tageId} className="text-sm t-mute">
              {t(`${PREFIX}.keys.days`)}
            </label>
            <input
              id={tageId}
              className="field"
              type="number"
              min={1}
              max={SCHLUESSEL_TAGE_MAX}
              value={tage}
              onChange={(event) => setTage(Number(event.target.value) || SCHLUESSEL_TAGE)}
            />
          </div>
        </div>
        <label className="flex items-center gap-2 text-sm cursor-pointer">
          <input type="checkbox" checked={schreiben} onChange={(event) => setSchreiben(event.target.checked)} />
          {t(`${PREFIX}.keys.writeScope`)}
        </label>
        <div>
          <button type="submit" className="btn btn-primary" disabled={create.isPending}>
            {t(`${PREFIX}.keys.create`)}
          </button>
        </div>
      </form>
      {fehler && (
        <p className="text-sm t-alert m-0" role="alert">
          {fehlerText(t, fehler, PREFIX)}
        </p>
      )}
    </Abschnitt>
  );
}

// ---------------------------------------------------------------------------
// Seite
// ---------------------------------------------------------------------------

export function OrganisationSeite() {
  const { t } = useTranslation();
  const staff = useSession().data?.staff;
  const organisation = staff?.organisation;
  if (!staff || !organisation) {
    return <p className="t-mute">{t(`${PREFIX}.none`)}</p>;
  }
  const admin = organisation.role === "admin";
  return (
    <div className="flex flex-col gap-10">
      <Kopf eyebrow={t(`${PREFIX}.eyebrow`)} titel={organisation.display_name}>
        <p>{t(admin ? `${PREFIX}.introAdmin` : `${PREFIX}.introMember`)}</p>
      </Kopf>
      <Verbrauch />
      {admin && <Mitglieder selbst={staff.id} />}
      {admin && <Erscheinungsbild />}
      {admin && <ApiSchluessel />}
    </div>
  );
}
