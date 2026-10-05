import { expect, test } from "@playwright/test";

// Hausmodell HM4/HM5, Kundenweg bis Speichern (docs/PLAN_HAUSMODELL.md 6): Demohaus auf AD 65 wählen, Fassade ändern,
// speichern. Der Server rechnet denselben Preis wie der Kern in Chromium (`price_match`). Voraussetzungen wie in
// rules.spec.ts, zusätzlich die Demohäuser ohne IFC:
//   docker compose cp packages/domain/seed/demo-house api:/tmp/demo-house
//   docker compose exec -T -e PYTHONPATH=/tmp api python -m tests.e2e_seed_house /tmp/demo-house

test.describe.serial("Hausmodell: Kundenweg (HM4)", () => {
  test("ops schaltet Grundstückswahl, Simulation, Baurahmen und Hausmodell frei", async ({ page }) => {
    await page.goto("/buero");
    await page.getByRole("link", { name: "Anmelden" }).click();
    await expect(page.getByRole("heading", { name: "Willkommen" })).toBeVisible();
    const csrf = (await page.context().cookies()).find((c) => c.name === "emprise_csrf")?.value ?? "";
    for (const key of ["site_selection", "rules_simulation", "envelope_simulation", "house_model"]) {
      const response = await page.request.put(`/api/v1/admin/flags/${key}`, {
        data: { description: "HM4 Ende-zu-Ende", enabled_for_all: true },
        headers: { "X-CSRF-Token": csrf },
      });
      expect(response.status()).toBe(200);
    }
  });

  test("Kunde wählt das Demohaus auf AD 65, ändert die Fassade und speichert", async ({ page }) => {
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

    await page.getByRole("link", { name: "Haus konfigurieren" }).click();
    await expect(page.getByRole("heading", { name: "Ihr Haus konfigurieren" })).toBeVisible();
    const card = page.getByTestId("haustyp-demo_house");
    await expect(card.getByText("Auf Ihrem Grundstück möglich")).toBeVisible();
    await expect(card.getByTestId("ab-preis")).toHaveText(/^ab ca\. \d{1,3}(\.\d{3})+ €$/);
    // HM5: das R+1 mit Satteldach steht als zweiter Typ zur Wahl, mit Geschossen und Neigung
    const r1 = page.getByTestId("haustyp-demo_house_r1");
    await expect(r1.getByText("R+1")).toBeVisible();
    await expect(r1.getByText("Satteldach, 35°")).toBeVisible();

    await card.getByRole("button", { name: "Diesen Typ wählen" }).click();
    await expect(page.getByTestId("haus-name")).toHaveText("Demohaus");
    await expect(page.getByTestId("haus")).toBeVisible();
    await expect(page.getByTestId("speicherstand")).toHaveText("Gespeichert");

    const saved = page.waitForResponse(
      (response) => response.url().endsWith("/house/configuration") && response.request().method() === "PATCH",
    );
    const brick = page.getByTestId("slot-wall_profile").getByRole("radio", { name: /Vorgehängte Ziegelfassade/ });
    await brick.check();
    const response = await saved;
    expect(response.status()).toBe(200);
    const body = await response.json();
    // Server- gleich Browserpreis: der Kern in Chromium und in `engine` rechnen auf den Cent gleich (L5)
    expect(body.price_match).toBe(true);
    expect(body.configuration.selections.wall_profile.value.option_value_id).toBe("wall.brick");

    const amount = `ca. ${new Intl.NumberFormat("de-DE").format(body.price.gross_rounded)} €`;
    await expect(page.getByTestId("speicherstand")).toHaveText("Gespeichert");
    await expect(page.getByTestId("gesamtpreis")).toContainText(amount);
    await expect(page.getByTestId("preisabweichung")).toHaveCount(0);

    // Gespeichert: nach dem Neuladen derselbe Stand
    await page.reload();
    await expect(page.getByTestId("slot-wall_profile").getByRole("radio", { name: /Vorgehängte Ziegelfassade/ })).toBeChecked();
    await expect(page.getByTestId("gesamtpreis")).toContainText(amount);

    expect(errors, "keine Konsolenfehler, insbesondere keine CSP-Verstöße").toEqual([]);
  });
});
