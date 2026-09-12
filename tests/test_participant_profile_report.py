import asyncio
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.core.dependencies import require_admin
from app.core.exceptions import NotFoundException
from app.modules.participants.profile_report import participant_profile_report, record
from app.modules.participants.reporting_routes import router
from app.modules.participants.models import ParticipantProfile
from app.modules.users.models import User
from app.modules.registrations.models import Registration
from app.modules.events.models import Event
from app.modules.iwbif.models import Company, DelegateRegistrationDetail, RegistrationDocument, ExhibitorRegistration
from app.modules.business_matching.models import BusinessMatchingProfile


def test_combined_profile_preserves_full_forms_and_excludes_secrets():
    participant_id, user_id, event_id, registration_id = [uuid4() for _ in range(4)]
    profile = ParticipantProfile(id=participant_id, user_id=user_id, full_name='Profile name', biography='Bio')
    user = User(id=user_id, full_name='Account name', email='test@example.com', country='ID', password_hash='NEVER EXPORT')
    delegate = DelegateRegistrationDetail(registration_id=registration_id, job_title='Director', business_objectives='Export', need_airport_pickup=False, medical_condition='Assistance requested', preferred_countries=['ID', 'SG'])
    registry = {
        Registration: [Registration(id=registration_id, participant_id=participant_id, event_id=event_id, registration_number='REG-1')],
        Company: [Company(id=uuid4(), participant_id=participant_id, name='Company', country='ID', address='Full address')],
        ExhibitorRegistration: [ExhibitorRegistration(id=uuid4(), participant_id=participant_id, event_id=event_id, products_to_display='Products', booth_size_requested='3x3')],
        BusinessMatchingProfile: [BusinessMatchingProfile(id=uuid4(), participant_id=participant_id, event_id=event_id, production_capacity='100/month', business_needs=['Distributor'], preferred_slot_ids=[])],
        RegistrationDocument: [RegistrationDocument(id=uuid4(), original_filename='passport.pdf', storage_key='PRIVATE FILE PATH')],
    }

    class DB:
        async def get(self, model, key):
            return {ParticipantProfile: profile, User: user, DelegateRegistrationDetail: delegate, Event: Event(id=event_id, name='Test Event')}.get(model)

        async def execute(self, statement):
            model = statement.column_descriptions[0]['entity']
            # Every collection is constrained to this participant or their registration.
            assert statement.whereclause is not None
            return SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: registry.get(model, [])))

    data = asyncio.run(participant_profile_report(DB(), participant_id))
    assert data['account']['full_name'] == 'Account name'
    assert data['profile']['full_name'] == 'Profile name'
    assert 'password_hash' not in data['account']
    detail = data['registrations'][0]['delegate']
    assert detail['medical_condition'] == 'Assistance requested'
    assert detail['need_airport_pickup'] is False
    assert detail['preferred_countries'] == ['ID', 'SG']
    assert data['companies'][0]['address'] == 'Full address'
    assert data['exhibitors'][0]['exhibitor']['booth_size_requested'] == '3x3'
    assert data['business_matching'][0]['business']['production_capacity'] == '100/month'
    assert 'storage_key' not in data['registrations'][0]['documents'][0]
    assert 'storage_key' not in data['exhibitors'][0]['documents'][0]


def test_missing_participant_and_empty_record():
    class DB:
        async def get(self, model, key):
            return None
    with pytest.raises(NotFoundException):
        asyncio.run(participant_profile_report(DB(), uuid4()))
    assert record(None) is None


def test_complete_profile_route_requires_admin():
    route = next(route for route in router.routes if route.path.endswith('/{participant_id}/profile'))
    assert require_admin in [dependency.call for dependency in route.dependant.dependencies]
