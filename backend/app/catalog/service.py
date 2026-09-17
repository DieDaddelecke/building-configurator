"""Dienst des Moduls H1 (Plan H1 4.3). Nur für das Büro (`architect`, `catalog_admin`, `ops`)."""

import hashlib
import math
import re
from datetime import date

from shapely.geometry import Polygon
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.catalog.domain.consistency import check_roof_pitch, check_room_area_share
from app.catalog.domain.dxf import FootprintDxfInvalid, read_footprints
from app.catalog.domain.xlsx import TypeWorkbookInvalid, read_type_workbook
from app.catalog.models import (
    BuildingType,
    BuildingTypeVersion,
    EnergyAssessment,
    Module,
    ModuleTypePrice,
    ModuleVersion,
    Package,
    PackageTypePrice,
    PackageVersion,
    PlanDocument,
    PriceCatalog,
    PriceCatalogVersion,
    TypeBasePrice,
)
from app.catalog.schemas import (
    ConsistencyFindingOut,
    EnergyAssessmentOut,
    FacadeRolesIn,
    ModuleIn,
    ModuleTypePriceOut,
    ModuleVersionOut,
    PackageIn,
    PackageTypePriceOut,
    PackageVersionOut,
    PlacementIn,
    PlanDocumentOut,
    PriceCatalogVersionOut,
    RoomOut,
    TypeBasePriceOut,
    TypeSummaryOut,
    TypeVersionOut,
)
from app.platform import audit, storage
from app.platform.db import utcnow
from app.platform.problems import Problem

DEFAULT_PRICE_REGION = "default"
DEFAULT_CLIMATE_ZONE = "H2b"
SLUG_RE = re.compile(r"^[a-z][a-z0-9_]{1,59}$")


def _check_slug(slug: str) -> None:
    if not SLUG_RE.match(slug):
        raise Problem(422, "validation_error", detail="slug muss ^[a-z][a-z0-9_]{1,59}$ entsprechen")


def _storey_count(storeys: str) -> int:
    """Grobe Zählung aus der PLU-Notation (`R+1+C` → 3), für die Warnschwelle der Raumflächen (3.5)."""
    return max(1, len([p for p in storeys.split("+") if p]))


def _depth_m(facade: Polygon, ridge_direction: str | None) -> float:
    """Lauf des Dachs quer zum First: kürzere Rechteckseite bei `laengs`/unbekannt, längere bei `quer`
    (Plan H1 3.5; First liegt bei `laengs` auf der langen Seite, das Dach läuft über die kurze)."""
    rect = facade.minimum_rotated_rectangle
    xs, ys = rect.exterior.coords.xy
    sides = sorted(math.dist((xs[i], ys[i]), (xs[i + 1], ys[i + 1])) for i in range(len(xs) - 1))
    short_side, long_side = sides[0], sides[-1]
    return long_side if ridge_direction == "quer" else short_side


def _building_type(db: Session, slug: str) -> BuildingType:
    building_type = db.execute(select(BuildingType).where(BuildingType.slug == slug)).scalar_one_or_none()
    if building_type is None:
        raise Problem(404, "not_found", detail=f"Typ „{slug}“ nicht gefunden")
    return building_type


def _version_out(version: BuildingTypeVersion, slug: str) -> TypeVersionOut:
    return TypeVersionOut(
        id=version.id,
        building_type_id=version.building_type_id,
        slug=slug,
        version=version.version,
        status=version.status,
        name=version.name,
        family=None,
        storeys=version.storeys,
        roof_form=version.roof_form,
        pitch_deg=version.pitch_deg,
        ridge_direction=version.ridge_direction,
        ridge_height_m=version.ridge_height_m,
        eave_height_m=version.eave_height_m,
        footprint_facade=version.footprint_facade,
        footprint_facade_area_m2=version.footprint_facade_area_m2,
        footprint_projection=version.footprint_projection,
        footprint_projection_area_m2=version.footprint_projection_area_m2,
        living_area_m2=version.living_area_m2,
        rooms_text=version.rooms_text,
        rooms=[RoomOut(**r) for r in version.rooms],
        facade_roles=version.facade_roles,
        entrance=version.entrance,
        garage_door=version.garage_door,
        base_price_min_cents=version.base_price_min_cents,
        base_price_max_cents=version.base_price_max_cents,
        consistency_warnings=[ConsistencyFindingOut(**w) for w in version.consistency_warnings],
        published_at=version.published_at,
        created_at=version.created_at,
    )


def list_types(db: Session) -> list[TypeSummaryOut]:
    out = []
    for building_type in db.execute(select(BuildingType).order_by(BuildingType.slug)).scalars():
        current = (
            db.get(BuildingTypeVersion, building_type.current_version_id)
            if building_type.current_version_id
            else None
        )
        out.append(
            TypeSummaryOut(
                id=building_type.id,
                slug=building_type.slug,
                family=building_type.family,
                alternatives=building_type.alternatives,
                current_version=_version_out(current, building_type.slug) if current else None,
            )
        )
    return out


def _draft_or_review(db: Session, slug: str, version: int) -> tuple[BuildingType, BuildingTypeVersion]:
    building_type = _building_type(db, slug)
    row = db.execute(
        select(BuildingTypeVersion)
        .where(
            BuildingTypeVersion.building_type_id == building_type.id,
            BuildingTypeVersion.version == version,
        )
        .with_for_update()
    ).scalar_one_or_none()
    if row is None:
        raise Problem(404, "not_found")
    return building_type, row


def get_type_version(db: Session, slug: str, version: int) -> TypeVersionOut:
    building_type = _building_type(db, slug)
    row = db.execute(
        select(BuildingTypeVersion).where(
            BuildingTypeVersion.building_type_id == building_type.id, BuildingTypeVersion.version == version
        )
    ).scalar_one_or_none()
    if row is None:
        raise Problem(404, "not_found")
    return _version_out(row, slug)


def import_type_version(
    db: Session, slug: str, xlsx_data: bytes, dxf_data: bytes, actor_id: str
) -> TypeVersionOut:
    """Neuer Entwurf aus Typdatenblatt und DXF-Umriss (Plan H1 3.2, 3.3, 4.2)."""
    _check_slug(slug)
    try:
        sheet = read_type_workbook(xlsx_data)
    except TypeWorkbookInvalid as exc:
        raise Problem(422, "type_workbook_invalid", detail=str(exc)) from None
    try:
        facade, projection = read_footprints(dxf_data)
    except FootprintDxfInvalid as exc:
        raise Problem(422, "footprint_dxf_invalid", detail=str(exc)) from None

    depth_m = _depth_m(facade, sheet.ridge_direction)
    pitch_finding = check_roof_pitch(
        roof_form=sheet.roof_form,
        declared_pitch_deg=sheet.pitch_deg,
        ridge_height_m=sheet.ridge_height_m,
        eave_height_m=sheet.eave_height_m,
        depth_m=depth_m,
    )
    room_sum = sum(r.area_m2 for r in sheet.rooms)
    storey_area = facade.area * _storey_count(sheet.storeys)
    area_finding = check_room_area_share(room_area_sum_m2=room_sum, storey_footprint_m2=storey_area)
    findings = [f for f in (pitch_finding, area_finding) if f is not None]

    building_type = db.execute(
        select(BuildingType).where(BuildingType.slug == slug).with_for_update()
    ).scalar_one_or_none()
    if building_type is None:
        building_type = BuildingType(slug=slug, created_by=actor_id)
        db.add(building_type)
        db.flush()

    next_version = (
        db.execute(
            select(func.coalesce(func.max(BuildingTypeVersion.version), 0)).where(
                BuildingTypeVersion.building_type_id == building_type.id
            )
        ).scalar_one()
        + 1
    )

    xlsx_sha = hashlib.sha256(xlsx_data).hexdigest()
    dxf_sha = hashlib.sha256(dxf_data).hexdigest()
    xlsx_key = f"catalog/{slug}/{xlsx_sha}.xlsx"
    dxf_key = f"catalog/{slug}/{dxf_sha}.dxf"
    storage.put_bytes(
        xlsx_key, xlsx_data, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    storage.put_bytes(dxf_key, dxf_data, "application/dxf")

    version = BuildingTypeVersion(
        building_type_id=building_type.id,
        version=next_version,
        status="draft",
        name=sheet.name,
        storeys=sheet.storeys,
        roof_form=sheet.roof_form,
        pitch_deg=sheet.pitch_deg,
        ridge_direction=sheet.ridge_direction,
        ridge_height_m=sheet.ridge_height_m,
        eave_height_m=sheet.eave_height_m,
        footprint_facade=[list(p) for p in facade.exterior.coords][:-1],
        footprint_facade_area_m2=round(facade.area, 2),
        footprint_projection=[list(p) for p in projection.exterior.coords][:-1],
        footprint_projection_area_m2=round(projection.area, 2),
        living_area_m2=sheet.living_area_m2,
        rooms_text=sheet.rooms_text,
        rooms=[
            {"name": r.name, "category": r.category, "storey": r.storey, "area_m2": r.area_m2}
            for r in sheet.rooms
        ],
        base_price_min_cents=sheet.base_price_min_eur * 100,
        base_price_max_cents=sheet.base_price_max_eur * 100,
        consistency_warnings=[{"code": f.code, "level": f.level, "detail": f.detail} for f in findings],
        source_xlsx_key=xlsx_key,
        source_xlsx_sha256=xlsx_sha,
        source_dxf_key=dxf_key,
        source_dxf_sha256=dxf_sha,
        created_by=actor_id,
    )
    if sheet.family:
        building_type.family = sheet.family
    db.add(version)
    db.flush()

    price_catalog_version = _draft_price_catalog(db, actor_id)
    _apply_type_base_price(
        db,
        price_catalog_version,
        building_type,
        sheet.base_price_min_eur * 100,
        sheet.base_price_max_eur * 100,
    )
    for entry in sheet.prices:
        surcharge_cents = entry.surcharge_eur * 100
        if entry.kind == "linie":
            package = db.execute(select(Package).where(Package.slug == entry.reference)).scalar_one_or_none()
            if package is None:
                raise Problem(422, "catalog_reference_unknown", detail=f"Linie „{entry.reference}“ unbekannt")
            _apply_package_type_price(db, price_catalog_version, package, building_type, surcharge_cents)
        else:
            module = db.execute(select(Module).where(Module.slug == entry.reference)).scalar_one_or_none()
            if module is None:
                raise Problem(
                    422, "catalog_reference_unknown", detail=f"Option „{entry.reference}“ unbekannt"
                )
            _apply_module_type_price(db, price_catalog_version, module, building_type, surcharge_cents)

    audit.record(
        db,
        actor_type="staff",
        actor_id=actor_id,
        action="building_type_version.import",
        entity_type="building_type_version",
        entity_id=str(version.id),
        after={"slug": slug, "version": next_version, "findings": [f.code for f in findings]},
    )
    db.commit()
    return _version_out(version, slug)


def set_facade_roles(
    db: Session, slug: str, version_no: int, body: FacadeRolesIn, actor_id: str
) -> TypeVersionOut:
    _unused, version = _draft_or_review(db, slug, version_no)
    if version.status == "published":
        raise Problem(409, "version_published")
    edge_count = len(version.footprint_facade)
    for index in body.roles:
        if not index.isdigit() or int(index) >= edge_count:
            raise Problem(422, "validation_error", detail=f"Kantenindex {index} außerhalb des Umrisses")
    version.facade_roles = dict(body.roles)
    db.flush()
    audit.record(
        db,
        actor_type="staff",
        actor_id=actor_id,
        action="building_type_version.facade_roles",
        entity_type="building_type_version",
        entity_id=str(version.id),
        after={"roles": version.facade_roles},
    )
    db.commit()
    return _version_out(version, slug)


def set_placement(
    db: Session, slug: str, version_no: int, body: PlacementIn, actor_id: str
) -> TypeVersionOut:
    _unused, version = _draft_or_review(db, slug, version_no)
    if version.status == "published":
        raise Problem(409, "version_published")
    version.entrance = body.entrance
    version.garage_door = body.garage_door
    db.flush()
    audit.record(
        db,
        actor_type="staff",
        actor_id=actor_id,
        action="building_type_version.placement",
        entity_type="building_type_version",
        entity_id=str(version.id),
        after={"entrance": body.entrance, "garage_door": body.garage_door},
    )
    db.commit()
    return _version_out(version, slug)


_REQUIRED_FOR_PUBLISH = ("name", "storeys", "roof_form", "footprint_facade", "living_area_m2")


def publish_type_version(db: Session, slug: str, version_no: int, actor_id: str) -> TypeVersionOut:
    """Veröffentlichen: Pflichtkennwerte vorhanden, Basispreis gesetzt, keine ungelöste Fehlermeldung der
    Konsistenzprüfung (Plan H1 3.9). Danach unveränderlich (Trigger `forbid_published_modification`)."""
    building_type, version = _draft_or_review(db, slug, version_no)
    if version.status == "published":
        return _version_out(version, slug)
    if version.status == "retired":
        raise Problem(409, "version_retired")
    if version.base_price_min_cents <= 0:
        raise Problem(409, "publish_blocked", detail="Basispreis fehlt")
    errors = [w for w in version.consistency_warnings if w.get("level") == "error"]
    if errors:
        raise Problem(409, "publish_blocked", detail="; ".join(w["detail"] for w in errors))
    version.status = "published"
    version.published_at = utcnow()
    version.published_by = actor_id
    building_type.current_version_id = version.id
    db.flush()
    audit.record(
        db,
        actor_type="staff",
        actor_id=actor_id,
        action="building_type_version.publish",
        entity_type="building_type_version",
        entity_id=str(version.id),
        after={"slug": slug, "version": version_no},
    )
    db.commit()
    return _version_out(version, slug)


def retire_type_version(db: Session, slug: str, version_no: int, actor_id: str) -> TypeVersionOut:
    building_type, version = _draft_or_review(db, slug, version_no)
    version.status = "retired"
    if building_type.current_version_id == version.id:
        building_type.current_version_id = None
    db.flush()
    audit.record(
        db,
        actor_type="staff",
        actor_id=actor_id,
        action="building_type_version.retire",
        entity_type="building_type_version",
        entity_id=str(version.id),
    )
    db.commit()
    return _version_out(version, slug)


def upload_plan_document(
    db: Session, slug: str, filename: str, data: bytes, actor_id: str
) -> PlanDocumentOut:
    building_type = _building_type(db, slug)
    sha = hashlib.sha256(data).hexdigest()
    key = f"catalog/{slug}/plans/{sha}.pdf"
    storage.put_bytes(key, data, "application/pdf")
    doc = PlanDocument(
        building_type_id=building_type.id,
        filename=filename,
        storage_key=key,
        sha256=sha,
        size_bytes=len(data),
        created_by=actor_id,
    )
    db.add(doc)
    db.commit()
    return PlanDocumentOut(
        id=doc.id,
        building_type_id=doc.building_type_id,
        filename=doc.filename,
        size_bytes=doc.size_bytes,
        created_at=doc.created_at,
    )


# --- Linien (Package) ------------------------------------------------------------------------------


def list_packages(db: Session) -> list[PackageVersionOut]:
    out = []
    for package in db.execute(select(Package).order_by(Package.slug)).scalars():
        version = db.get(PackageVersion, package.current_version_id) if package.current_version_id else None
        if version is not None:
            out.append(_package_version_out(version, package.slug))
    return out


def _package_version_out(version: PackageVersion, slug: str) -> PackageVersionOut:
    return PackageVersionOut(
        id=version.id,
        package_id=version.package_id,
        slug=slug,
        version=version.version,
        status=version.status,
        label_de=version.label_de,
        label_fr=version.label_fr,
        scope=version.scope,
        published_at=version.published_at,
    )


def create_package_version(db: Session, slug: str, body: PackageIn, actor_id: str) -> PackageVersionOut:
    _check_slug(slug)
    package = db.execute(select(Package).where(Package.slug == slug).with_for_update()).scalar_one_or_none()
    if package is None:
        package = Package(slug=slug, created_by=actor_id)
        db.add(package)
        db.flush()
    next_version = (
        db.execute(
            select(func.coalesce(func.max(PackageVersion.version), 0)).where(
                PackageVersion.package_id == package.id
            )
        ).scalar_one()
        + 1
    )
    version = PackageVersion(
        package_id=package.id,
        version=next_version,
        status="draft",
        label_de=body.label_de,
        label_fr=body.label_fr,
        scope=body.scope,
        created_by=actor_id,
    )
    db.add(version)
    db.commit()
    return _package_version_out(version, slug)


def publish_package_version(db: Session, slug: str, version_no: int, actor_id: str) -> PackageVersionOut:
    package = db.execute(select(Package).where(Package.slug == slug).with_for_update()).scalar_one_or_none()
    if package is None:
        raise Problem(404, "not_found")
    version = db.execute(
        select(PackageVersion).where(
            PackageVersion.package_id == package.id, PackageVersion.version == version_no
        )
    ).scalar_one_or_none()
    if version is None:
        raise Problem(404, "not_found")
    version.status = "published"
    version.published_at = utcnow()
    version.published_by = actor_id
    package.current_version_id = version.id
    db.commit()
    return _package_version_out(version, slug)


# --- Optionen (Module) ------------------------------------------------------------------------------


def list_modules(db: Session) -> list[ModuleVersionOut]:
    out = []
    for module in db.execute(select(Module).order_by(Module.slug)).scalars():
        version = db.get(ModuleVersion, module.current_version_id) if module.current_version_id else None
        if version is not None:
            out.append(_module_version_out(version, module.slug))
    return out


def _module_version_out(version: ModuleVersion, slug: str) -> ModuleVersionOut:
    return ModuleVersionOut(
        id=version.id,
        module_id=version.module_id,
        slug=slug,
        version=version.version,
        status=version.status,
        label_de=version.label_de,
        label_fr=version.label_fr,
        excludes_slugs=version.excludes_slugs,
        published_at=version.published_at,
    )


def create_module_version(db: Session, slug: str, body: ModuleIn, actor_id: str) -> ModuleVersionOut:
    _check_slug(slug)
    module = db.execute(select(Module).where(Module.slug == slug).with_for_update()).scalar_one_or_none()
    if module is None:
        module = Module(slug=slug, created_by=actor_id)
        db.add(module)
        db.flush()
    next_version = (
        db.execute(
            select(func.coalesce(func.max(ModuleVersion.version), 0)).where(
                ModuleVersion.module_id == module.id
            )
        ).scalar_one()
        + 1
    )
    version = ModuleVersion(
        module_id=module.id,
        version=next_version,
        status="draft",
        label_de=body.label_de,
        label_fr=body.label_fr,
        excludes_slugs=body.excludes_slugs,
        created_by=actor_id,
    )
    db.add(version)
    db.commit()
    return _module_version_out(version, slug)


def publish_module_version(db: Session, slug: str, version_no: int, actor_id: str) -> ModuleVersionOut:
    module = db.execute(select(Module).where(Module.slug == slug).with_for_update()).scalar_one_or_none()
    if module is None:
        raise Problem(404, "not_found")
    version = db.execute(
        select(ModuleVersion).where(ModuleVersion.module_id == module.id, ModuleVersion.version == version_no)
    ).scalar_one_or_none()
    if version is None:
        raise Problem(404, "not_found")
    version.status = "published"
    version.published_at = utcnow()
    version.published_by = actor_id
    module.current_version_id = version.id
    db.commit()
    return _module_version_out(version, slug)


# --- Preiskatalog und RE2020 -------------------------------------------------------------------------


def _draft_price_catalog(db: Session, actor_id: str) -> PriceCatalogVersion:
    """Ein Entwurf je Region wird angelegt und weiterbenutzt, bis er veröffentlicht wird (Plan H1 3.7)."""
    catalog = db.execute(
        select(PriceCatalog).where(PriceCatalog.region == DEFAULT_PRICE_REGION).with_for_update()
    ).scalar_one_or_none()
    if catalog is None:
        catalog = PriceCatalog(region=DEFAULT_PRICE_REGION, created_by=actor_id)
        db.add(catalog)
        db.flush()
    draft = db.execute(
        select(PriceCatalogVersion).where(
            PriceCatalogVersion.price_catalog_id == catalog.id, PriceCatalogVersion.status == "draft"
        )
    ).scalar_one_or_none()
    if draft is not None:
        return draft
    next_version = (
        db.execute(
            select(func.coalesce(func.max(PriceCatalogVersion.version), 0)).where(
                PriceCatalogVersion.price_catalog_id == catalog.id
            )
        ).scalar_one()
        + 1
    )
    draft = PriceCatalogVersion(
        price_catalog_id=catalog.id,
        version=next_version,
        status="draft",
        valid_from=date.today(),
        created_by=actor_id,
    )
    db.add(draft)
    db.flush()
    return draft


def _apply_type_base_price(
    db: Session, pcv: PriceCatalogVersion, building_type: BuildingType, min_cents: int, max_cents: int
) -> None:
    row = db.execute(
        select(TypeBasePrice).where(
            TypeBasePrice.price_catalog_version_id == pcv.id,
            TypeBasePrice.building_type_id == building_type.id,
        )
    ).scalar_one_or_none()
    if row is None:
        db.add(
            TypeBasePrice(
                price_catalog_version_id=pcv.id,
                building_type_id=building_type.id,
                min_cents=min_cents,
                max_cents=max_cents,
            )
        )
    else:
        row.min_cents, row.max_cents = min_cents, max_cents


def _apply_package_type_price(
    db: Session, pcv: PriceCatalogVersion, package: Package, building_type: BuildingType, surcharge_cents: int
) -> None:
    row = db.execute(
        select(PackageTypePrice).where(
            PackageTypePrice.price_catalog_version_id == pcv.id,
            PackageTypePrice.package_id == package.id,
            PackageTypePrice.building_type_id == building_type.id,
        )
    ).scalar_one_or_none()
    if row is None:
        db.add(
            PackageTypePrice(
                price_catalog_version_id=pcv.id,
                package_id=package.id,
                building_type_id=building_type.id,
                surcharge_cents=surcharge_cents,
            )
        )
    else:
        row.surcharge_cents = surcharge_cents


def _apply_module_type_price(
    db: Session, pcv: PriceCatalogVersion, module: Module, building_type: BuildingType, surcharge_cents: int
) -> None:
    row = db.execute(
        select(ModuleTypePrice).where(
            ModuleTypePrice.price_catalog_version_id == pcv.id,
            ModuleTypePrice.module_id == module.id,
            ModuleTypePrice.building_type_id == building_type.id,
        )
    ).scalar_one_or_none()
    if row is None:
        db.add(
            ModuleTypePrice(
                price_catalog_version_id=pcv.id,
                module_id=module.id,
                building_type_id=building_type.id,
                surcharge_cents=surcharge_cents,
            )
        )
    else:
        row.surcharge_cents = surcharge_cents


def _price_catalog_version_out(db: Session, pcv: PriceCatalogVersion) -> PriceCatalogVersionOut:
    types = {t.id: t.slug for t in db.execute(select(BuildingType)).scalars()}
    packages = {p.id: p.slug for p in db.execute(select(Package)).scalars()}
    modules = {m.id: m.slug for m in db.execute(select(Module)).scalars()}
    base_prices = db.execute(
        select(TypeBasePrice).where(TypeBasePrice.price_catalog_version_id == pcv.id)
    ).scalars()
    package_prices = db.execute(
        select(PackageTypePrice).where(PackageTypePrice.price_catalog_version_id == pcv.id)
    ).scalars()
    module_prices = db.execute(
        select(ModuleTypePrice).where(ModuleTypePrice.price_catalog_version_id == pcv.id)
    ).scalars()
    assessments = db.execute(select(EnergyAssessment)).scalars()
    return PriceCatalogVersionOut(
        id=pcv.id,
        price_catalog_id=pcv.price_catalog_id,
        region=DEFAULT_PRICE_REGION,
        version=pcv.version,
        status=pcv.status,
        valid_from=pcv.valid_from,
        vat_rate_default=pcv.vat_rate_default,
        published_at=pcv.published_at,
        base_prices=[
            TypeBasePriceOut(
                building_type_slug=types[b.building_type_id],
                min_cents=b.min_cents,
                max_cents=b.max_cents,
            )
            for b in base_prices
        ],
        package_prices=[
            PackageTypePriceOut(
                package_slug=packages[p.package_id],
                building_type_slug=types[p.building_type_id],
                surcharge_cents=p.surcharge_cents,
            )
            for p in package_prices
        ],
        module_prices=[
            ModuleTypePriceOut(
                module_slug=modules[m.module_id],
                building_type_slug=types[m.building_type_id],
                surcharge_cents=m.surcharge_cents,
            )
            for m in module_prices
        ],
        energy_assessments=[
            EnergyAssessmentOut(
                building_type_slug=types[a.building_type_id],
                package_slug=packages[a.package_id],
                climate_zone=a.climate_zone,
                verdict=a.verdict,
                compliant=a.compliant,
                compliance_surcharge_cents=a.compliance_surcharge_cents,
                measures=a.measures,
            )
            for a in assessments
        ],
    )


def get_draft_price_catalog(db: Session, actor_id: str) -> PriceCatalogVersionOut:
    return _price_catalog_version_out(db, _draft_price_catalog(db, actor_id))


def publish_price_catalog(db: Session, actor_id: str) -> PriceCatalogVersionOut:
    catalog = db.execute(
        select(PriceCatalog).where(PriceCatalog.region == DEFAULT_PRICE_REGION).with_for_update()
    ).scalar_one_or_none()
    if catalog is None:
        raise Problem(404, "not_found")
    draft = db.execute(
        select(PriceCatalogVersion).where(
            PriceCatalogVersion.price_catalog_id == catalog.id, PriceCatalogVersion.status == "draft"
        )
    ).scalar_one_or_none()
    if draft is None:
        raise Problem(404, "not_found")
    draft.status = "published"
    draft.published_at = utcnow()
    draft.published_by = actor_id
    catalog.current_version_id = draft.id
    db.flush()
    audit.record(
        db,
        actor_type="staff",
        actor_id=actor_id,
        action="price_catalog_version.publish",
        entity_type="price_catalog_version",
        entity_id=str(draft.id),
    )
    db.commit()
    return _price_catalog_version_out(db, draft)


def set_energy_assessment(
    db: Session,
    type_slug: str,
    package_slug: str,
    *,
    climate_zone: str,
    verdict: str,
    compliant: bool,
    compliance_surcharge_cents: int | None,
    measures: str | None,
    actor_id: str,
) -> EnergyAssessmentOut:
    building_type = _building_type(db, type_slug)
    package = db.execute(select(Package).where(Package.slug == package_slug)).scalar_one_or_none()
    if package is None:
        raise Problem(404, "not_found", detail=f"Linie „{package_slug}“ nicht gefunden")
    row = db.execute(
        select(EnergyAssessment).where(
            EnergyAssessment.building_type_id == building_type.id, EnergyAssessment.package_id == package.id
        )
    ).scalar_one_or_none()
    if row is None:
        row = EnergyAssessment(building_type_id=building_type.id, package_id=package.id, created_by=actor_id)
        db.add(row)
    row.climate_zone = climate_zone
    row.verdict = verdict
    row.compliant = compliant
    row.compliance_surcharge_cents = compliance_surcharge_cents
    row.measures = measures
    db.commit()
    return EnergyAssessmentOut(
        building_type_slug=type_slug,
        package_slug=package_slug,
        climate_zone=climate_zone,
        verdict=verdict,
        compliant=compliant,
        compliance_surcharge_cents=compliance_surcharge_cents,
        measures=measures,
    )
