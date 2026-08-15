# Frontend Business Matching Web Messaging

## REST flow

Semua endpoint membutuhkan `Authorization: Bearer <access-token>`.

- `POST /api/v1/events/{event_id}/conversations` membuka atau menggunakan kembali conversation dengan participant tujuan.
- `GET /api/v1/events/{event_id}/conversations` mengembalikan counterpart, last message, dan unread count.
- `GET /api/v1/conversations/{id}/messages?limit=50&before=<ISO-8601>` mengambil histori secara cursor pagination.
- `POST /api/v1/conversations/{id}/messages` mengirim text/reply.
- `PATCH /api/v1/conversations/{id}/messages/{message_id}` mengedit pesan sendiri.
- `DELETE /api/v1/conversations/{id}/messages/{message_id}` melakukan soft-delete pesan sendiri.
- `POST /api/v1/conversations/{id}/read` mengirim read receipt.
- `POST /api/v1/conversations/{id}/archive` dan `/unarchive` mengatur inbox user.
- `GET /api/v1/messages/unread-count` menghasilkan badge unread global.

Contoh kirim pesan:

```json
{"body":"Saya tertarik mendiskusikan distribusi produk Anda.","reply_to_message_id":null}
```

## WebSocket

Hubungkan setelah conversation diperoleh:

```text
wss://<backend-domain>/api/v1/ws/conversations/<conversation_id>?token=<access-token>
```

Event server:

- `connected`
- `new_message`
- `message_updated`
- `message_deleted`
- `read_update`
- `meeting_status_update`

Client dapat mengirim `{"type":"ping"}` dan menerima `{"type":"pong"}`.
Pembuatan/edit/hapus pesan tetap dilakukan lewat REST agar validasi, transaksi,
notification, dan audit konsisten; WebSocket hanya untuk delivery realtime.

Hub saat ini process-local. Deployment satu worker dapat langsung digunakan.
Untuk beberapa worker/instance, tambahkan Redis pub/sub sebagai backplane tanpa
mengubah kontrak frontend.
