// Geneigtes Dach für den IFC-Import (E-HM-64): der Import leitet Form und Parameter aus den Dachflächen in Archicad ab
// und vergleicht das Dach des Kerns mit ihnen. Vertrag `HouseRoofRequest` → `HouseRoofGeometry`, Längen in m.
import type { HousePoint3, HouseRoofGeometry, HouseRoofRequest } from "../contract.gen.ts";
import { ModelError } from "../errors.ts";
import { polygonDefect, signedArea, toUnits } from "../geometry/polygon.ts";
import { buildRoof, RoofError, roofRefusal, type Roof } from "./build.ts";
import type { Vec3 } from "./skeleton.ts";

const point3 = (p: Vec3): HousePoint3 => ({ x: p.x, y: p.y, z: p.z });

/** Wirft `ModelError`: `envelope_invalid`, `envelope_not_counter_clockwise`, `roof_not_constructible` mit Grund. */
export function roofGeometry(request: HouseRoofRequest): HouseRoofGeometry {
  if (request.design.form === "flat") throw new Error("roofGeometry: nur geneigte Dächer");
  const contour = request.contour.map((p) => ({ x: toUnits(p.x), y: toUnits(p.y) }));
  const defect = polygonDefect(contour);
  if (defect) throw new ModelError("envelope_invalid", { defect });
  if (signedArea(contour) <= 0) throw new ModelError("envelope_not_counter_clockwise");
  const { design } = request;
  let roof: Roof;
  try {
    roof = buildRoof({
      contour,
      bearing: request.bearing_height,
      wallThickness: request.wall_thickness,
      eaveOverhang: request.eave_overhang,
      vergeOverhang: request.verge_overhang,
      design: { form: design.form, pitchDeg: design.pitch_deg, upperPitchDeg: design.upper_pitch_deg, breakHeight: design.break_height, rotation: design.rotation },
      thickness: request.thickness,
    });
  } catch (error) {
    if (error instanceof RoofError) throw new ModelError("roof_not_constructible", { reason: roofRefusal(error.code) });
    throw error;
  }
  return {
    outline: roof.outline.map((p) => ({ x: p.x, y: p.y })),
    edge_kinds: roof.edgeKinds,
    faces: roof.faces.map((f) => ({ contour_edges: f.contourEdges, segment: f.segment, pitch_deg: f.pitchDeg, polygon: f.polygon.map(point3) })),
    lines: roof.lines.map((l) => ({ kind: l.kind, a: point3(l.a), b: point3(l.b) })),
    top_height: roof.top,
    eave_height: roof.eave,
    ridge_azimuth_deg: roof.ridgeAzimuthDeg,
  };
}
