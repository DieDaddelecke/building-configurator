import { beforeEach, expect, it } from "vitest";

import type { EnvelopeOut } from "../api/envelope";
import fixture from "../envelope/__fixtures__/envelope-ad0065.json";
import i18n from "../i18n";
import { aussagen, statement } from "./abstand";

const envelope = fixture as unknown as EnvelopeOut;
const t = i18n.t.bind(i18n);
const heights = envelope.parts[0]!.heights;
const setback = envelope.edges[0]!.setbacks[0]!;

beforeEach(async () => {
  await i18n.changeLanguage("de");
});

it("nennt Grenze und Mindestabstand im Klartext", () => {
  const [side] = aussagen(envelope.edges[0]!, envelope.parts, t, "de");
  expect(side!.text).toBe("auf der Grenze zulässig, sonst mindestens 3,00 m");
  const [street] = aussagen(envelope.edges[3]!, envelope.parts, t, "de");
  expect(street!.text).toBe("zwischen 5,00 m und 20,00 m (ganzer Baukörper im Band)");
});

it("rechnet einen höhenabhängigen Abstand mit der Höhe der Zone vor", () => {
  const factor = { ...setback, params: { min_m: 3, height_factor: 0.5, height_basis: "eave", allow_on_boundary: false } };
  expect(statement(factor, heights, t, "de")).toBe("H/2 (Traufhöhe), mindestens 3,00 m – bei 7,00 m Höhe also 3,50 m");
  expect(statement(factor, { ...heights, eave_m: null, ridge_m: null }, t, "de")).toBe(
    "H/2 (Traufhöhe), mindestens 3,00 m – Höhe nicht ermittelt",
  );
  const onBoundary = { ...setback, params: { min_m: 4, allow_on_boundary: true, on_boundary_max_height_m: 3.5 } };
  expect(statement(onBoundary, heights, t, "de")).toBe(
    "auf der Grenze zulässig bis 3,50 m Höhe, sonst mindestens 4,00 m",
  );
});

it("sagt nicht geregelt und nicht ermittelt, statt zu schätzen", () => {
  expect(statement({ ...setback, status: "not_regulated", params: {} }, heights, t, "de")).toBe(
    "nicht geregelt – kein Mindestabstand",
  );
  expect(statement({ ...setback, status: "unknown", params: {} }, heights, t, "de")).toBe("nicht ermittelt");
});

it("spricht Französisch", async () => {
  await i18n.changeLanguage("fr");
  const [side] = aussagen(envelope.edges[0]!, envelope.parts, t, "fr");
  expect(side!.text).toBe("implantation en limite autorisée, sinon au moins 3,00 m");
});
