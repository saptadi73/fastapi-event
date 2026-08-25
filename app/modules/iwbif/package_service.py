import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictException, NotFoundException, ValidationException
from app.modules.store.models import Product
from . import schemas
from .models import DelegatePackage, DelegatePackageFacility, DelegatePackageRate


class DelegatePackageService:
    @staticmethod
    async def catalog(db: AsyncSession, event_id, *, admin=False):
        packages_q = select(DelegatePackage).where(DelegatePackage.event_id == event_id)
        if not admin:
            packages_q = packages_q.where(DelegatePackage.is_active.is_(True))
        packages = list((await db.execute(packages_q.order_by(DelegatePackage.display_order, DelegatePackage.code))).scalars())
        if not packages:
            return schemas.PackageCatalogRead(main_packages=[], additional_packages=[])
        ids = [row.id for row in packages]
        rates_q = select(DelegatePackageRate).where(DelegatePackageRate.delegate_package_id.in_(ids))
        facilities_q = select(DelegatePackageFacility).where(DelegatePackageFacility.delegate_package_id.in_(ids))
        if not admin:
            now = datetime.now(timezone.utc)
            rates_q = rates_q.where(DelegatePackageRate.is_active.is_(True), (DelegatePackageRate.valid_from.is_(None) | (DelegatePackageRate.valid_from <= now)), (DelegatePackageRate.valid_until.is_(None) | (DelegatePackageRate.valid_until > now)))
            facilities_q = facilities_q.where(DelegatePackageFacility.is_active.is_(True))
        rates = list((await db.execute(rates_q.order_by(DelegatePackageRate.is_default.desc(), DelegatePackageRate.amount))).scalars())
        rate_ids = [row.id for row in rates]
        product_rows = list((await db.execute(select(Product.delegate_package_rate_id, Product.id).where(Product.delegate_package_rate_id.in_(rate_ids)))).all()) if rate_ids else []
        product_map = {rate_id: product_id for rate_id, product_id in product_rows}
        facilities = list((await db.execute(facilities_q.order_by(DelegatePackageFacility.display_order, DelegatePackageFacility.name))).scalars())
        rate_map, facility_map = {}, {}
        for row in rates: rate_map.setdefault(row.delegate_package_id, []).append(row)
        for row in facilities: facility_map.setdefault(row.delegate_package_id, []).append(row)
        main, additional = [], []
        for package in packages:
            item = schemas.PackageCatalogItem.model_validate(package).model_copy(update={
                "rates": [schemas.PackageRateRead.model_validate(x).model_copy(update={"product_id": product_map.get(x.id)}) for x in rate_map.get(package.id, [])],
                "facilities": [schemas.PackageFacilityRead.model_validate(x) for x in facility_map.get(package.id, [])],
            })
            (main if package.package_type == "main" else additional).append(item)
        return schemas.PackageCatalogRead(main_packages=main, additional_packages=additional)

    @staticmethod
    async def _package(db, package_id, event_id=None):
        package = await db.get(DelegatePackage, package_id)
        if not package or (event_id and package.event_id != event_id):
            raise NotFoundException("DELEGATE_PACKAGE_NOT_FOUND", "Paket delegate tidak ditemukan")
        return package

    @staticmethod
    async def _sync_product(db, package, rate):
        product = (await db.execute(select(Product).where(Product.delegate_package_rate_id == rate.id))).scalar_one_or_none()
        payable = rate.payment_amount_idr if rate.payment_amount_idr is not None else rate.amount
        currency = "IDR" if rate.payment_amount_idr is not None else rate.currency
        if product is None:
            product = Product(id=uuid.uuid4(), delegate_package_rate_id=rate.id, event_id=package.event_id, code=f"DELEGATE_{package.code}_{rate.occupancy_type}"[:60], product_type="delegate" if package.package_type == "main" else "additional", max_quantity=1)
            db.add(product)
        product.name = f"{package.name} - {rate.name}"
        product.description = package.description
        product.price, product.currency, product.is_active = payable, currency, package.is_active and rate.is_active
        product.metadata_json = {"delegate_package_id": str(package.id), "delegate_package_rate_id": str(rate.id), "package_type": package.package_type, "package_code": package.code, "package_name": package.name, "rate_name": rate.name, "occupancy_type": rate.occupancy_type, "display_amount": str(rate.amount), "display_currency": rate.currency}
        return product

    @staticmethod
    async def create_rate(db, event_id, package_id, payload):
        package = await DelegatePackageService._package(db, package_id, event_id)
        existing_rates = list((await db.execute(select(DelegatePackageRate).where(DelegatePackageRate.delegate_package_id == package.id))).scalars())
        if any(row.occupancy_type == payload.occupancy_type for row in existing_rates):
            raise ConflictException("PACKAGE_RATE_EXISTS", "Tarif occupancy tersebut sudah tersedia")
        existing_count = len(existing_rates)
        values = payload.model_dump()
        if existing_count == 0 and payload.is_active:
            values["is_default"] = True
        if values["is_default"]:
            rows = (await db.execute(select(DelegatePackageRate).where(DelegatePackageRate.delegate_package_id == package.id, DelegatePackageRate.is_default.is_(True)))).scalars()
            for row in rows: row.is_default = False
        rate = DelegatePackageRate(delegate_package_id=package.id, **values)
        db.add(rate); await db.flush(); await DelegatePackageService._sync_product(db, package, rate)
        if rate.is_default:
            package.amount, package.currency, package.payment_amount_idr = rate.amount, rate.currency, rate.payment_amount_idr
        await db.commit(); await db.refresh(rate); return rate

    @staticmethod
    async def update_rate(db, rate_id, payload):
        rate = await db.get(DelegatePackageRate, rate_id, with_for_update=True)
        if not rate: raise NotFoundException("PACKAGE_RATE_NOT_FOUND", "Tarif package tidak ditemukan")
        package = await DelegatePackageService._package(db, rate.delegate_package_id)
        duplicate = (await db.execute(select(DelegatePackageRate.id).where(DelegatePackageRate.delegate_package_id == package.id, DelegatePackageRate.occupancy_type == payload.occupancy_type, DelegatePackageRate.id != rate.id))).first()
        if duplicate:
            raise ConflictException("PACKAGE_RATE_EXISTS", "Tarif occupancy tersebut sudah tersedia")
        if rate.is_default and not payload.is_default:
            replacement = (await db.execute(select(DelegatePackageRate.id).where(DelegatePackageRate.delegate_package_id == package.id, DelegatePackageRate.id != rate.id, DelegatePackageRate.is_default.is_(True), DelegatePackageRate.is_active.is_(True)))).first()
            if not replacement:
                raise ConflictException("DEFAULT_RATE_REQUIRED", "Pilih tarif default pengganti sebelum melepas default saat ini")
        if payload.is_default:
            rows = (await db.execute(select(DelegatePackageRate).where(DelegatePackageRate.delegate_package_id == package.id, DelegatePackageRate.id != rate.id, DelegatePackageRate.is_default.is_(True)))).scalars()
            for row in rows: row.is_default = False
        for key, value in payload.model_dump().items(): setattr(rate, key, value)
        await DelegatePackageService._sync_product(db, package, rate)
        if rate.is_default: package.amount, package.currency, package.payment_amount_idr = rate.amount, rate.currency, rate.payment_amount_idr
        await db.commit(); await db.refresh(rate); return rate

    @staticmethod
    async def disable_rate(db, rate_id):
        rate = await db.get(DelegatePackageRate, rate_id, with_for_update=True)
        if not rate: raise NotFoundException("PACKAGE_RATE_NOT_FOUND", "Tarif package tidak ditemukan")
        if rate.is_default: raise ConflictException("DEFAULT_RATE_REQUIRED", "Tarif default tidak dapat dinonaktifkan sebelum default pengganti dipilih")
        rate.is_active = False
        product = (await db.execute(select(Product).where(Product.delegate_package_rate_id == rate.id))).scalar_one_or_none()
        if product: product.is_active = False
        await db.commit()

    @staticmethod
    async def create_facility(db, event_id, package_id, payload):
        await DelegatePackageService._package(db, package_id, event_id)
        row = DelegatePackageFacility(delegate_package_id=package_id, **payload.model_dump()); db.add(row)
        await db.commit(); await db.refresh(row); return row

    @staticmethod
    async def update_facility(db, facility_id, payload):
        row = await db.get(DelegatePackageFacility, facility_id, with_for_update=True)
        if not row: raise NotFoundException("PACKAGE_FACILITY_NOT_FOUND", "Facility package tidak ditemukan")
        for key, value in payload.model_dump().items(): setattr(row, key, value)
        await db.commit(); await db.refresh(row); return row

    @staticmethod
    async def disable_facility(db, facility_id):
        row = await db.get(DelegatePackageFacility, facility_id, with_for_update=True)
        if not row: raise NotFoundException("PACKAGE_FACILITY_NOT_FOUND", "Facility package tidak ditemukan")
        row.is_active = False; await db.commit()
