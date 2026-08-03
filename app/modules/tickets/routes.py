from uuid import UUID

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db_session
from app.modules.tickets import schemas
from app.modules.tickets.service import TicketService
from app.support.responses import success_response

router = APIRouter(prefix="/tickets", tags=["tickets"])


@router.get("/me", summary="List my tickets")
async def list_my_tickets(
    request: Request,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    data = await TicketService.get_user_tickets(db, current_user.id)
    return success_response("Tickets user ditemukan", data=data, request=request)


@router.post("", summary="Issue ticket by registration")
async def issue_ticket(
    request: Request,
    payload: schemas.TicketIssueRequest,
    db: AsyncSession = Depends(get_db_session),
):
    ticket = await TicketService.issue_for_registration(db, payload.registration_id)
    return success_response("Ticket diterbitkan", data=ticket, request=request)


@router.get("/{ticket_id}/qr", summary="Get ticket QR")
async def ticket_qr(
    request: Request,
    ticket_id: UUID,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    data = await TicketService.get_user_ticket_qr(db, ticket_id, current_user.id)
    return success_response("QR ticket tersedia", data=data, request=request)


@router.post("/{ticket_id}/reissue", summary="Reissue ticket")
async def ticket_reissue(
    request: Request,
    ticket_id: UUID,
    db: AsyncSession = Depends(get_db_session),
):
    ticket = await TicketService.reissue(db, ticket_id)
    return success_response("Ticket direissue", data=ticket, request=request)
