// Nachschlagen in Template und Katalog: Elemente mit ihrem Kontext für Ausdrücke (P 8.4) und Katalogeinträge
// nach Kennung. Fehlende Verweise sind ModelErrors; die Kompatibilitätsprüfung meldet sie vorher (P 2.1 Nr. 5).
import type {
  HouseCatalog,
  HouseDoorType,
  HouseMaterial,
  HouseOptionValue,
  HouseRoofType,
  HouseRoomType,
  HouseSlot,
  HouseTemplate,
  HouseWallLayer,
  HouseWallProfile,
  HouseWindowType,
} from "./contract.gen.ts";
import type { ModelErrorCode } from "./codes.ts";
import { ModelError } from "./errors.ts";

export type ElementKind = "envelope_segment" | "interior_wall" | "opening" | "roof" | "room" | "building";

export interface ModelElement {
  readonly id: string;
  readonly elementKind: ElementKind;
  /** Räume am Element: bei Öffnungen und Innenwänden die angrenzenden, bei Räumen der Raum selbst. */
  readonly roomIds: readonly string[];
  /** Kontext `element.*` der Ausdrücke. */
  readonly context: Readonly<Record<string, unknown>>;
}

function byId<T extends { readonly id: string }>(items: readonly T[]): ReadonlyMap<string, T> {
  return new Map(items.map((item) => [item.id, item]));
}

export class CatalogIndex {
  readonly catalog: HouseCatalog;
  readonly materials: ReadonlyMap<string, HouseMaterial>;
  readonly layers: ReadonlyMap<string, HouseWallLayer>;
  readonly profiles: ReadonlyMap<string, HouseWallProfile>;
  readonly windowTypes: ReadonlyMap<string, HouseWindowType>;
  readonly doorTypes: ReadonlyMap<string, HouseDoorType>;
  readonly roofTypes: ReadonlyMap<string, HouseRoofType>;
  readonly roomTypes: ReadonlyMap<string, HouseRoomType>;
  readonly slots: readonly HouseSlot[];
  readonly options: ReadonlyMap<string, HouseOptionValue>;
  readonly optionsBySlot: ReadonlyMap<string, readonly HouseOptionValue[]>;

  constructor(catalog: HouseCatalog) {
    this.catalog = catalog;
    this.materials = byId(catalog.materials);
    this.layers = byId(catalog.wall_layers);
    this.profiles = byId(catalog.wall_profiles);
    this.windowTypes = byId(catalog.window_types);
    this.doorTypes = byId(catalog.door_types);
    this.roofTypes = byId(catalog.roof_types);
    this.roomTypes = byId(catalog.room_types);
    this.slots = [...catalog.slots].sort((a, b) => a.sort_order - b.sort_order || a.id.localeCompare(b.id));
    this.options = byId(catalog.option_values);
    const bySlot = new Map<string, HouseOptionValue[]>();
    for (const option of [...catalog.option_values].sort((a, b) => a.sort_order - b.sort_order)) {
      bySlot.set(option.slot_id, [...(bySlot.get(option.slot_id) ?? []), option]);
    }
    this.optionsBySlot = bySlot;
  }

  get<T>(map: ReadonlyMap<string, T>, id: string, code: ModelErrorCode): T {
    const item = map.get(id);
    if (item === undefined) throw new ModelError(code, { id });
    return item;
  }
}

export class TemplateIndex {
  readonly template: HouseTemplate;
  readonly elements: readonly ModelElement[];
  readonly elementsById: ReadonlyMap<string, ModelElement>;

  constructor(template: HouseTemplate, catalog: CatalogIndex) {
    this.template = template;
    const roomType = new Map(template.rooms.map((room) => [room.id, room.room_type_id]));
    const rooms = (ids: readonly string[]) =>
      ids.map((id) => {
        const type = roomType.get(id);
        if (type === undefined) throw new ModelError("room_unknown", { id });
        return { id, room_type_id: type, override_priority: catalog.roomTypes.get(type)?.override_priority ?? 0 };
      });
    const hostKind = new Map<string, string>();
    const elements: ModelElement[] = [];
    for (const loop of template.envelope) {
      for (const segment of loop.segments) {
        hostKind.set(segment.id, "envelope_segment");
        elements.push({
          id: segment.id,
          elementKind: "envelope_segment",
          roomIds: [],
          context: { id: segment.id, element_kind: "envelope_segment", level_id: loop.level_id, facade_role: segment.facade_role },
        });
      }
    }
    for (const wall of template.interior_walls) {
      hostKind.set(wall.id, "interior_wall");
      elements.push({
        id: wall.id,
        elementKind: "interior_wall",
        roomIds: wall.adjacent_room_ids,
        context: {
          id: wall.id,
          element_kind: "interior_wall",
          level_id: wall.level_id,
          thickness: wall.thickness,
          adjacent_rooms: rooms(wall.adjacent_room_ids),
        },
      });
    }
    for (const opening of template.openings) {
      if (hostKind.get(opening.host_id) !== opening.host_kind) {
        throw new ModelError("host_unknown", { id: opening.id, host: opening.host_id });
      }
      elements.push({
        id: opening.id,
        elementKind: "opening",
        roomIds: opening.adjacent_room_ids,
        context: {
          id: opening.id,
          element_kind: "opening",
          kind: opening.kind,
          host_kind: opening.host_kind,
          host_id: opening.host_id,
          entrance: opening.id === template.entrance_opening_id,
          garage_door: opening.id === template.garage_door_opening_id,
          adjacent_rooms: rooms(opening.adjacent_room_ids),
        },
      });
    }
    for (const room of template.rooms) {
      elements.push({
        id: room.id,
        elementKind: "room",
        roomIds: [room.id],
        context: { id: room.id, element_kind: "room", level_id: room.level_id, room_type_id: room.room_type_id },
      });
    }
    elements.push({ id: "roof", elementKind: "roof", roomIds: [], context: { id: "roof", element_kind: "roof" } });
    elements.push({ id: "building", elementKind: "building", roomIds: [], context: { id: "building", element_kind: "building" } });
    this.elements = elements;
    this.elementsById = new Map(elements.map((element) => [element.id, element]));
  }

}
