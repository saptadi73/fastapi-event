# Backend Technical Reference --- Business Matching & Messaging

**Project:** Event Portal\
**Backend:** FastAPI\
**Database:** PostgreSQL\
**Version:** 1.0

## 1. Tujuan

Dokumen ini menjadi acuan pengembangan backend fitur **Business
Matching**. Siklus utama:

**Discover → Match → Communicate → Request Meeting → Schedule → Confirm
→ Meet → Follow-up**

Backend mencakup profile matching, discovery, recommendation, messaging,
meeting request, scheduling, conflict checking, notification, email
reminder, organizer-assisted matching, reporting, dan audit trail.

## 2. Struktur Modul FastAPI

Business logic tidak ditempatkan di route.

``` text
app/modules/
├── business_matching/
│   ├── routes/
│   ├── schemas/
│   ├── models/
│   ├── repositories/
│   ├── services/
│   │   ├── recommendation_service.py
│   │   ├── meeting_service.py
│   │   └── scheduling_service.py
│   └── dependencies.py
├── messaging/
│   ├── routes/
│   ├── schemas/
│   ├── models/
│   ├── repositories/
│   └── services/
└── notifications/
    ├── routes/
    ├── schemas/
    ├── models/
    ├── services/
    └── tasks/
```

## 3. Domain

1.  Business Matching Profile
2.  Participant Discovery
3.  Recommendation Engine
4.  Conversation & Messaging
5.  Meeting Request
6.  Meeting Scheduling
7.  Venue/Room/Table Allocation
8.  Notification & Email
9.  Organizer Assisted Matching
10. Reporting & Audit

## 4. Business Matching Profile

### Ownership dan identitas organisasi

Current user ditentukan oleh access token. Backend mencari participant melalui
`participants.user_id`; frontend tidak boleh mengirim participant ID untuk
mengubah identitas pemilik profile. Untuk profile IWBIF, registrasi terkait wajib
berstatus `confirmed`.

Data organisasi canonical disimpan di `companies` dan direferensikan oleh
delegate registration, business matching profile, serta exhibitor. Nama dan
kontak yang ikut tersimpan pada profile merupakan snapshot/presentation data,
bukan identitas organisasi baru.

Table `business_matching_profiles`:

  Field                    Type           Keterangan
  ------------------------ -------------- ------------------------
  id                       UUID           PK
  event_id                 UUID           FK event
  participant_id           UUID           FK participant
  registration_id          UUID           FK registration, unique
  company_id               UUID           FK company
  organization_name        varchar        Organisasi
  country_code             varchar        Negara
  organization_type        varchar/enum   Tipe organisasi
  position_title           varchar        Jabatan
  short_description        text           Deskripsi
  target_market            jsonb          Target market
  preferred_regions        jsonb          Wilayah diminati
  available_for_matching   boolean        Aktif matching
  visibility               enum           all/recommended/hidden
  allow_messages           boolean        Izin message
  allow_meeting_requests   boolean        Izin meeting
  created_at               timestamptz    Audit
  updated_at               timestamptz    Audit

Gunakan master/tag relational table untuk `business_interests`,
`business_sectors`, `technology_interests`, `partnership_types`,
`business_offerings`, dan `business_needs`.

Pilihan jadwal IWBIF tersimpan pada `business_matching_profile_slots`; backend
memvalidasi bahwa setiap slot aktif dan berasal dari event registrasi yang sama.

## 5. Participant Discovery

``` http
GET /api/v1/events/{event_id}/business-matching/participants
```

Filter: country, organization type, sector, business interest,
technology interest, offering, looking-for, dan partnership type.

Backend hanya menampilkan participant pada event yang sama, aktif,
membuka business matching, memenuhi privacy policy, bukan current
participant, dan tidak memiliki block relation.

## 6. Recommendation Engine

MVP menggunakan rule-based scoring:

  Faktor                        Bobot
  --------------------------- -------
  Looking For ↔ Offering           35
  Business Interest                25
  Industry/Sector                  15
  Technology Interest              10
  Target Market                    10
  Country/Region Preference         5

Response harus menyertakan `match_score` dan `match_reasons`.

``` json
{
  "participant_id": "uuid",
  "match_score": 91,
  "match_reasons": [
    "Offering matches your business need",
    "Shared interest: Food & Beverage Distribution"
  ]
}
```

``` http
GET /api/v1/events/{event_id}/business-matching/recommendations
```

Recommendation engine dibuat sebagai service terpisah agar nantinya
dapat diganti dengan semantic/AI recommendation.

## 7. Conversation & Messaging

### `conversations`

``` text
id UUID PK
event_id UUID FK
created_by UUID FK
status enum(active, archived, blocked)
last_message_at timestamptz
created_at timestamptz
updated_at timestamptz
```

### `conversation_participants`

``` text
id UUID PK
conversation_id UUID FK
participant_id UUID FK
last_read_at timestamptz
is_archived boolean
is_muted boolean
```

### `messages`

``` text
id UUID PK
conversation_id UUID FK
sender_participant_id UUID FK
message_type enum
body text
meeting_id UUID nullable
reply_to_message_id UUID nullable
created_at timestamptz
edited_at timestamptz nullable
deleted_at timestamptz nullable
```

`message_type`: `text`, `system`, `meeting_request`, `meeting_accepted`,
`meeting_declined`, `meeting_confirmed`, `meeting_reschedule`,
`meeting_cancelled`, `contact_card`, `attachment`.

Unread message dapat dihitung menggunakan
`conversation_participants.last_read_at`.

API:

``` http
GET  /api/v1/events/{event_id}/conversations
POST /api/v1/events/{event_id}/conversations
GET  /api/v1/conversations/{id}/messages
POST /api/v1/conversations/{id}/messages
POST /api/v1/conversations/{id}/read
POST /api/v1/conversations/{id}/archive
```

Backend wajib memvalidasi authentication, event membership, conversation
membership, privacy `allow_messages`, dan block relation.

## 8. Real-Time Messaging

MVP dapat memakai REST + polling. Jika diperlukan real-time:

``` text
WS /api/v1/ws/conversations/{conversation_id}
```

WebSocket dapat membawa new-message, read-update, meeting-status-update,
dan notification badge. PostgreSQL tetap **source of truth**.

Untuk multi-worker/multi-instance gunakan Redis Pub/Sub atau broker
sejenis; jangan hanya memakai in-memory connection manager.

## 9. Meeting

### `meetings`

``` text
id UUID PK
event_id UUID FK
conversation_id UUID nullable
requester_participant_id UUID FK
recipient_participant_id UUID FK
purpose varchar/enum
topic varchar
description text
status enum
confirmed_slot_id UUID nullable
venue_resource_id UUID nullable
created_at timestamptz
updated_at timestamptz
confirmed_at timestamptz nullable
completed_at timestamptz nullable
cancelled_at timestamptz nullable
```

Status: `requested`, `accepted`, `scheduling`, `confirmed`, `completed`,
`declined`, `cancelled`, `reschedule_requested`, `no_show`.

Sediakan
`meeting_participants(meeting_id, participant_id, role, response_status)`
agar kelak mendukung group meeting.

## 10. Slot Proposal dan Matching Session

`meeting_slot_proposals`:

``` text
id UUID
meeting_id UUID
slot_id UUID
proposed_by UUID
status enum(proposed, accepted, rejected, expired)
created_at timestamptz
```

`matching_sessions`:

``` text
id UUID
event_id UUID
name varchar
session_date date
start_time time
end_time time
slot_duration_minutes integer
status enum
```

`meeting_slots`:

``` text
id UUID
matching_session_id UUID
starts_at timestamptz
ends_at timestamptz
status enum(available, disabled)
```

Slot digenerate otomatis berdasarkan window session dan durasi.

## 11. Venue, Room, dan Table

`meeting_venues`:

``` text
id UUID
event_id UUID
name varchar
location_description text
```

`meeting_resources`:

``` text
id UUID
venue_id UUID
resource_type enum(room, table, booth, online)
code varchar
name varchar
capacity integer
is_active boolean
```

Resource generik lebih fleksibel daripada table terpisah untuk room dan
table.

## 12. Conflict Checking

Sebelum status `confirmed`, backend wajib memeriksa secara atomik:

1.  requester availability;
2.  recipient availability;
3.  participant tambahan;
4.  slot availability;
5.  room/table/resource availability.

Tidak boleh ada dua confirmed meeting yang overlap untuk participant
atau resource yang sama.

``` python
async def confirm_meeting(meeting_id, slot_id, resource_id):
    async with transaction:
        lock_required_rows()
        validate_meeting_status()
        validate_slot_active()
        validate_participant_availability()
        validate_resource_availability()
        assign_slot()
        assign_resource()
        set_status("confirmed")
        create_system_message()
        create_notifications()
```

Gunakan transaction dan database locking/constraint untuk mencegah race
condition.

## 13. Meeting State Machine

``` text
requested → accepted / declined
accepted → scheduling / confirmed
scheduling → confirmed / cancelled
confirmed → reschedule_requested / cancelled / completed / no_show
reschedule_requested → confirmed / cancelled
```

Jangan sediakan update status generik dari frontend. Gunakan command
endpoint:

``` http
POST /meetings/{id}/accept
POST /meetings/{id}/decline
POST /meetings/{id}/confirm
POST /meetings/{id}/request-reschedule
POST /meetings/{id}/cancel
POST /meetings/{id}/complete
```

Aktivitas meeting menghasilkan `system message` yang menyimpan
`meeting_id`.

## 14. Notification Center

`notifications`:

``` text
id UUID
user_id UUID
event_id UUID
type varchar/enum
title varchar
body text
entity_type varchar
entity_id UUID
is_read boolean
created_at timestamptz
read_at timestamptz nullable
```

Type: `new_message`, `meeting_request`, `meeting_accepted`,
`meeting_declined`, `meeting_reschedule`, `meeting_confirmed`,
`meeting_cancelled`, `meeting_reminder`, `organizer_recommendation`.

``` http
GET  /api/v1/notifications
GET  /api/v1/notifications/unread-count
POST /api/v1/notifications/{id}/read
POST /api/v1/notifications/read-all
```

## 15. Email & Reminder

Email diproses sebagai background job, bukan menahan HTTP request.

Kirim email untuk meeting request, accepted, declined, reschedule,
confirmation, cancellation, dan reminder. Untuk chat gunakan delayed
notification/digest bila pesan belum dibaca, bukan email setiap message.

Domain event yang disarankan:

``` text
MeetingRequested
MeetingAccepted
MeetingConfirmed
MeetingCancelled
NewUnreadMessage
```

Handler dapat membuat portal notification, queue email, system message,
dan WebSocket event.

Reminder dapat dijalankan H-1 dan 30 menit sebelum meeting. Simpan
`notification_deliveries` untuk mencegah pengiriman ganda.

## 16. Block, Report, dan Privacy

Sediakan:

``` text
participant_blocks
participant_reports
```

Jika A memblokir B, pasangan tersebut tidak boleh saling mengirim
message/meeting request dan tidak muncul dalam recommendation.

Backend wajib menerapkan JWT authentication, event-level authorization,
participant ownership, conversation membership, organizer-role
validation, rate limiting, input sanitization, dan tidak mengekspos
email/phone tanpa izin.

Organizer dapat melihat metadata meeting untuk operasional, tetapi tidak
otomatis membaca isi conversation privat.

## 17. Organizer Assisted Matching

`organizer_match_recommendations`:

``` text
id UUID
event_id UUID
participant_a_id UUID
participant_b_id UUID
recommended_by UUID
reason text
participant_a_response enum
participant_b_response enum
status enum
created_at timestamptz
```

Jika kedua pihak `interested`, sistem dapat membuka conversation dan
scheduling.

## 18. Audit Trail

Audit aktivitas kritis: request, accept/decline, perubahan
slot/resource, reschedule, cancellation, organizer override,
block/report.

``` text
business_matching_audit_logs
- id UUID
- event_id UUID
- actor_user_id UUID
- action varchar
- entity_type varchar
- entity_id UUID
- old_values jsonb nullable
- new_values jsonb nullable
- created_at timestamptz
```

Isi pesan privat tidak perlu masuk audit log.

## 19. Index Database

Index minimum:

``` text
business_matching_profiles(event_id, participant_id)
business_matching_profiles(event_id, available_for_matching)
conversations(event_id, last_message_at)
conversation_participants(participant_id, conversation_id)
messages(conversation_id, created_at)
meetings(event_id, status)
meetings(requester_participant_id, status)
meetings(recipient_participant_id, status)
meetings(confirmed_slot_id)
meetings(venue_resource_id, confirmed_slot_id)
notifications(user_id, is_read, created_at)
```

## 20. Standard API Response

``` json
{
  "status": "success",
  "message": "Meeting request created successfully",
  "data": {
    "id": "uuid",
    "status": "requested"
  }
}
```

Gunakan HTTP status semantik: `200`, `201`, `400`, `401`, `403`, `404`,
`409`, `422`. Gunakan **409 Conflict** untuk bentrok slot/resource.

## 21. Endpoint Summary

### Profile & Discovery

``` http
GET /events/{event_id}/business-matching/profile
PUT /events/{event_id}/business-matching/profile
GET /events/{event_id}/business-matching/participants
GET /events/{event_id}/business-matching/recommendations
```

### Conversation

``` http
GET  /events/{event_id}/conversations
POST /events/{event_id}/conversations
GET  /conversations/{id}/messages
POST /conversations/{id}/messages
POST /conversations/{id}/read
```

### Meeting

``` http
POST /events/{event_id}/meetings
GET  /events/{event_id}/meetings
GET  /meetings/{id}
POST /meetings/{id}/accept
POST /meetings/{id}/decline
POST /meetings/{id}/confirm
POST /meetings/{id}/request-reschedule
POST /meetings/{id}/cancel
POST /meetings/{id}/complete
```

### Scheduling

``` http
GET /events/{event_id}/matching-sessions
GET /events/{event_id}/meeting-slots
GET /events/{event_id}/meeting-resources
GET /events/{event_id}/availability
```

## 22. Transaction Boundary Penting

Gunakan transaction untuk:

-   create conversation;
-   send message + update `last_message_at`;
-   accept meeting;
-   confirm meeting;
-   reschedule;
-   cancel meeting;
-   allocate/release resource.

`confirm meeting` adalah operasi paling kritis karena menyentuh meeting,
participant schedule, slot, resource, system message, notification, dan
audit.

## 23. MVP vs Phase 2

### MVP

-   Profile matching
-   Participant directory/filter
-   Rule-based recommendation
-   One-to-one messaging
-   Read/unread
-   Meeting request
-   Accept/decline
-   Slot proposal
-   Conflict checking
-   Room/table allocation
-   Notification center
-   Email notification
-   Reminder
-   Organizer monitoring
-   Audit log

### Phase 2

-   WebSocket real-time messaging
-   Redis Pub/Sub
-   Attachment/brochure
-   Business card exchange
-   AI/semantic recommendation
-   Organizer-assisted matching
-   Meeting feedback
-   Advanced analytics

## 24. Testing Minimum

Unit test:

-   scoring recommendation;
-   authorization;
-   meeting state transition;
-   conflict detection;
-   privacy/block rules.

Integration test:

-   create conversation → send message;
-   request → accept → confirm meeting;
-   concurrent booking pada slot/resource yang sama;
-   reschedule;
-   cancellation;
-   notification generation.

Security test:

-   participant mengakses conversation orang lain;
-   cross-event access;
-   hidden participant;
-   blocked participant;
-   direct status manipulation.

## 25. Acceptance Criteria Backend

Backend dianggap memenuhi rancangan dasar jika:

-   participant hanya dapat mengakses data sesuai event dan permission;
-   recommendation memberikan score dan alasan;
-   message tersimpan persisten;
-   unread count konsisten;
-   meeting mengikuti state machine;
-   tidak terjadi double-booking participant/resource;
-   perubahan meeting tercermin sebagai system message;
-   notification tercipta pada event penting;
-   email dapat diproses asynchronous;
-   organizer dapat memonitor jadwal tanpa membuka private chat;
-   semua tindakan administratif penting tercatat dalam audit log.

## 26. Catatan Implementasi

Prioritas implementasi yang disarankan:

1.  Profile + master/tag.
2.  Discovery.
3.  Conversation + message.
4.  Meeting + state machine.
5.  Session + slot + resource.
6.  Conflict checking.
7.  Notification.
8.  Email/background worker.
9.  Recommendation engine.
10. Organizer dashboard API.
11. WebSocket/Redis bila benar-benar dibutuhkan.

Dengan pemisahan domain tersebut, Business Matching tetap modular dan
dapat dikembangkan bertahap tanpa membuat messaging, scheduling, dan
recommendation saling terikat secara berlebihan.
