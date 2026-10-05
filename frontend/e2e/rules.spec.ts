import { expect, test } from "@playwright/test";

// Module G2 und G3, Hauptpfad (Plan 4.1 Kriterium 2): Regeln des Grundstücks als Simulation und der daraus
// abgeleitete Baurahmen. Voraussetzungen wie in site.spec.ts, zusätzlich Planstand und aufgezeichnete
// Auswertung der Zone Uh (ohne OpenRouter):
//   docker compose cp backend/tests api:/tmp/tests
//   docker compose exec -T -e EMPRISE_OPENROUTER_API_KEY=e2e-ohne-aufruf -e PYTHONPATH=/tmp api python -m tests.e2e_seed_rules

test.describe.serial("Regeln und Baurahmen als Simulation (G2, G3)", () => {
  test("ops schaltet Grundstückswahl, Simulation und Baurahmen frei", async ({ page }) => {
    await page.goto("/buero");
    await page.getByRole("link", { name: "Anmelden" }).click();
    await expect(page.getByRole("heading", { name: "Willkommen" })).toBeVisible();
    const csrf = (await page.context().cookies()).find((c) => c.name === "emprise_csrf")?.value ?? "";
    for (const key of ["site_selection", "rules_simulation", "envelope_simulation"]) {
      const response = await page.request.put(`/api/v1/admin/flags/${key}`, {
        data: { description: "G2/G3 Ende-zu-Ende", enabled_for_all: true },
        headers: { "X-CSRF-Token": csrf },
      });
      expect(response.status()).toBe(200);
    }
    await page.getByRole("link", { name: "Regelwerke" }).first().click();
    await expect(page.getByRole("heading", { name: "Regelwerke" })).toBeVisible();
    await expect(page.getByRole("link", { name: "Uh", exact: true })).toBeVisible();
  });

  test("Kunde sieht Baurahmen und Regeln mit Quelle und Kennzeichnung", async ({ page }) => {
    const errors: string[] = [];
    page.on("console", (msg) => {
      if (msg.type() === "error" && !msg.text().includes("404")) errors.push(msg.text());
    });

    await page.goto("/grundstueck");
    await page.getByText("Parzellennummer eingeben").click();
    // In CI gibt es nur Treillières; ein lokaler Stack kann weitere Gemeinden haben
    await page.getByLabel("Gemeinde").selectOption({ label: "TREILLIERES" });
    await page.getByLabel("Sektion").fill("AD");
    await page.getByLabel("Nummer").fill("65");
    await page.getByRole("button", { name: "Parzelle suchen" }).click();
    await page.getByRole("button", { name: "Grundstück übernehmen" }).click();

    // Baurahmen (G3): beide Auslegungen, Grenzwerte mit Quelle, Lageplan
    await expect(page.getByRole("heading", { name: "Was darf ich bauen?" })).toBeVisible();
    await expect(page.getByText("Simulation – unverbindlich.").first()).toBeVisible();
    const baurahmen = page.getByRole("table", { name: "Baurahmen der Zone Uh" });
    await expect(baurahmen.getByRole("row", { name: /^Höchste Grundfläche \d/ })).toBeVisible();
    // Zeilenname enthält auch den Straßennamen der Kante, deshalb der Abstand als Textprüfung
    await expect(baurahmen.getByRole("row", { name: /^Grenze zur Straße \d/ })).toContainText("5,00 m");
    await expect(page.getByRole("img", { name: /Lageplan mit bebaubarer Fläche/ })).toBeVisible();
    await expect(page.getByText("Bebaubar nach jeder Auslegung").first()).toBeVisible();

    // Regeln (G2) stehen als Herleitung darunter
    await page.getByText("Herleitung: Regeln mit Zitaten").click();
    await expect(page.getByRole("heading", { name: "Regeln des Bebauungsplans" })).toBeVisible();
    const table = page.getByRole("table", { name: "Regeln der Zone Uh" });
    const street = table.getByRole("row", { name: /^Abstand zur Straße 5–20 m/ });
    await expect(street).toBeVisible();
    // Kapitel-PDF des Ausschnitts (Seite 9) oder des vollständigen Planstands (Seite 97), je nachdem, wer zuerst importiert
    await expect(street.getByRole("link")).toHaveAttribute("href", /244400503_reglement_20260304\.pdf#page=(9|97)$/);
    await expect(table.getByRole("row", { name: /^Dach nicht ermittelt/ })).toBeVisible();
    await expect(page.getByText(/Certificat d'urbanisme/).first()).toBeVisible();

    // Steckbrief: der Worker setzt das PDF, ein erneuter Klick liefert es (dasselbe Projekt wie oben,
    // deshalb im selben Test: jeder Test startet mit einem leeren Cookie und damit ohne Grundstück)
    await page.getByRole("button", { name: "Steckbrief als PDF" }).click();
    const link = page.getByRole("link", { name: "Steckbrief öffnen" });
    await expect(link).toBeVisible({ timeout: 25_000 });
    const href = await link.getAttribute("href");
    const pdf = await page.request.get(href ?? "");
    expect(pdf.status()).toBe(200);
    expect(pdf.headers()["content-type"]).toContain("application/pdf");

    expect(errors, "keine Konsolenfehler, insbesondere keine CSP-Verstöße").toEqual([]);
  });
});
