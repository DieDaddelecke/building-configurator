import { expect, test } from "@playwright/test";

// Modul G2, Hauptpfad (Plan 4.1 Kriterium 2): Regeln des Grundstücks als Simulation. Voraussetzungen wie in
// site.spec.ts, zusätzlich Planstand und aufgezeichnete Auswertung der Zone Uh (ohne Claude API):
//   docker compose cp backend/tests api:/tmp/tests
//   docker compose exec -T -e EMPRISE_ANTHROPIC_API_KEY=e2e-ohne-aufruf -e PYTHONPATH=/tmp api python -m tests.e2e_seed_rules

test.describe.serial("Regeln als Simulation (G2)", () => {
  test("ops schaltet Grundstückswahl und Simulation frei", async ({ page }) => {
    await page.goto("/buero");
    await page.getByRole("link", { name: "Anmelden" }).click();
    await expect(page.getByRole("heading", { name: "Willkommen" })).toBeVisible();
    const csrf = (await page.context().cookies()).find((c) => c.name === "emprise_csrf")?.value ?? "";
    for (const key of ["site_selection", "rules_simulation"]) {
      const response = await page.request.put(`/api/v1/admin/flags/${key}`, {
        data: { description: "G2 Ende-zu-Ende", enabled_for_all: true },
        headers: { "X-CSRF-Token": csrf },
      });
      expect(response.status()).toBe(200);
    }
    await page.getByRole("link", { name: "Regelwerke" }).first().click();
    await expect(page.getByRole("heading", { name: "Regelwerke" })).toBeVisible();
    await expect(page.getByRole("link", { name: "Uh", exact: true })).toBeVisible();
  });

  test("Kunde sieht die Regeln seines Grundstücks mit Quelle und Kennzeichnung", async ({ page }) => {
    const errors: string[] = [];
    page.on("console", (msg) => {
      if (msg.type() === "error" && !msg.text().includes("404")) errors.push(msg.text());
    });

    await page.goto("/grundstueck");
    await page.getByText("Parzellennummer eingeben").click();
    await page.getByLabel("Sektion").fill("AD");
    await page.getByLabel("Nummer").fill("65");
    await page.getByRole("button", { name: "Parzelle suchen" }).click();
    await page.getByRole("button", { name: "Grundstück übernehmen" }).click();

    await expect(page.getByRole("heading", { name: "Regeln des Bebauungsplans" })).toBeVisible();
    await expect(page.getByRole("note")).toContainText("Simulation – unverbindlich.");
    const table = page.getByRole("table", { name: "Regeln der Zone Uh" });
    const street = table.getByRole("row", { name: /^Abstand zur Straße 5–20 m/ });
    await expect(street).toBeVisible();
    // Kapitel-PDF des Ausschnitts (Seite 9) oder des vollständigen Planstands (Seite 97), je nachdem, wer zuerst importiert
    await expect(street.getByRole("link")).toHaveAttribute("href", /244400503_reglement_20260304\.pdf#page=(9|97)$/);
    await expect(table.getByRole("row", { name: /^Dach nicht ermittelt/ })).toBeVisible();
    await expect(page.getByText(/Certificat d'urbanisme/).first()).toBeVisible();

    expect(errors, "keine Konsolenfehler, insbesondere keine CSP-Verstöße").toEqual([]);
  });
});
