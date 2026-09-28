import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, expect, it, vi } from "vitest";

import type { ModelOptionOut, RulesModelOut } from "../api/rules";
import i18n from "../i18n";
import { ModellWahl } from "./ModellWahl";

const state = vi.hoisted(() => ({
  model: null as RulesModelOut | null,
  models: [] as ModelOptionOut[],
  modelsError: false,
  mutate: vi.fn(),
}));

vi.mock("../api/rules", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../api/rules")>()),
  useRulesModel: () => ({ data: state.model }),
  useRulesModels: () => ({
    data: state.modelsError ? undefined : state.models,
    isPending: false,
    isError: state.modelsError,
  }),
  useSetRulesModel: () => ({ mutate: state.mutate, isPending: false, error: null }),
}));

const vorgabe: RulesModelOut = {
  model: "anthropic/claude-opus-5",
  source: "default",
  default_model: "anthropic/claude-opus-5",
  price_input_per_mtok: 5,
  price_output_per_mtok: 25,
  updated_at: null,
  input: "pdf",
  configured: true,
  month_cost_usd: 1.5,
  budget_month_usd: 20,
};

const option = (id: string, name: string, input: number, output: number, readsPdf = true): ModelOptionOut => ({
  id,
  name,
  price_input_per_mtok: input,
  price_output_per_mtok: output,
  context_length: 1_000_000,
  reads_pdf: readsPdf,
});

beforeEach(async () => {
  await i18n.changeLanguage("de");
  state.model = vorgabe;
  state.modelsError = false;
  state.models = [
    option("anthropic/claude-opus-5", "Anthropic: Claude Opus 5", 5, 25),
    option("anthropic/claude-opus-5.5", "Anthropic: Claude Opus 5.5", 4, 20),
    option("google/gemini-3.5-flash", "Google: Gemini 3.5 Flash", 1.5, 9),
    option("deepseek/deepseek-v4-flash-0731", "DeepSeek: V4 Flash", 0.021, 0.32, false),
  ];
  state.mutate.mockReset();
});

it("zeigt das Modell mit Preisen und Kosten; ohne Rolle gibt es nichts zu ändern", () => {
  render(<ModellWahl darfAendern={false} />);
  expect(screen.getByTestId("ki-modell")).toHaveTextContent("anthropic/claude-opus-5");
  expect(screen.getByText("Vorgabe")).toBeInTheDocument();
  expect(screen.getByText(/5,00\s\$ Eingabe · 25,00\s\$ Ausgabe je Mio. Token/)).toBeInTheDocument();
  expect(screen.getByText(/diesen Monat: 1,50\s\$ von 20,00\s\$/)).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Ändern" })).not.toBeInTheDocument();
});

it("wählt im Dialog ein anderes Modell für alle künftigen Auswertungen", async () => {
  render(<ModellWahl darfAendern />);
  await userEvent.click(screen.getByRole("button", { name: "Ändern" }));
  const dialog = screen.getByRole("dialog", { name: "KI-Modell wählen" });
  expect(within(dialog).getAllByRole("radio")).toHaveLength(4);
  // Das eingestellte Modell ist gewählt; ohne andere Wahl gibt es nichts zu übernehmen
  expect(within(dialog).getByRole("radio", { name: /Claude Opus 5\s*eingestellt\s*Vorgabe/ })).toBeChecked();
  expect(within(dialog).getByRole("button", { name: "Übernehmen" })).toBeDisabled();

  await userEvent.type(within(dialog).getByLabelText("Modell suchen"), "5.5");
  expect(within(dialog).getAllByRole("radio")).toHaveLength(1);
  await userEvent.click(within(dialog).getByRole("radio", { name: /Claude Opus 5\.5/ }));
  await userEvent.click(within(dialog).getByRole("button", { name: "Übernehmen" }));
  expect(state.mutate).toHaveBeenCalledWith("anthropic/claude-opus-5.5", expect.anything());
});

it("warnt bei anderen Anbietern und schließt mit Escape", async () => {
  render(<ModellWahl darfAendern />);
  await userEvent.click(screen.getByRole("button", { name: "Ändern" }));
  const hinweis = screen.getByText(/auf Claude-Modelle von Anthropic abgestimmt/);
  expect(hinweis).toHaveClass("t-mute");
  await userEvent.click(screen.getByRole("radio", { name: /Gemini/ }));
  expect(hinweis).toHaveClass("t-warn");
  await userEvent.keyboard("{Escape}");
  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  expect(state.mutate).not.toHaveBeenCalled();
});

it("stellt die Vorgabe auch ohne Liste von OpenRouter wieder her", async () => {
  state.model = { ...vorgabe, model: "google/gemini-3.5-flash", source: "setting", updated_at: "2026-09-28T18:00:00Z" };
  state.modelsError = true;
  render(<ModellWahl darfAendern />);
  expect(screen.queryByText("Vorgabe")).not.toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Ändern" }));
  expect(screen.getByRole("alert")).toHaveTextContent("gerade nicht abrufbar");
  await userEvent.click(screen.getByRole("button", { name: "Vorgabe wiederherstellen (anthropic/claude-opus-5)" }));
  expect(state.mutate).toHaveBeenCalledWith("anthropic/claude-opus-5", expect.anything());
});

it("sagt, dass ein Modell ohne PDF-Eingabe den Text der Seiten bekommt", async () => {
  state.model = { ...vorgabe, model: "deepseek/deepseek-v4-flash-0731", source: "setting", input: "text" };
  render(<ModellWahl darfAendern />);
  expect(screen.getByText("liest Text statt PDF")).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Ändern" }));
  const dialog = screen.getByRole("dialog");
  expect(within(dialog).getByText(/bekommt den Text der Seiten/)).toHaveClass("t-warn");
  await userEvent.click(within(dialog).getByRole("radio", { name: /Claude Opus 5\.5/ }));
  expect(within(dialog).queryByText(/bekommt den Text der Seiten/)).not.toBeInTheDocument();
});

it("nennt einen fehlenden Schlüssel", () => {
  state.model = { ...vorgabe, configured: false };
  render(<ModellWahl darfAendern />);
  expect(screen.getByText(/Kein Schlüssel für OpenRouter/)).toBeInTheDocument();
});
