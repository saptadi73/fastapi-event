import uuid
from decimal import Decimal

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictException, NotFoundException, ValidationException
from app.modules.payments.models import Order, OrderStatus
from app.modules.store.models import Cart, CartItem, OrderItem, Product
from app.modules.iwbif.models import DelegatePackage, DelegatePackageRate


class StoreService:
    @staticmethod
    def localized_product_snapshot(product, translation):
        metadata = dict(product.metadata_json or {})
        metadata["content_locale"] = translation.locale if translation else "source"
        name = translation.fields.get("name", product.name) if translation else product.name
        return name, metadata

    @staticmethod
    async def get_cart(db: AsyncSession, user_id, event_id):
        cart = (await db.execute(select(Cart).where(Cart.user_id == user_id, Cart.event_id == event_id))).scalar_one_or_none()
        if not cart:
            cart = Cart(user_id=user_id, event_id=event_id)
            db.add(cart)
            await db.flush()
        rows = (await db.execute(select(CartItem, Product).join(Product, Product.id == CartItem.product_id).where(CartItem.cart_id == cart.id).order_by(Product.product_type, Product.name))).all()
        return cart, rows

    @staticmethod
    async def add_item(db: AsyncSession, user_id, event_id, payload):
        product = await db.get(Product, payload.product_id)
        if not product or product.event_id != event_id or not product.is_active:
            raise NotFoundException("PRODUCT_NOT_FOUND", "Product tidak ditemukan atau tidak aktif")
        cart, rows = await StoreService.get_cart(db, user_id, event_id)
        if product.delegate_package_rate_id:
            rate = await db.get(DelegatePackageRate, product.delegate_package_rate_id)
            package = await db.get(DelegatePackage, rate.delegate_package_id) if rate else None
            if not rate or not package or not rate.is_active or not package.is_active:
                raise ValidationException("PACKAGE_RATE_INACTIVE", "Tarif package tidak aktif")
            if payload.quantity != 1:
                raise ValidationException("PACKAGE_QUANTITY_INVALID", "Package delegate hanya dapat dipilih satu kali")
            # Radio behavior for main packages and occupancy variants. Adding a
            # new rate replaces the previous selection in the same group.
            existing = (await db.execute(
                select(CartItem, Product, DelegatePackageRate, DelegatePackage)
                .join(Product, Product.id == CartItem.product_id)
                .join(DelegatePackageRate, DelegatePackageRate.id == Product.delegate_package_rate_id)
                .join(DelegatePackage, DelegatePackage.id == DelegatePackageRate.delegate_package_id)
                .where(CartItem.cart_id == cart.id)
            )).all()
            replace_ids = [item.id for item, _, _, selected_package in existing if selected_package.id == package.id or (package.package_type == "main" and selected_package.package_type == "main")]
            if replace_ids:
                await db.execute(delete(CartItem).where(CartItem.id.in_(replace_ids)))
        item = (await db.execute(select(CartItem).where(CartItem.cart_id == cart.id, CartItem.product_id == product.id))).scalar_one_or_none()
        quantity = (item.quantity if item else 0) + payload.quantity
        if product.max_quantity and quantity > product.max_quantity:
            raise ValidationException("PRODUCT_QUANTITY_LIMIT", "Jumlah product melebihi batas")
        if item:
            item.quantity = quantity
        else:
            db.add(CartItem(cart_id=cart.id, product_id=product.id, quantity=quantity))
        await db.commit()
        return await StoreService.get_cart(db, user_id, event_id)

    @staticmethod
    async def remove_item(db: AsyncSession, user_id, event_id, product_id):
        cart, _ = await StoreService.get_cart(db, user_id, event_id)
        result = await db.execute(delete(CartItem).where(CartItem.cart_id == cart.id, CartItem.product_id == product_id))
        if not result.rowcount:
            raise NotFoundException("CART_ITEM_NOT_FOUND", "Item tidak ditemukan di cart")
        await db.commit()
        return await StoreService.get_cart(db, user_id, event_id)

    @staticmethod
    async def checkout(db: AsyncSession, user_id, event_id, locale="en"):
        cart = (await db.execute(
            select(Cart)
            .where(Cart.user_id == user_id, Cart.event_id == event_id)
            .with_for_update()
        )).scalar_one_or_none()
        if not cart:
            raise ValidationException("EMPTY_CART", "Cart masih kosong")
        rows = (await db.execute(
            select(CartItem, Product)
            .join(Product, Product.id == CartItem.product_id)
            .where(CartItem.cart_id == cart.id)
            .order_by(Product.product_type, Product.name)
        )).all()
        if not rows:
            raise ValidationException("EMPTY_CART", "Cart masih kosong")
        linked = [(item, product) for item, product in rows if product.delegate_package_rate_id]
        if linked:
            selections = []
            for item, product in linked:
                rate = await db.get(DelegatePackageRate, product.delegate_package_rate_id)
                package = await db.get(DelegatePackage, rate.delegate_package_id) if rate else None
                if not rate or not package or not rate.is_active or not package.is_active or item.quantity != 1:
                    raise ValidationException("INVALID_DELEGATE_SELECTION", "Pilihan package atau tarif tidak valid")
                selections.append((package, rate))
            mains = [(package, rate) for package, rate in selections if package.package_type == "main"]
            if len(mains) != 1:
                raise ValidationException("MAIN_PACKAGE_REQUIRED", "Tepat satu Main Package wajib dipilih")
            if len({package.id for package, _ in selections}) != len(selections):
                raise ValidationException("DUPLICATE_PACKAGE_SELECTION", "Satu package hanya boleh memiliki satu pilihan tarif")
        currencies = {product.currency for _, product in rows}
        if len(currencies) != 1:
            raise ValidationException("MIXED_CURRENCY", "Product dalam satu order harus memiliki currency yang sama")
        subtotal = sum((Decimal(str(product.price)) * item.quantity for item, product in rows), Decimal("0"))
        order = Order(user_id=user_id, registration_id=None, event_id=event_id, order_number=f"ORD-{uuid.uuid4().hex[:16].upper()}", subtotal=subtotal, discount_amount=0, tax_amount=0, service_fee=0, total_amount=subtotal, currency=currencies.pop(), status=OrderStatus.PENDING)
        db.add(order)
        await db.flush()
        from app.modules.content_translations.service import translation_map
        product_translations = await translation_map(db, "product", [product.id for _, product in rows], locale)
        for item, product in rows:
            translation = product_translations.get(product.id)
            product_name, metadata = StoreService.localized_product_snapshot(product, translation)
            db.add(OrderItem(order_id=order.id, product_id=product.id, product_code=product.code, product_name=product_name, product_type=product.product_type, quantity=item.quantity, unit_price=product.price, currency=product.currency, line_total=Decimal(str(product.price)) * item.quantity, metadata_json=metadata))
        await db.execute(delete(CartItem).where(CartItem.cart_id == cart.id))
        await db.commit()
        await db.refresh(order)
        return order, len(rows)
