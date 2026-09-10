from sqlalchemy import String, cast, func, or_, select


def search_filter(search: str | None, *columns):
    """Case-insensitive literal substring search; blank input matches all rows."""
    term = (search or "").strip()
    if not term:
        return True
    return or_(*(cast(column, String).icontains(term, autoescape=True) for column in columns))


def pagination_meta(page: int, size: int, total: int) -> dict:
    return {"page": page, "size": size, "total": total, "pages": (total + size - 1) // size}


async def paginate_query(db, stmt, page: int, size: int):
    count = select(func.count()).select_from(stmt.order_by(None).subquery())
    total = int(await db.scalar(count) or 0)
    rows = (await db.execute(stmt.offset((page - 1) * size).limit(size))).scalars().all()
    return rows, pagination_meta(page, size, total)


def resolve_pagination(page: int | None, size: int | None, limit: int, offset: int):
    """Explicit page/size take precedence over legacy limit/offset."""
    if page is not None or size is not None:
        page, size = page or 1, size or 20
        return page, size, (page - 1) * size
    return offset // limit + 1, limit, offset
