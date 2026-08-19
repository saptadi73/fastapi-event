import uuid
from decimal import Decimal

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictException, NotFoundException, ValidationException
from app.modules.payments.models import Order, OrderStatus
from app.modules.participants.models import ParticipantProfile
from app.modules.registrations.models import Registration
from app.modules.store.models import Cart, CartItem, OrderItem, Product


class StoreService:
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
    async def checkout(db: AsyncSession, user_id, event_id):
        registration = (await db.execute(
            select(Registration)
            .join(ParticipantProfile, Registration.participant_id == ParticipantProfile.id)
            .where(Registration.event_id == event_id, ParticipantProfile.user_id == user_id)
            .order_by(Registration.id.desc())
        )).scalars().first()
        if not registration:
            raise ValidationException("REGISTRATION_REQUIRED", "User harus menyelesaikan registrasi event sebelum checkout")
        cart, rows = await StoreService.get_cart(db, user_id, event_id)
        if not rows:
            raise ValidationException("EMPTY_CART", "Cart masih kosong")
        currencies = {product.currency for _, product in rows}
        if len(currencies) != 1:
            raise ValidationException("MIXED_CURRENCY", "Product dalam satu order harus memiliki currency yang sama")
        subtotal = sum((Decimal(str(product.price)) * item.quantity for item, product in rows), Decimal("0"))
        order = Order(user_id=user_id, registration_id=registration.id, order_number=f"ORD-{uuid.uuid4().hex[:16].upper()}", subtotal=subtotal, discount_amount=0, tax_amount=0, service_fee=0, total_amount=subtotal, currency=currencies.pop(), status=OrderStatus.PENDING)
        db.add(order)
        await db.flush()
        for item, product in rows:
            db.add(OrderItem(order_id=order.id, product_id=product.id, product_code=product.code, product_name=product.name, product_type=product.product_type, quantity=item.quantity, unit_price=product.price, currency=product.currency, line_total=Decimal(str(product.price)) * item.quantity))
        await db.execute(delete(CartItem).where(CartItem.cart_id == cart.id))
        await db.commit()
        await db.refresh(order)
        return order, len(rows)
