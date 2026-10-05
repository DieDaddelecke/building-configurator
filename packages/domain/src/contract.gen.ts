// Erzeugt von scripts/contract-types.ts aus backend/openapi.json; nicht von Hand ändern.
// Quelle: backend/app/house/contract.py (docs/PLAN_HAUSMODELL.md 3.4).
export type paths = Record<string, never>;
export type webhooks = Record<string, never>;
export interface components {
    schemas: {
        /** HouseBearing */
        readonly HouseBearing: {
            /**
             * Kind
             * @enum {string}
             */
            readonly kind: "foundation_ledge" | "brackets";
            /** Supported Layer Ids */
            readonly supported_layer_ids: readonly string[];
        };
        /** HouseBinaryExpr */
        readonly HouseBinaryExpr: {
            readonly left: components["schemas"]["HouseExpr"];
            /**
             * Op
             * @enum {string}
             */
            readonly op: "eq" | "neq" | "gt" | "gte" | "lt" | "lte" | "in" | "not_in" | "contains" | "add" | "sub" | "mul" | "div";
            readonly right: components["schemas"]["HouseExpr"];
        };
        /**
         * HouseCandidate
         * @description Vorschau eines Werts vor der Wahl (P 8.2 `evaluateCandidates`); bei der Drehung des Dachs je Zahl.
         */
        readonly HouseCandidate: {
            /** Available Count */
            readonly available_count: number;
            /** Number */
            readonly number: number | null;
            /** Option Value Id */
            readonly option_value_id: string | null;
            /** Price Delta */
            readonly price_delta: number;
            /** Rule Results */
            readonly rule_results: readonly components["schemas"]["HouseRuleResult"][];
            /**
             * Status
             * @enum {string}
             */
            readonly status: "valid" | "valid_with_warnings" | "with_deviations" | "blocked";
            /** Target Count */
            readonly target_count: number;
            readonly unavailable_reason: components["schemas"]["HouseText"] | null;
        };
        /** HouseCandidatesRequest */
        readonly HouseCandidatesRequest: {
            /** Element Id */
            readonly element_id: string | null;
            /** Slot Id */
            readonly slot_id: string;
        };
        /** HouseCarportFacts */
        readonly HouseCarportFacts: {
            /** Depth */
            readonly depth: number;
            /** Height */
            readonly height: number;
            /** Spaces */
            readonly spaces: number;
            /** Type Id */
            readonly type_id: string;
            /** Width */
            readonly width: number;
        };
        /**
         * HouseCarportType
         * @description Carport (Ergänzung 7): Maße für Preis und Prüfung; Lage und Zufahrt rechnet Python.
         */
        readonly HouseCarportType: {
            /** Depth */
            readonly depth: number;
            /** Height */
            readonly height: number;
            /** Id */
            readonly id: string;
            readonly name: components["schemas"]["HouseText"];
            /** Render Key */
            readonly render_key: string;
            /** Spaces */
            readonly spaces: number;
            /** Width */
            readonly width: number;
        };
        /**
         * HouseCatalog
         * @description Katalogversion eines Markts: Bauteile, Slots, Werte, Regeln und Preise in einem Dokument (E-HM-8).
         */
        readonly HouseCatalog: {
            /** Carport Types */
            readonly carport_types: readonly components["schemas"]["HouseCarportType"][];
            /**
             * Currency
             * @constant
             */
            readonly currency: "EUR";
            /** Door Types */
            readonly door_types: readonly components["schemas"]["HouseDoorType"][];
            /** Ignored Zone Categories */
            readonly ignored_zone_categories: readonly string[];
            /** Lines */
            readonly lines: readonly components["schemas"]["HouseLine"][];
            /**
             * Market
             * @constant
             */
            readonly market: "FR";
            /** Materials */
            readonly materials: readonly components["schemas"]["HouseMaterial"][];
            /** Option Values */
            readonly option_values: readonly components["schemas"]["HouseOptionValue"][];
            readonly parameters: components["schemas"]["HouseCatalogParameters"];
            /** Price Entries */
            readonly price_entries: readonly components["schemas"]["HousePriceEntry"][];
            /** Pricing Rules */
            readonly pricing_rules: readonly components["schemas"]["HousePricingRule"][];
            /** Roof Shapes */
            readonly roof_shapes: readonly components["schemas"]["HouseRoofShape"][];
            /** Roof Types */
            readonly roof_types: readonly components["schemas"]["HouseRoofType"][];
            /** Room Types */
            readonly room_types: readonly components["schemas"]["HouseRoomType"][];
            /** Rules */
            readonly rules: readonly components["schemas"]["HouseRule"][];
            /**
             * Schema Version
             * @constant
             */
            readonly schema_version: 2;
            /** Slots */
            readonly slots: readonly components["schemas"]["HouseSlot"][];
            /** Terrace Types */
            readonly terrace_types: readonly components["schemas"]["HouseTerraceType"][];
            /** Vat Rate */
            readonly vat_rate: number;
            /** Wall Layers */
            readonly wall_layers: readonly components["schemas"]["HouseWallLayer"][];
            /** Wall Profiles */
            readonly wall_profiles: readonly components["schemas"]["HouseWallProfile"][];
            /** Window Types */
            readonly window_types: readonly components["schemas"]["HouseWindowType"][];
        };
        /** HouseCatalogParameters */
        readonly HouseCatalogParameters: {
            /** Opening Deduction Threshold */
            readonly opening_deduction_threshold: number;
            /** Parapet Min Upstand */
            readonly parapet_min_upstand: number;
            /** Surface Resistance Inside */
            readonly surface_resistance_inside: number;
            /** Surface Resistance Outside */
            readonly surface_resistance_outside: number;
        };
        /**
         * HouseCompatibility
         * @description Prüfung Template ↔ Katalog (P 2.1 Nr. 5); die Freigabe trifft danach ein Mensch.
         */
        readonly HouseCompatibility: {
            /** Domain Version */
            readonly domain_version: string;
            /** Issues */
            readonly issues: readonly components["schemas"]["HouseCompatibilityIssue"][];
            /** Supported */
            readonly supported: boolean;
        };
        /** HouseCompatibilityIssue */
        readonly HouseCompatibilityIssue: {
            /** Code */
            readonly code: string;
            /** Element Id */
            readonly element_id: string | null;
            /** Ref Id */
            readonly ref_id: string | null;
            /** Slot Id */
            readonly slot_id: string | null;
        };
        /** HouseCompatibilityRequest */
        readonly HouseCompatibilityRequest: {
            readonly catalog: components["schemas"]["HouseCatalog"];
            readonly template: components["schemas"]["HouseTemplate"];
        };
        /**
         * HouseConfiguration
         * @description Nur Auswahl: keine Geometrie, keine Mengen, keine Preise (P 2 Nr. 2).
         */
        readonly HouseConfiguration: {
            /** Selections */
            readonly selections: {
                readonly [key: string]: components["schemas"]["HouseSlotSelection"];
            };
        };
        /** HouseDoorType */
        readonly HouseDoorType: {
            /** Height */
            readonly height: number;
            /** Id */
            readonly id: string;
            readonly name: components["schemas"]["HouseText"];
            /** Render Key */
            readonly render_key: string;
            /** Width */
            readonly width: number;
        };
        /** HouseEdgePosition */
        readonly HouseEdgePosition: {
            /** Edge */
            readonly edge: number;
            /** Position */
            readonly position: number;
        };
        /** HouseEdgeRole */
        readonly HouseEdgeRole: {
            /** Edge */
            readonly edge: number;
            /**
             * Role
             * @enum {string}
             */
            readonly role: "street" | "garden" | "side_left" | "side_right";
        };
        /** HouseEnergy */
        readonly HouseEnergy: {
            /** Wall U Values */
            readonly wall_u_values: readonly components["schemas"]["HouseProfileUValue"][];
            /** Window Shares */
            readonly window_shares: readonly components["schemas"]["HouseWindowShare"][];
        };
        /** HouseEnvelopeLoop */
        readonly HouseEnvelopeLoop: {
            /** Inner Polygon */
            readonly inner_polygon: readonly components["schemas"]["HousePoint"][];
            /** Level Id */
            readonly level_id: string;
            /** Segments */
            readonly segments: readonly components["schemas"]["HouseEnvelopeSegment"][];
        };
        /**
         * HouseEnvelopeSegment
         * @description Kante `i` der Bezugskontur, von Punkt `i` zu Punkt `i + 1`.
         */
        readonly HouseEnvelopeSegment: {
            /** Facade Role */
            readonly facade_role: ("street" | "garden" | "side_left" | "side_right") | null;
            /** Id */
            readonly id: string;
            /** Source Ifc Guid */
            readonly source_ifc_guid: string | null;
        };
        /** HouseEvaluateRequest */
        readonly HouseEvaluateRequest: {
            readonly candidates: components["schemas"]["HouseCandidatesRequest"] | null;
            readonly catalog: components["schemas"]["HouseCatalog"];
            readonly configuration: components["schemas"]["HouseConfiguration"];
            readonly template: components["schemas"]["HouseTemplate"];
        };
        /** HouseEvaluation */
        readonly HouseEvaluation: {
            /** Candidates */
            readonly candidates: readonly components["schemas"]["HouseCandidate"][] | null;
            /** Domain Version */
            readonly domain_version: string;
            readonly energy: components["schemas"]["HouseEnergy"];
            readonly facts: components["schemas"]["HouseFacts"];
            /** Notes */
            readonly notes: readonly components["schemas"]["HouseResolutionNote"][];
            readonly price: components["schemas"]["HousePrice"];
            /** Quantities */
            readonly quantities: readonly components["schemas"]["HouseQuantity"][];
            /** Resolved */
            readonly resolved: readonly components["schemas"]["HouseResolvedValue"][];
            /** Rule Results */
            readonly rule_results: readonly components["schemas"]["HouseRuleResult"][];
            /**
             * Status
             * @enum {string}
             */
            readonly status: "valid" | "valid_with_warnings" | "with_deviations" | "blocked";
        };
        readonly HouseExpr: components["schemas"]["HousePathExpr"] | components["schemas"]["HouseBinaryExpr"] | components["schemas"]["HouseLogicExpr"] | components["schemas"]["HouseLiteral"] | readonly components["schemas"]["HouseLiteral"][];
        /**
         * HouseFacts
         * @description Hausbeschreibung für die Prüfung auf dem Grundstück in Python (3.1, E-HM-4); ersetzt `HouseType`.
         */
        readonly HouseFacts: {
            readonly carport: components["schemas"]["HouseCarportFacts"] | null;
            /** Eave Height */
            readonly eave_height: number;
            readonly entrance: components["schemas"]["HouseEdgePosition"] | null;
            /**
             * Facade Material Class
             * @enum {string}
             */
            readonly facade_material_class: "render" | "wood" | "brick" | "stone" | "concrete" | "metal" | "glass" | "slate" | "clay_tile" | "zinc" | "composite" | "vegetation" | "other";
            /** Facade Outline */
            readonly facade_outline: readonly components["schemas"]["HousePoint"][];
            /** Facade Roles */
            readonly facade_roles: readonly components["schemas"]["HouseEdgeRole"][];
            /** Floor Area */
            readonly floor_area: number;
            readonly garage_door: components["schemas"]["HouseEdgePosition"] | null;
            /** Ground Floor Offset */
            readonly ground_floor_offset: number;
            /** Projection Outline */
            readonly projection_outline: readonly components["schemas"]["HousePoint"][];
            /** Ridge Azimuth Deg */
            readonly ridge_azimuth_deg: number | null;
            /**
             * Roof Material Class
             * @enum {string}
             */
            readonly roof_material_class: "render" | "wood" | "brick" | "stone" | "concrete" | "metal" | "glass" | "slate" | "clay_tile" | "zinc" | "composite" | "vegetation" | "other";
            /**
             * Roof Shape
             * @enum {string}
             */
            readonly roof_shape: "flat" | "mono_pitch" | "gable" | "hip" | "half_hip" | "mansard" | "mansard_gable";
            /** Roof Slopes Deg */
            readonly roof_slopes_deg: readonly number[];
            /** Storeys */
            readonly storeys: number;
            readonly terrace: components["schemas"]["HouseTerraceFacts"] | null;
            /** Top Height */
            readonly top_height: number;
        };
        /** HouseInteriorWall */
        readonly HouseInteriorWall: {
            /** Adjacent Room Ids */
            readonly adjacent_room_ids: readonly string[];
            /** Axis */
            readonly axis: readonly [
                components["schemas"]["HousePoint"],
                components["schemas"]["HousePoint"]
            ];
            /** Id */
            readonly id: string;
            /** Level Id */
            readonly level_id: string;
            /** Source Ifc Guid */
            readonly source_ifc_guid: string | null;
            /** Thickness */
            readonly thickness: number;
        };
        /** HouseLevel */
        readonly HouseLevel: {
            /** Elevation */
            readonly elevation: number;
            /** Id */
            readonly id: string;
            /** Name */
            readonly name: string;
        };
        /**
         * HouseLine
         * @description Ausstattungslinie (Ergänzung 6, E-HM-14): setzt mehrere Slots auf ausdrückliche Wahl des Kunden auf
         *     einmal. Sie wird nicht gespeichert und hat keinen eigenen Preis; aktiv ist sie, solange alle ihre Werte
         *     gelten.
         */
        readonly HouseLine: {
            readonly description: components["schemas"]["HouseText"] | null;
            /** Id */
            readonly id: string;
            readonly name: components["schemas"]["HouseText"];
            /** Presets */
            readonly presets: {
                readonly [key: string]: components["schemas"]["HouseSlotValue"];
            };
            /** Sort Order */
            readonly sort_order: number;
        };
        readonly HouseLiteral: string | number | boolean | null;
        /** HouseLogicExpr */
        readonly HouseLogicExpr: {
            /** Args */
            readonly args: readonly components["schemas"]["HouseExpr"][];
            /**
             * Op
             * @enum {string}
             */
            readonly op: "and" | "or" | "not" | "exists";
        };
        /** HouseMaterial */
        readonly HouseMaterial: {
            /** Carbon Per M3 */
            readonly carbon_per_m3: number | null;
            /** Conductivity */
            readonly conductivity: number | null;
            /** Density */
            readonly density: number | null;
            /** Id */
            readonly id: string;
            readonly name: components["schemas"]["HouseText"];
            /** Render Key */
            readonly render_key: string;
        };
        /** HouseOpening */
        readonly HouseOpening: {
            /** Adjacent Room Ids */
            readonly adjacent_room_ids: readonly string[];
            /** Host Id */
            readonly host_id: string;
            /**
             * Host Kind
             * @enum {string}
             */
            readonly host_kind: "envelope_segment" | "interior_wall";
            /** Id */
            readonly id: string;
            /**
             * Kind
             * @enum {string}
             */
            readonly kind: "window" | "door";
            /** Offset Along Host */
            readonly offset_along_host: number;
            /** Source Ifc Guid */
            readonly source_ifc_guid: string | null;
        };
        /**
         * HouseOptionAssigns
         * @description Ein Wert weist immer einen vollständigen Typ zu, nie eine Ergänzung (P 8.1).
         */
        readonly HouseOptionAssigns: {
            /** Carport Type Id */
            readonly carport_type_id: string | null;
            /** Door Type Id */
            readonly door_type_id: string | null;
            /** Roof Shape Id */
            readonly roof_shape_id: string | null;
            /** Roof Type Id */
            readonly roof_type_id: string | null;
            /** Terrace Type Id */
            readonly terrace_type_id: string | null;
            /** Wall Profile Id */
            readonly wall_profile_id: string | null;
            /** Window Type Id */
            readonly window_type_id: string | null;
        };
        /** HouseOptionCondition */
        readonly HouseOptionCondition: {
            /** Option Value Id */
            readonly option_value_id: string;
            /** Slot Id */
            readonly slot_id: string;
        };
        /** HouseOptionValue */
        readonly HouseOptionValue: {
            readonly assigns: components["schemas"]["HouseOptionAssigns"];
            readonly available_when: components["schemas"]["HouseExpr"];
            readonly description: components["schemas"]["HouseText"] | null;
            /** Id */
            readonly id: string;
            readonly name: components["schemas"]["HouseText"];
            /** Slot Id */
            readonly slot_id: string;
            /** Sort Order */
            readonly sort_order: number;
            readonly unavailable_reason: components["schemas"]["HouseText"] | null;
        };
        /** HousePathExpr */
        readonly HousePathExpr: {
            /** Path */
            readonly path: string;
        };
        /** HousePoint */
        readonly HousePoint: {
            /** X */
            readonly x: number;
            /** Y */
            readonly y: number;
        };
        /** HousePoint3 */
        readonly HousePoint3: {
            /** X */
            readonly x: number;
            /** Y */
            readonly y: number;
            /** Z */
            readonly z: number;
        };
        /**
         * HousePrice
         * @description Exakte Richtpreise für Snapshot und Dossier; der Kunde sieht nur gerundete Beträge (E-HM-2, L1).
         */
        readonly HousePrice: {
            /** Base Amount */
            readonly base_amount: number;
            /**
             * Currency
             * @constant
             */
            readonly currency: "EUR";
            /** Deltas */
            readonly deltas: {
                readonly [key: string]: number;
            };
            /** Gross Amount */
            readonly gross_amount: number;
            /**
             * Is Estimate
             * @constant
             */
            readonly is_estimate: true;
            /** Items */
            readonly items: readonly components["schemas"]["HousePriceItem"][];
            /**
             * Market
             * @constant
             */
            readonly market: "FR";
            /** Net Amount */
            readonly net_amount: number;
            /** Vat Amount */
            readonly vat_amount: number;
            /** Vat Rate */
            readonly vat_rate: number;
        };
        /**
         * HousePriceEntry
         * @description Sagt nur, was wie viel kostet (P 5.2); jeder Betrag stammt aus genau einem Eintrag (P 2.1 Nr. 11).
         */
        readonly HousePriceEntry: {
            /** Id */
            readonly id: string;
            /** Target Id */
            readonly target_id: string;
            /**
             * Target Kind
             * @enum {string}
             */
            readonly target_kind: "wall_layer" | "window_type" | "door_type" | "roof_type" | "template" | "slot_option" | "service" | "terrace_type" | "carport_type";
            /**
             * Unit
             * @enum {string}
             */
            readonly unit: "m" | "m2" | "m3" | "pcs" | "lump_sum" | "percent";
            /** Value */
            readonly value: number;
        };
        /** HousePriceItem */
        readonly HousePriceItem: {
            /** Amount */
            readonly amount: number;
            /** Element Ids */
            readonly element_ids: readonly string[];
            readonly label: components["schemas"]["HouseText"];
            /** Price Entry Id */
            readonly price_entry_id: string;
            /** Pricing Rule Id */
            readonly pricing_rule_id: string;
            /** Quantity */
            readonly quantity: number;
            /** Quantity Key */
            readonly quantity_key: string | null;
            /** Ref Id */
            readonly ref_id: string | null;
            /**
             * Unit
             * @enum {string}
             */
            readonly unit: "m" | "m2" | "m3" | "pcs" | "lump_sum" | "percent";
            /** Unit Price */
            readonly unit_price: number;
        };
        /**
         * HousePricingRule
         * @description Sagt nur, welche Menge mit welchem Eintrag verrechnet wird (P 9.2); enthält keine Beträge.
         */
        readonly HousePricingRule: {
            readonly applies_to: components["schemas"]["HouseOptionCondition"] | null;
            /** By Target */
            readonly by_target: ("wall_layer" | "window_type" | "door_type" | "roof_type" | "template" | "slot_option" | "service" | "terrace_type" | "carport_type") | null;
            /** Entry Id */
            readonly entry_id: string | null;
            /** Id */
            readonly id: string;
            readonly label: components["schemas"]["HouseText"];
            /**
             * Method
             * @enum {string}
             */
            readonly method: "per_unit" | "lump_sum" | "percent";
            /** Order */
            readonly order: number;
            /** Percent Base */
            readonly percent_base: string | null;
            /** Quantity Key */
            readonly quantity_key: string | null;
        };
        /** HouseProfileUValue */
        readonly HouseProfileUValue: {
            /** U Value */
            readonly u_value: number;
            /** Wall Profile Id */
            readonly wall_profile_id: string;
        };
        /** HouseQuantity */
        readonly HouseQuantity: {
            /** Element Ids */
            readonly element_ids: readonly string[];
            /** Key */
            readonly key: string;
            /** Ref Id */
            readonly ref_id: string | null;
            /**
             * Unit
             * @enum {string}
             */
            readonly unit: "m" | "m2" | "m3" | "pcs";
            /** Value */
            readonly value: number;
        };
        /**
         * HouseResolutionNote
         * @description Eine Stufe der Auflösung griff nicht (P 8.2); die Auswahl bleibt unverändert. `default_replaced`: der
         *     Standard ist nicht verfügbar, es gilt der erste verfügbare Wert (E-HM-60). `out_of_range`: die Zahl liegt
         *     außerhalb der Spanne. `roof_kind_mismatch`: der Dachaufbau passt nicht zur wirksamen Dachform (flach oder
         *     geneigt). `roof_not_constructible`: Form, Neigung oder Drehung lässt sich auf dem Grundriss nicht erzeugen
         *     (Ergänzung 4).
         */
        readonly HouseResolutionNote: {
            /** Applied Number */
            readonly applied_number: number | null;
            /** Applied Value Id */
            readonly applied_value_id: string | null;
            /**
             * Code
             * @enum {string}
             */
            readonly code: "unavailable" | "room_override_tie" | "out_of_range" | "roof_kind_mismatch" | "roof_not_constructible" | "default_replaced";
            /** Element Id */
            readonly element_id: string;
            readonly reason: components["schemas"]["HouseText"] | null;
            /**
             * Skipped Level
             * @enum {string}
             */
            readonly skipped_level: "element" | "room" | "global" | "default";
            /** Skipped Number */
            readonly skipped_number: number | null;
            /** Skipped Value Ids */
            readonly skipped_value_ids: readonly string[];
            /** Slot Id */
            readonly slot_id: string;
        };
        /**
         * HouseResolvedValue
         * @description Wirksamer Wert: ein Wert des Katalogs oder bei Parameter-Slots eine Zahl.
         */
        readonly HouseResolvedValue: {
            /** Available */
            readonly available: boolean;
            /** Element Id */
            readonly element_id: string;
            /** Number */
            readonly number: number | null;
            /** Option Value Id */
            readonly option_value_id: string | null;
            /** Slot Id */
            readonly slot_id: string;
            /**
             * Source
             * @enum {string}
             */
            readonly source: "element" | "room" | "global" | "default";
        };
        /** HouseRevealFinish */
        readonly HouseRevealFinish: {
            /** Material Id */
            readonly material_id: string;
        };
        /**
         * HouseRoofDesign
         * @description Dachform mit Parametern (Ergänzung 4, 11): aus dem IFC oder im Entwurf vom Büro gesetzt; Voreinstellung
         *     der Dachform im Konfigurator.
         */
        readonly HouseRoofDesign: {
            /** Break Height */
            readonly break_height: number | null;
            /**
             * Form
             * @enum {string}
             */
            readonly form: "flat" | "mono_pitch" | "gable" | "hip" | "half_hip" | "mansard" | "mansard_gable";
            /** Pitch Deg */
            readonly pitch_deg: number | null;
            /**
             * Rotation
             * @enum {integer}
             */
            readonly rotation: 0 | 90 | 180 | 270;
            /** Upper Pitch Deg */
            readonly upper_pitch_deg: number | null;
        };
        /** HouseRoofFace */
        readonly HouseRoofFace: {
            /** Contour Edges */
            readonly contour_edges: readonly number[];
            /** Pitch Deg */
            readonly pitch_deg: number;
            /** Polygon */
            readonly polygon: readonly components["schemas"]["HousePoint3"][];
            /** Segment */
            readonly segment: number;
        };
        /** HouseRoofGeometry */
        readonly HouseRoofGeometry: {
            /** Eave Height */
            readonly eave_height: number;
            /** Edge Kinds */
            readonly edge_kinds: readonly ("eave" | "gable")[];
            /** Faces */
            readonly faces: readonly components["schemas"]["HouseRoofFace"][];
            /** Lines */
            readonly lines: readonly components["schemas"]["HouseRoofLine"][];
            /** Outline */
            readonly outline: readonly components["schemas"]["HousePoint"][];
            /** Ridge Azimuth Deg */
            readonly ridge_azimuth_deg: number | null;
            /** Top Height */
            readonly top_height: number;
        };
        /** HouseRoofLayer */
        readonly HouseRoofLayer: {
            /** Material Id */
            readonly material_id: string;
            /** Thickness */
            readonly thickness: number;
        };
        /** HouseRoofLine */
        readonly HouseRoofLine: {
            readonly a: components["schemas"]["HousePoint3"];
            readonly b: components["schemas"]["HousePoint3"];
            /**
             * Kind
             * @enum {string}
             */
            readonly kind: "ridge" | "hip" | "valley" | "eave" | "verge" | "break";
        };
        /** HouseRoofPitch */
        readonly HouseRoofPitch: {
            /** Default Deg */
            readonly default_deg: number;
            /** Max Deg */
            readonly max_deg: number;
            /** Min Deg */
            readonly min_deg: number;
        };
        /**
         * HouseRoofPlacement
         * @description Dach des Templates (3.6, E-HM-10): Lage, Maße und Form aus dem IFC; Form und Aufbau wählt der
         *     Konfigurator.
         */
        readonly HouseRoofPlacement: {
            /** Bearing Height */
            readonly bearing_height: number;
            readonly design: components["schemas"]["HouseRoofDesign"];
            /** Eave Overhang */
            readonly eave_overhang: number;
            /** Parapet Height */
            readonly parapet_height: number;
            /** Verge Overhang */
            readonly verge_overhang: number;
        };
        /**
         * HouseRoofRequest
         * @description Geneigtes Dach aus Form und Parametern; der IFC-Import vergleicht es mit dem Dach aus Archicad.
         */
        readonly HouseRoofRequest: {
            /** Bearing Height */
            readonly bearing_height: number;
            /** Contour */
            readonly contour: readonly components["schemas"]["HousePoint"][];
            readonly design: components["schemas"]["HouseRoofDesign"];
            /** Eave Overhang */
            readonly eave_overhang: number;
            /** Thickness */
            readonly thickness: number;
            /** Verge Overhang */
            readonly verge_overhang: number;
            /** Wall Thickness */
            readonly wall_thickness: number;
        };
        /**
         * HouseRoofShape
         * @description Dachform des Katalogs (Ergänzung 4): Voreinstellung und Spanne der Neigung, Knick- und Krüppelhöhe.
         *     Ist die Form die des Templates, gelten die Werte des Templates. Überstände, Dachdecke und Attika gelten
         *     nur, wenn das Template die andere Dachart hat (flach ↔ geneigt).
         */
        readonly HouseRoofShape: {
            /** Break Height */
            readonly break_height: number | null;
            /** Eave Overhang */
            readonly eave_overhang: number;
            /**
             * Form
             * @enum {string}
             */
            readonly form: "flat" | "mono_pitch" | "gable" | "hip" | "half_hip" | "mansard" | "mansard_gable";
            /** Id */
            readonly id: string;
            readonly name: components["schemas"]["HouseText"];
            /** Parapet Height */
            readonly parapet_height: number | null;
            readonly pitch: components["schemas"]["HouseRoofPitch"] | null;
            /** Render Key */
            readonly render_key: string;
            /** Slab Thickness */
            readonly slab_thickness: number | null;
            /** Upper Pitch Deg */
            readonly upper_pitch_deg: number | null;
            /** Verge Overhang */
            readonly verge_overhang: number;
        };
        /**
         * HouseRoofType
         * @description Dachaufbau (E-HM-10); `kind` sagt, zu welchen Dachformen er passt.
         */
        readonly HouseRoofType: {
            /** Build Up */
            readonly build_up: readonly components["schemas"]["HouseRoofLayer"][];
            /** Green */
            readonly green: boolean;
            /** Id */
            readonly id: string;
            /**
             * Kind
             * @enum {string}
             */
            readonly kind: "flat" | "pitched";
            /**
             * Material Class
             * @enum {string}
             */
            readonly material_class: "render" | "wood" | "brick" | "stone" | "concrete" | "metal" | "glass" | "slate" | "clay_tile" | "zinc" | "composite" | "vegetation" | "other";
            readonly name: components["schemas"]["HouseText"];
            /** Render Key */
            readonly render_key: string;
        };
        /**
         * HouseRoom
         * @description Raum; Fläche nur aus dem Umriss, Name aus dem Raumtyp (E-HM-23).
         */
        readonly HouseRoom: {
            /** Id */
            readonly id: string;
            /** Level Id */
            readonly level_id: string;
            /** Polygon */
            readonly polygon: readonly components["schemas"]["HousePoint"][];
            /** Room Type Id */
            readonly room_type_id: string;
            /** Source Ifc Guid */
            readonly source_ifc_guid: string | null;
        };
        /** HouseRoomType */
        readonly HouseRoomType: {
            /** Aliases */
            readonly aliases: readonly string[];
            readonly description: components["schemas"]["HouseText"] | null;
            /** Display Key */
            readonly display_key: string;
            /** Exterior Door Role */
            readonly exterior_door_role: ("entrance" | "garage_door") | null;
            /** Id */
            readonly id: string;
            readonly name: components["schemas"]["HouseText"];
            /** Override Priority */
            readonly override_priority: number;
        };
        /**
         * HouseRule
         * @description Technische Regel des Katalogs (P 8.3); `when` wahr heißt: trifft zu.
         */
        readonly HouseRule: {
            /** Id */
            readonly id: string;
            readonly message: components["schemas"]["HouseText"];
            /**
             * Outcome
             * @enum {string}
             */
            readonly outcome: "info" | "warning" | "block";
            /**
             * Scope
             * @enum {string}
             */
            readonly scope: "selection" | "element" | "building";
            readonly source: components["schemas"]["HouseRuleSource"] | null;
            readonly suggestion: components["schemas"]["HouseSuggestion"] | null;
            readonly target: components["schemas"]["HouseSelector"] | null;
            readonly when: components["schemas"]["HouseExpr"];
        };
        /** HouseRuleResult */
        readonly HouseRuleResult: {
            /** Code */
            readonly code: string;
            /** Element Ids */
            readonly element_ids: readonly string[];
            readonly message: components["schemas"]["HouseText"] | null;
            /**
             * Outcome
             * @enum {string}
             */
            readonly outcome: "info" | "warning" | "block" | "deviation";
            /** Params */
            readonly params: {
                readonly [key: string]: number | string;
            };
            /** Rule Id */
            readonly rule_id: string | null;
            readonly source: components["schemas"]["HouseRuleSource"] | null;
            readonly suggestion: components["schemas"]["HouseSuggestion"] | null;
        };
        /** HouseRuleSource */
        readonly HouseRuleSource: {
            /** Document */
            readonly document: string | null;
            /** Jurisdiction */
            readonly jurisdiction: string | null;
            /** Reference */
            readonly reference: string | null;
            /** Retrieved At */
            readonly retrieved_at: string | null;
            /** Section */
            readonly section: string | null;
        };
        /** HouseSelector */
        readonly HouseSelector: {
            /**
             * Element Kind
             * @enum {string}
             */
            readonly element_kind: "envelope_segment" | "interior_wall" | "opening" | "roof" | "room" | "building" | "site";
            readonly where: components["schemas"]["HouseExpr"];
        };
        /** HouseSlab */
        readonly HouseSlab: {
            /** Id */
            readonly id: string;
            /**
             * Kind
             * @enum {string}
             */
            readonly kind: "ground" | "floor" | "roof";
            /** Level Id */
            readonly level_id: string;
            /** Source Ifc Guid */
            readonly source_ifc_guid: string | null;
            /** Thickness */
            readonly thickness: number;
        };
        /** HouseSlot */
        readonly HouseSlot: {
            /** Category */
            readonly category: string;
            readonly description: components["schemas"]["HouseText"] | null;
            readonly effects: components["schemas"]["HouseSlotEffects"];
            /**
             * Granularity
             * @enum {string}
             */
            readonly granularity: "global" | "per_element" | "per_room";
            /** Id */
            readonly id: string;
            readonly name: components["schemas"]["HouseText"];
            /** Parameter */
            readonly parameter: ("roof_pitch" | "roof_rotation") | null;
            /** Parent Slot Id */
            readonly parent_slot_id: string | null;
            /** Sort Order */
            readonly sort_order: number;
            readonly target: components["schemas"]["HouseSelector"];
            /**
             * Value Type
             * @enum {string}
             */
            readonly value_type: "single" | "number";
        };
        /**
         * HouseSlotEffects
         * @description Nur Hinweis für Neuberechnung; die Korrektheit hängt nie davon ab (P 8.1).
         */
        readonly HouseSlotEffects: {
            /** Appearance */
            readonly appearance: boolean;
            /** Geometry */
            readonly geometry: boolean;
            /** Pricing */
            readonly pricing: boolean;
            /** Quantity */
            readonly quantity: boolean;
            /** Rules */
            readonly rules: boolean;
        };
        /**
         * HouseSlotNumber
         * @description Zahl eines Parameter-Slots, z. B. Dachneigung in Grad (E-HM-62).
         */
        readonly HouseSlotNumber: {
            /**
             * @description discriminator enum property added by openapi-typescript
             * @enum {string}
             */
            readonly type: "number";
            /** Value */
            readonly value: number;
        };
        /** HouseSlotOption */
        readonly HouseSlotOption: {
            /** Option Value Id */
            readonly option_value_id: string;
            /**
             * @description discriminator enum property added by openapi-typescript
             * @enum {string}
             */
            readonly type: "option";
        };
        /** HouseSlotSelection */
        readonly HouseSlotSelection: {
            /** Element Overrides */
            readonly element_overrides: {
                readonly [key: string]: components["schemas"]["HouseSlotValue"];
            };
            /** Room Overrides */
            readonly room_overrides: {
                readonly [key: string]: components["schemas"]["HouseSlotValue"];
            };
            readonly value: components["schemas"]["HouseSlotValue"] | null;
        };
        readonly HouseSlotValue: components["schemas"]["HouseSlotOption"] | components["schemas"]["HouseSlotNumber"];
        /** HouseSourceIfc */
        readonly HouseSourceIfc: {
            /** File Name */
            readonly file_name: string;
            /** Ifc Schema */
            readonly ifc_schema: string;
            /**
             * Imported At
             * Format: date-time
             */
            readonly imported_at: string;
            /** Sha256 */
            readonly sha256: string;
        };
        /** HouseSuggestion */
        readonly HouseSuggestion: {
            /** Element Ids */
            readonly element_ids: readonly string[];
            readonly label: components["schemas"]["HouseText"];
            /** Option Value Id */
            readonly option_value_id: string;
            /** Slot Id */
            readonly slot_id: string;
        };
        /**
         * HouseTemplate
         * @description Haustyp in einer Version, unveränderlich nach der Veröffentlichung (P 5.1, L4). Keine Preise.
         *
         *     Mehrere Geschosse haben dieselbe Bezugskontur (E-HM-63); das Dach liegt über dem obersten.
         */
        readonly HouseTemplate: {
            /** Defaults */
            readonly defaults: {
                readonly [key: string]: string;
            };
            /** Element Defaults */
            readonly element_defaults: {
                readonly [key: string]: {
                    readonly [key: string]: string;
                };
            };
            /** Entrance Opening Id */
            readonly entrance_opening_id: string | null;
            /** Envelope */
            readonly envelope: readonly components["schemas"]["HouseEnvelopeLoop"][];
            /** Garage Door Opening Id */
            readonly garage_door_opening_id: string | null;
            /** Ground Floor Offset */
            readonly ground_floor_offset: number;
            /** Interior Walls */
            readonly interior_walls: readonly components["schemas"]["HouseInteriorWall"][];
            /** Levels */
            readonly levels: readonly components["schemas"]["HouseLevel"][];
            readonly name: components["schemas"]["HouseText"];
            /** Openings */
            readonly openings: readonly components["schemas"]["HouseOpening"][];
            readonly roof: components["schemas"]["HouseRoofPlacement"];
            /** Rooms */
            readonly rooms: readonly components["schemas"]["HouseRoom"][];
            /**
             * Schema Version
             * @constant
             */
            readonly schema_version: 2;
            /** Slabs */
            readonly slabs: readonly components["schemas"]["HouseSlab"][];
            /** Slug */
            readonly slug: string;
            readonly source_ifc: components["schemas"]["HouseSourceIfc"] | null;
        };
        /** HouseTerraceFacts */
        readonly HouseTerraceFacts: {
            /** Depth */
            readonly depth: number;
            /** Height Above Terrain */
            readonly height_above_terrain: number;
            /** Sealing Factor */
            readonly sealing_factor: number;
            /** Type Id */
            readonly type_id: string;
            /** Width */
            readonly width: number | null;
        };
        /**
         * HouseTerraceType
         * @description Terrasse (Ergänzung 7): an der längsten Gartenkante, so breit wie diese; die Lage rechnet Python.
         */
        readonly HouseTerraceType: {
            /** Depth */
            readonly depth: number;
            /** Height Above Terrain */
            readonly height_above_terrain: number;
            /** Id */
            readonly id: string;
            readonly name: components["schemas"]["HouseText"];
            /** Render Key */
            readonly render_key: string;
            /** Sealing Factor */
            readonly sealing_factor: number;
        };
        /**
         * HouseText
         * @description Text in den Sprachen der Oberfläche (D7: Französisch führend, Deutsch zusätzlich).
         */
        readonly HouseText: {
            /** De */
            readonly de: string;
            /** Fr */
            readonly fr: string;
        };
        /** HouseWallLayer */
        readonly HouseWallLayer: {
            /** Id */
            readonly id: string;
            /** Material Id */
            readonly material_id: string;
            /** Structural */
            readonly structural: boolean;
            /** Thermal */
            readonly thermal: boolean;
            /** Thickness */
            readonly thickness: number;
        };
        /** HouseWallProfile */
        readonly HouseWallProfile: {
            readonly bearing: components["schemas"]["HouseBearing"] | null;
            /** Id */
            readonly id: string;
            /** Layer Ids */
            readonly layer_ids: readonly string[];
            /**
             * Material Class
             * @enum {string}
             */
            readonly material_class: "render" | "wood" | "brick" | "stone" | "concrete" | "metal" | "glass" | "slate" | "clay_tile" | "zinc" | "composite" | "vegetation" | "other";
            readonly name: components["schemas"]["HouseText"];
            /** Opening Anchor Layer Id */
            readonly opening_anchor_layer_id: string;
            readonly reveal_finish: components["schemas"]["HouseRevealFinish"] | null;
        };
        /** HouseWindowShare */
        readonly HouseWindowShare: {
            /**
             * Direction
             * @enum {string}
             */
            readonly direction: "n" | "e" | "s" | "w";
            /** Facade Area */
            readonly facade_area: number;
            /** Ratio */
            readonly ratio: number;
            /** Window Area */
            readonly window_area: number;
        };
        /** HouseWindowType */
        readonly HouseWindowType: {
            /** G */
            readonly g: number | null;
            /** Head Height */
            readonly head_height: number;
            /** Height */
            readonly height: number;
            /** Id */
            readonly id: string;
            readonly name: components["schemas"]["HouseText"];
            /** Render Key */
            readonly render_key: string;
            /** Shutter Box Height */
            readonly shutter_box_height: number;
            /** Uw */
            readonly uw: number | null;
            /** Width */
            readonly width: number;
        };
    };
    responses: never;
    parameters: never;
    requestBodies: never;
    headers: never;
    pathItems: never;
}
export type HouseBearing = components['schemas']['HouseBearing'];
export type HouseBinaryExpr = components['schemas']['HouseBinaryExpr'];
export type HouseCandidate = components['schemas']['HouseCandidate'];
export type HouseCandidatesRequest = components['schemas']['HouseCandidatesRequest'];
export type HouseCarportFacts = components['schemas']['HouseCarportFacts'];
export type HouseCarportType = components['schemas']['HouseCarportType'];
export type HouseCatalog = components['schemas']['HouseCatalog'];
export type HouseCatalogParameters = components['schemas']['HouseCatalogParameters'];
export type HouseCompatibility = components['schemas']['HouseCompatibility'];
export type HouseCompatibilityIssue = components['schemas']['HouseCompatibilityIssue'];
export type HouseCompatibilityRequest = components['schemas']['HouseCompatibilityRequest'];
export type HouseConfiguration = components['schemas']['HouseConfiguration'];
export type HouseDoorType = components['schemas']['HouseDoorType'];
export type HouseEdgePosition = components['schemas']['HouseEdgePosition'];
export type HouseEdgeRole = components['schemas']['HouseEdgeRole'];
export type HouseEnergy = components['schemas']['HouseEnergy'];
export type HouseEnvelopeLoop = components['schemas']['HouseEnvelopeLoop'];
export type HouseEnvelopeSegment = components['schemas']['HouseEnvelopeSegment'];
export type HouseEvaluateRequest = components['schemas']['HouseEvaluateRequest'];
export type HouseEvaluation = components['schemas']['HouseEvaluation'];
export type HouseExpr = components['schemas']['HouseExpr'];
export type HouseFacts = components['schemas']['HouseFacts'];
export type HouseInteriorWall = components['schemas']['HouseInteriorWall'];
export type HouseLevel = components['schemas']['HouseLevel'];
export type HouseLine = components['schemas']['HouseLine'];
export type HouseLiteral = components['schemas']['HouseLiteral'];
export type HouseLogicExpr = components['schemas']['HouseLogicExpr'];
export type HouseMaterial = components['schemas']['HouseMaterial'];
export type HouseOpening = components['schemas']['HouseOpening'];
export type HouseOptionAssigns = components['schemas']['HouseOptionAssigns'];
export type HouseOptionCondition = components['schemas']['HouseOptionCondition'];
export type HouseOptionValue = components['schemas']['HouseOptionValue'];
export type HousePathExpr = components['schemas']['HousePathExpr'];
export type HousePoint = components['schemas']['HousePoint'];
export type HousePoint3 = components['schemas']['HousePoint3'];
export type HousePrice = components['schemas']['HousePrice'];
export type HousePriceEntry = components['schemas']['HousePriceEntry'];
export type HousePriceItem = components['schemas']['HousePriceItem'];
export type HousePricingRule = components['schemas']['HousePricingRule'];
export type HouseProfileUValue = components['schemas']['HouseProfileUValue'];
export type HouseQuantity = components['schemas']['HouseQuantity'];
export type HouseResolutionNote = components['schemas']['HouseResolutionNote'];
export type HouseResolvedValue = components['schemas']['HouseResolvedValue'];
export type HouseRevealFinish = components['schemas']['HouseRevealFinish'];
export type HouseRoofDesign = components['schemas']['HouseRoofDesign'];
export type HouseRoofFace = components['schemas']['HouseRoofFace'];
export type HouseRoofGeometry = components['schemas']['HouseRoofGeometry'];
export type HouseRoofLayer = components['schemas']['HouseRoofLayer'];
export type HouseRoofLine = components['schemas']['HouseRoofLine'];
export type HouseRoofPitch = components['schemas']['HouseRoofPitch'];
export type HouseRoofPlacement = components['schemas']['HouseRoofPlacement'];
export type HouseRoofRequest = components['schemas']['HouseRoofRequest'];
export type HouseRoofShape = components['schemas']['HouseRoofShape'];
export type HouseRoofType = components['schemas']['HouseRoofType'];
export type HouseRoom = components['schemas']['HouseRoom'];
export type HouseRoomType = components['schemas']['HouseRoomType'];
export type HouseRule = components['schemas']['HouseRule'];
export type HouseRuleResult = components['schemas']['HouseRuleResult'];
export type HouseRuleSource = components['schemas']['HouseRuleSource'];
export type HouseSelector = components['schemas']['HouseSelector'];
export type HouseSlab = components['schemas']['HouseSlab'];
export type HouseSlot = components['schemas']['HouseSlot'];
export type HouseSlotEffects = components['schemas']['HouseSlotEffects'];
export type HouseSlotNumber = components['schemas']['HouseSlotNumber'];
export type HouseSlotOption = components['schemas']['HouseSlotOption'];
export type HouseSlotSelection = components['schemas']['HouseSlotSelection'];
export type HouseSlotValue = components['schemas']['HouseSlotValue'];
export type HouseSourceIfc = components['schemas']['HouseSourceIfc'];
export type HouseSuggestion = components['schemas']['HouseSuggestion'];
export type HouseTemplate = components['schemas']['HouseTemplate'];
export type HouseTerraceFacts = components['schemas']['HouseTerraceFacts'];
export type HouseTerraceType = components['schemas']['HouseTerraceType'];
export type HouseText = components['schemas']['HouseText'];
export type HouseWallLayer = components['schemas']['HouseWallLayer'];
export type HouseWallProfile = components['schemas']['HouseWallProfile'];
export type HouseWindowShare = components['schemas']['HouseWindowShare'];
export type HouseWindowType = components['schemas']['HouseWindowType'];
export type $defs = Record<string, never>;
export type operations = Record<string, never>;
