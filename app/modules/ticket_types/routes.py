from uuid import UUID

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db_session
from app.modules.ticket_types import schemas
from app.modules.ticket_types.service import TicketTypeService
from app.support.responses import success_response

router = APIRouter(prefix="/ticket-types", tags=["ticket-types"])


@router.get("/events/{event_id}", summary="List ticket types by event")
async def list_ticket_types(
    request: Request,
    event_id: UUID,
    db: AsyncSession = Depends(get_db_session),
):
    data = await TicketTypeService.list_by_event(db, event_id)
    return success_response("List ticket type", data=data, request=request)


@router.get("/{ticket_type_id}", summary="Get ticket type")
async def get_ticket_type(
    request: Request,
    ticket_type_id: UUID,
    db: AsyncSession = Depends(get_db_session),
):
    data = await TicketTypeService.get(db, ticket_type_id)
    return success_response("Ticket type ditemukan", data=data, request=request)


@router.post("", summary="Create ticket type")
async def create_ticket_type(
    request: Request,
    payload: schemas.TicketTypeCreate,
    db: AsyncSession = Depends(get_db_session),
    current_user=Depends(get_current_user),
):
    data = await TicketTypeService.create(db, payload)
    return success_response("Ticket type berhasil dibuat", data=data, request=request)


@router.put("/{ticket_type_id}", summary="Update ticket type")
async def update_ticket_type(
    request: Request,
    ticket_type_id: UUID,
    payload: schemas.TicketTypeUpdate,
    db: AsyncSession = Depends(get_db_session),
    current_user=Depends(get_current_user),
):
    data = await TicketTypeService.update(db, ticket_type_id, payload)
    return success_response("Ticket type berhasil diubah", data=data, request=request)

