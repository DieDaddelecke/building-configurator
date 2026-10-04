// Semantische Grundriss-Tests mit dem Demohaus (P 20.1.1).
import { describe, expect, it } from "vitest";
import { areaSquareMetres, checkCompatibility, deriveModel, evaluate, polygonDefect, toUnits, type HouseCatalog, type HouseTemplate } from "../src/index.ts";
import { catalog, configuration, template } from "./demo-house.ts";

const roomTypes = new Set(catalog.room_types.map((t) => t.id));
const rooms = new Map(template.rooms.map((r) => [r.id, r]));
const units = (points: readonly { x: number; y: number }[]) => points.map((p) => ({ x: toUnits(p.x), y: toUnits(p.y) }));

describe("Grundriss des Demohauses", () => {
  it("jeder Raum hat einen gültigen Raumtyp und eine geschlossene Geometrie", () => {
    for (const room of template.rooms) {
      expect(roomTypes.has(room.room_type_id), room.id).toBe(true);
      expect(polygonDefect(units(room.polygon)), room.id).toBeNull();
      expect(areaSquareMetres(units(room.polygon)), room.id).toBeGreaterThan(0);
    }
  });

  it("Raumflächen kommen nur aus der Raumgeometrie", () => {
    const sum = template.rooms.reduce((s, r) => s + areaSquareMetres(units(r.polygon)), 0);
    expect(evaluate({ template, catalog, configuration: configuration() }).facts.floor_area).toBeCloseTo(sum, 10);
    // Ein anderer Raumtyp ändert die Fläche nicht
    const retyped: HouseTemplate = { ...template, rooms: template.rooms.map((r) => ({ ...r, room_type_id: "corridor" })) };
    expect(evaluate({ template: retyped, catalog, configuration: configuration() }).facts.floor_area).toBeCloseTo(sum, 10);
  });

  it("jede Innenwand grenzt an 0–2 bekannte Räume", () => {
    for (const wall of template.interior_walls) {
      expect(wall.adjacent_room_ids.length, wall.id).toBeLessThanOrEqual(2);
      expect(wall.adjacent_room_ids.every((id) => rooms.has(id)), wall.id).toBe(true);
    }
  });

  it("Türen nennen ihre angrenzenden Räume", () => {
    const walls = new Map(template.interior_walls.map((w) => [w.id, w]));
    for (const door of template.openings.filter((o) => o.kind === "door")) {
      if (door.host_kind === "interior_wall") {
        expect([...door.adjacent_room_ids].sort(), door.id).toEqual([...walls.get(door.host_id)!.adjacent_room_ids].sort());
      } else {
        expect(door.adjacent_room_ids, door.id).toEqual(["room-hall"]);
      }
    }
  });

  it("Öffnungen liegen in ihrem Host und überlappen nicht, bei jedem Profil und Fenstertyp", () => {
    for (const wall of ["wall.standard", "wall.brick", "wall.wood"]) {
      for (const window of ["window.standard", "window.floor_length"]) {
        const evaluation = evaluate({ template, catalog, configuration: configuration({ wall_profile: { value: wall }, window_type: { value: window } }) });
        expect(evaluation.rule_results, `${wall} ${window}`).toEqual([]);
      }
    }
  });

  it("Öffnungen außerhalb des Hosts oder übereinander sperren", () => {
    const moved: HouseTemplate = {
      ...template,
      openings: template.openings.map((o) =>
        o.id === "win-child" ? { ...o, offset_along_host: 11.7 } : o.id === "win-bedroom" ? { ...o, offset_along_host: 3.3 } : o,
      ),
    };
    const evaluation = evaluate({ template: moved, catalog, configuration: configuration() });
    expect(evaluation.status).toBe("blocked");
    expect(evaluation.rule_results.map((r) => [r.code, r.element_ids])).toEqual([
      ["opening_outside_host", ["win-child", "seg-south"]],
      ["openings_overlap", ["win-living-south", "win-bedroom"]],
    ]);
    // Zu hohe Fenster stoßen an die Decke
    const tall: HouseCatalog = { ...catalog, window_types: catalog.window_types.map((w) => ({ ...w, head_height: 2.6 })) };
    expect(evaluate({ template, catalog: tall, configuration: configuration() }).rule_results.map((r) => r.code)).toContain("opening_above_ceiling");
  });

  it("ein Wechsel des Außenwandprofils ändert weder Räume noch Innenwände", () => {
    const frozen = structuredClone(template);
    const models = ["wall.standard", "wall.brick", "wall.wood"].map((wall) =>
      deriveModel({ template, catalog, configuration: configuration({ wall_profile: { value: wall } }) }),
    );
    for (const model of models.slice(1)) {
      expect(model.rooms).toEqual(models[0]!.rooms);
      expect(model.openings.filter((o) => o.hostKind === "interior_wall")).toEqual(models[0]!.openings.filter((o) => o.hostKind === "interior_wall"));
    }
    expect(template).toEqual(frozen);
  });

  it("Darstellungsschlüssel ändern weder Geometrie noch Mengen, Preis oder Regeln", () => {
    const restyled: HouseCatalog = {
      ...catalog,
      materials: catalog.materials.map((m) => ({ ...m, render_key: `${m.render_key}_alt` })),
      window_types: catalog.window_types.map((w) => ({ ...w, render_key: "other" })),
      roof_types: catalog.roof_types.map((r) => ({ ...r, render_key: "other" })),
      room_types: catalog.room_types.map((t) => ({ ...t, display_key: "neutral" })),
    };
    const variants: NonNullable<Parameters<typeof configuration>[0]>[] = [{}, { wall_profile: { value: "wall.brick" }, window_type: { value: "window.floor_length" } }];
    for (const selections of variants) {
      const config = configuration(selections);
      expect(evaluate({ template, catalog: restyled, configuration: config })).toEqual(evaluate({ template, catalog, configuration: config }));
      expect(deriveModel({ template, catalog: restyled, configuration: config }).rooms).toEqual(deriveModel({ template, catalog, configuration: config }).rooms);
    }
    expect(checkCompatibility({ template, catalog: restyled }).supported).toBe(true);
  });
});
