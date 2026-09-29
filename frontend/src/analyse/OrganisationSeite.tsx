/**
 * Seite „Organisation“ (AN6, docs/PLAN_AN6_MANDANTEN.md 3.7): Name und Mitglieder, verwaltet von der Rolle
 * `admin`. Rechte prüft der Server; die Seite blendet nur aus, was ein Mitglied nicht darf. Erscheinungsbild,
 * Verbrauch und API-Schlüssel sind seit dem 29.09.2026 zurückgebaut (REFACTORING_PLAN S8).
 */

import { useId, useState, type FormEvent, type ReactNode } from "react";
import { useTranslation } from "react-i18next";

import {
  useAddMember,
  useChangeMemberRole,
  useMembers,
  useOrganisation,
  useRemoveMember,
  useUpdateOrganisation,
  type OrganisationOut,
  type OrganisationRole,
} from "../api/organisation";
import { useSession } from "../api/session";
import { Kopf } from "../components/Kopf";
import { fehlerText } from "./fehler";

const PREFIX = "analyse.organisation";
const ROLLEN: readonly OrganisationRole[] = ["member", "admin"];

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
// Name
// ---------------------------------------------------------------------------

function NameFormular({ org }: { org: OrganisationOut }) {
  const { t } = useTranslation();
  const update = useUpdateOrganisation();
  const [name, setName] = useState(org.display_name);
  const id = useId();

  const speichern = (event: FormEvent) => {
    event.preventDefault();
    update.mutate({ display_name: name.trim() || org.display_name });
  };

  return (
    <form className="flex flex-col gap-3 sm:flex-row sm:items-end" onSubmit={speichern}>
      <div className="flex flex-col gap-1 flex-1 min-w-0">
        <label htmlFor={id} className="text-sm t-mute">
          {t(`${PREFIX}.name.label`)}
        </label>
        <input
          id={id}
          className="field"
          required
          minLength={2}
          maxLength={200}
          value={name}
          onChange={(event) => setName(event.target.value)}
        />
      </div>
      <button type="submit" className="btn btn-primary" disabled={update.isPending}>
        {t(`${PREFIX}.name.save`)}
      </button>
      {update.isSuccess && (
        <span className="text-sm t-mute" role="status">
          {t(`${PREFIX}.name.saved`)}
        </span>
      )}
      {update.error && (
        <p className="text-sm t-alert m-0" role="alert">
          {fehlerText(t, update.error, PREFIX)}
        </p>
      )}
    </form>
  );
}

function Name() {
  const { t } = useTranslation();
  const organisation = useOrganisation();
  return (
    <Abschnitt id="org-name" titel={t(`${PREFIX}.name.title`)}>
      {organisation.isPending && <p className="t-mute m-0">{t("loading")}</p>}
      {organisation.isError && <p className="t-alert m-0">{t("error.generic")}</p>}
      {organisation.data && <NameFormular org={organisation.data} />}
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
      {admin && <Name />}
      {admin && <Mitglieder selbst={staff.id} />}
    </div>
  );
}
