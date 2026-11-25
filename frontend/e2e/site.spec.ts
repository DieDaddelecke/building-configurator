import { expect, test } from "@playwright/test";

import { waehleTreillieres } from "./gemeinde";

// Modul G1, Hauptpfad (Plan 4.1 Kriterium 2). Voraussetzungen wie in platform.spec.ts, zusätzlich der
// Kataster-Ausschnitt Treillières aus backend/tests/fixtures/site:
//   docker compose cp backend/tests/fixtures/site api:/tmp/site-fixtures
//   docker compose exec api python -m app.cli cadastre-import --from-dir /tmp/site-fixtures --release e2e --force

test.describe.serial("Grundstück (G1)", () => {
  test("ops schaltet die Grundstückswahl frei", async ({ page }) => {
    await page.goto("/buero");
    await page.getByRole("link", { name: "Anmelden" }).click();
    await expect(page.getByRole("heading", { name: "Willkommen" })).toBeVisible();
    const csrf = (await page.context().cookies()).find((c) => c.name === "emprise_csrf")?.value ?? "";
    const response = await page.request.put("/api/v1/admin/flags/site_selection", {
      data: { description: "G1 Ende-zu-Ende", enabled_for_all: true },
      headers: { "X-CSRF-Token": csrf },
    });
    expect(response.status()).toBe(200);
  });

  test("Kunde wählt eine Parzelle über die Nummer, prüft und korrigiert das Grundstück", async ({ page }) => {
    const errors: string[] = [];
    page.on("console", (msg) => {
      // Die Abfrage des noch nicht gebildeten Grundstücks antwortet erwartungsgemäß mit 404
      if (msg.type() === "error" && !msg.text().includes("404")) errors.push(msg.text());
    });

    await page.goto("/grundstueck");
    await expect(page.getByRole("heading", { name: "Wählen Sie Ihre Parzelle" })).toBeVisible();

    await page.getByText("Parzellennummer eingeben").click();
    await waehleTreillieres(page);
    await page.getByLabel("Sektion").fill("AD");
    await page.getByLabel("Nummer").fill("65");
    await page.getByRole("button", { name: "Parzelle suchen" }).click();
    await expect(page.getByRole("button", { name: /^AD 65/ })).toHaveAttribute("aria-pressed", "true");

    await page.getByRole("button", { name: "Grundstück übernehmen" }).click();
    await expect(page.getByRole("heading", { name: "Ihr Grundstück" })).toBeVisible();

    const table = page.getByRole("table", { name: "Grenzen des Grundstücks" });
    await expect(table.getByRole("row")).toHaveCount(5);
    await expect(table.getByText("Rue des chênes")).toBeVisible();
    await expect(table.getByText("Hintere Grenze")).toBeVisible();

    const rearRow = table.getByRole("row").filter({ hasText: "Hintere Grenze" });
    await rearRow.getByRole("combobox").selectOption({ label: "Straße" });
    await expect(page.getByRole("status").filter({ hasText: "nicht verbindlich" })).toBeVisible();
    await expect(table.getByText("Ihre Angabe")).toBeVisible();

    expect(errors, "keine Konsolenfehler, insbesondere keine CSP-Verstöße").toEqual([]);
  });
});
