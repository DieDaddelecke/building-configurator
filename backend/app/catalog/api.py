"""Endpunkte des Moduls H1 (Plan H1 4.3). Nur für das Büro, kein Kundenschritt.

Rollen wie bei G2 (Plan H1 9 Punkt 2, korrigiert nach Fund `catalog_admin`): `architect` liest überall
mit, `catalog_admin` ist die fachspezifische Editor-Rolle, `ops` verwaltet den Preiskatalog mit.
"""

from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy.orm import Session

from app.catalog import service
from app.catalog.schemas import (
    EnergyAssessmentIn,
    EnergyAssessmentOut,
    FacadeRolesIn,
    ModuleIn,
    ModuleVersionOut,
    PackageIn,
    PackageVersionOut,
    PlacementIn,
    PlanDocumentOut,
    PriceCatalogVersionOut,
    TypeSummaryOut,
    TypeVersionOut,
)
from app.platform.auth.context import Role, StaffPrincipal, require_roles
from app.platform.db import get_db

router = APIRouter(tags=["catalog"])

Reader = Depends(require_roles(Role.architect, Role.catalog_admin, Role.ops))
Editor = Depends(require_roles(Role.architect, Role.catalog_admin))


@router.get("/admin/catalog/types", response_model=list[TypeSummaryOut])
def list_types(staff: StaffPrincipal = Reader, db: Session = Depends(get_db)) -> list[TypeSummaryOut]:
    return service.list_types(db)


@router.post("/admin/catalog/types/{slug}/versions", response_model=TypeVersionOut, status_code=201)
async def import_type_version(
    slug: str,
    xlsx: UploadFile = File(...),
    dxf: UploadFile = File(...),
    staff: StaffPrincipal = Editor,
    db: Session = Depends(get_db),
) -> TypeVersionOut:
    """Neuer Entwurf aus Typdatenblatt (XLSX) und Umriss (DXF), Plan H1 3.2, 3.3."""
    return service.import_type_version(db, slug, await xlsx.read(), await dxf.read(), staff.actor_id)


@router.get("/admin/catalog/types/{slug}/versions/{version}", response_model=TypeVersionOut)
def get_type_version(
    slug: str, version: int, staff: StaffPrincipal = Reader, db: Session = Depends(get_db)
) -> TypeVersionOut:
    return service.get_type_version(db, slug, version)


@router.put("/admin/catalog/types/{slug}/versions/{version}/facade-roles", response_model=TypeVersionOut)
def set_facade_roles(
    slug: str,
    version: int,
    body: FacadeRolesIn,
    staff: StaffPrincipal = Editor,
    db: Session = Depends(get_db),
) -> TypeVersionOut:
    return service.set_facade_roles(db, slug, version, body, staff.actor_id)


@router.put("/admin/catalog/types/{slug}/versions/{version}/placement", response_model=TypeVersionOut)
def set_placement(
    slug: str,
    version: int,
    body: PlacementIn,
    staff: StaffPrincipal = Editor,
    db: Session = Depends(get_db),
) -> TypeVersionOut:
    return service.set_placement(db, slug, version, body, staff.actor_id)


@router.post("/admin/catalog/types/{slug}/versions/{version}/publish", response_model=TypeVersionOut)
def publish_type_version(
    slug: str, version: int, staff: StaffPrincipal = Editor, db: Session = Depends(get_db)
) -> TypeVersionOut:
    return service.publish_type_version(db, slug, version, staff.actor_id)


@router.post("/admin/catalog/types/{slug}/versions/{version}/retire", response_model=TypeVersionOut)
def retire_type_version(
    slug: str, version: int, staff: StaffPrincipal = Editor, db: Session = Depends(get_db)
) -> TypeVersionOut:
    return service.retire_type_version(db, slug, version, staff.actor_id)


@router.post("/admin/catalog/types/{slug}/plan-document", response_model=PlanDocumentOut, status_code=201)
async def upload_plan_document(
    slug: str, file: UploadFile = File(...), staff: StaffPrincipal = Editor, db: Session = Depends(get_db)
) -> PlanDocumentOut:
    """Grundriss-PDF als reiner Upload, ohne Auswertung (Plan H1 3.6)."""
    filename = file.filename or "grundriss.pdf"
    return service.upload_plan_document(db, slug, filename, await file.read(), staff.actor_id)


@router.get("/admin/catalog/lines", response_model=list[PackageVersionOut])
def list_packages(staff: StaffPrincipal = Reader, db: Session = Depends(get_db)) -> list[PackageVersionOut]:
    return service.list_packages(db)


@router.post("/admin/catalog/lines/{slug}/versions", response_model=PackageVersionOut, status_code=201)
def create_package_version(
    slug: str, body: PackageIn, staff: StaffPrincipal = Editor, db: Session = Depends(get_db)
) -> PackageVersionOut:
    return service.create_package_version(db, slug, body, staff.actor_id)


@router.post("/admin/catalog/lines/{slug}/versions/{version}/publish", response_model=PackageVersionOut)
def publish_package_version(
    slug: str, version: int, staff: StaffPrincipal = Editor, db: Session = Depends(get_db)
) -> PackageVersionOut:
    return service.publish_package_version(db, slug, version, staff.actor_id)


@router.get("/admin/catalog/options", response_model=list[ModuleVersionOut])
def list_modules(staff: StaffPrincipal = Reader, db: Session = Depends(get_db)) -> list[ModuleVersionOut]:
    return service.list_modules(db)


@router.post("/admin/catalog/options/{slug}/versions", response_model=ModuleVersionOut, status_code=201)
def create_module_version(
    slug: str, body: ModuleIn, staff: StaffPrincipal = Editor, db: Session = Depends(get_db)
) -> ModuleVersionOut:
    return service.create_module_version(db, slug, body, staff.actor_id)


@router.post("/admin/catalog/options/{slug}/versions/{version}/publish", response_model=ModuleVersionOut)
def publish_module_version(
    slug: str, version: int, staff: StaffPrincipal = Editor, db: Session = Depends(get_db)
) -> ModuleVersionOut:
    return service.publish_module_version(db, slug, version, staff.actor_id)


@router.get("/admin/catalog/price-catalog/draft", response_model=PriceCatalogVersionOut)
def get_draft_price_catalog(
    staff: StaffPrincipal = Reader, db: Session = Depends(get_db)
) -> PriceCatalogVersionOut:
    """Entwurf des Preiskatalogs, mit den aus Typ-Importen übernommenen Preisen (Plan H1 3.7)."""
    return service.get_draft_price_catalog(db, staff.actor_id)


@router.post("/admin/catalog/price-catalog/publish", response_model=PriceCatalogVersionOut)
def publish_price_catalog(
    staff: StaffPrincipal = Editor, db: Session = Depends(get_db)
) -> PriceCatalogVersionOut:
    return service.publish_price_catalog(db, staff.actor_id)


@router.put(
    "/admin/catalog/types/{type_slug}/energy-assessment/{package_slug}", response_model=EnergyAssessmentOut
)
def set_energy_assessment(
    type_slug: str,
    package_slug: str,
    body: EnergyAssessmentIn,
    staff: StaffPrincipal = Editor,
    db: Session = Depends(get_db),
) -> EnergyAssessmentOut:
    return service.set_energy_assessment(
        db,
        type_slug,
        package_slug,
        climate_zone=body.climate_zone,
        verdict=body.verdict,
        compliant=body.compliant,
        compliance_surcharge_cents=body.compliance_surcharge_cents,
        measures=body.measures,
        actor_id=staff.actor_id,
    )
