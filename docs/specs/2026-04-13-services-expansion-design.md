# Services Expansion — MCP Tool Design Spec

**Date:** 2026-04-13
**Sub-project:** 1 of 4 (Services Expansion)
**Goal:** Enable full org bootstrap and song library management — song CRUD, arrangement CRUD with lyrics/chords, file attachments, media management, CCLI compliance tools, and service type creation.

---

## Context

The pco-mcp server currently has 17 Services tools covering plan management, team scheduling, and read-only song/arrangement listing. Missing: the ability to create or edit songs, manage arrangements (lyrics, chord charts, keys), upload media/attachments, pull CCLI reporting, or create service types. A user bootstrapping a blank PCO org or filling in song metadata cannot do so through the agent today.

**PCO API base:** `https://api.planningcenteronline.com/services/v2`

---

## New Tools (16)

### Song CRUD

#### `create_song`
- **Type:** WRITE
- **Endpoint:** `POST /services/v2/songs`
- **Parameters:** `title` (required), `author`, `copyright`, `ccli_number` (integer), `themes`, `admin` (notes)
- **Returns:** Created song with ID, title, author, CCLI number
- **Notes:** After creation, the user will typically want to create an arrangement with lyrics/chords.

#### `get_song`
- **Type:** READ
- **Endpoint:** `GET /services/v2/songs/{song_id}`
- **Parameters:** `song_id` (required)
- **Returns:** Full song detail including title, author, copyright, CCLI number, themes, admin notes, created_at, last_scheduled_at
- **Notes:** The existing `list_songs` is search-oriented. This returns complete detail for a known song.

#### `update_song`
- **Type:** WRITE
- **Endpoint:** `PATCH /services/v2/songs/{song_id}`
- **Parameters:** `song_id` (required), plus any of: `title`, `author`, `copyright`, `ccli_number`, `themes`, `admin`
- **Returns:** Updated song
- **Notes:** Key use case: populating missing CCLI numbers on existing songs.

#### `delete_song`
- **Type:** DESTRUCTIVE
- **Endpoint:** `DELETE /services/v2/songs/{song_id}`
- **Parameters:** `song_id` (required)
- **Returns:** `{"status": "deleted"}`
- **Notes:** Removes song and all arrangements/attachments. Confirmation required.

### Arrangement CRUD

#### `create_arrangement`
- **Type:** WRITE
- **Endpoint:** `POST /services/v2/songs/{song_id}/arrangements`
- **Parameters:** `song_id` (required), `name` (required), `chord_chart` (ChordPro or plain text lyrics), `bpm` (float), `meter` (string, e.g. "4/4"), `length` (integer, seconds), `chord_chart_key` (string, e.g. "G"), `sequence` (array of section labels), `notes`
- **Returns:** Created arrangement with ID and all fields
- **Notes:** `chord_chart` is the primary field — it stores both lyrics and chords. ChordPro format embeds chords inline: `[G]Amazing [C]grace`. Plain text is lyrics-only. The `lyrics` field on the response is read-only and derived from `chord_chart`. Arrangement sections are also derived from `chord_chart` content — they are not independently writable.

#### `update_arrangement`
- **Type:** WRITE
- **Endpoint:** `PATCH /services/v2/songs/{song_id}/arrangements/{arrangement_id}`
- **Parameters:** `song_id` (required), `arrangement_id` (required), plus any of the fields from `create_arrangement`
- **Returns:** Updated arrangement
- **Notes:** Primary use case (#2): filling in missing BPM, key, lyrics, chord charts on existing arrangements.

#### `delete_arrangement`
- **Type:** DESTRUCTIVE
- **Endpoint:** `DELETE /services/v2/songs/{song_id}/arrangements/{arrangement_id}`
- **Parameters:** `song_id`, `arrangement_id` (required)
- **Returns:** `{"status": "deleted"}`

### File Attachments

#### `create_attachment`
- **Type:** WRITE
- **Endpoint:** Multi-step:
  1. `POST /services/v2/songs/{song_id}/arrangements/{arrangement_id}/attachments` — creates record, returns S3 presigned URL
  2. `PUT` to presigned URL — uploads file bytes
  3. `PATCH /services/v2/attachments/{attachment_id}` — marks upload complete
- **Parameters:** `song_id`, `arrangement_id` (required), `url` (required — publicly accessible URL to the file), `filename` (required), `content_type` (e.g. "application/pdf", "audio/mpeg")
- **Returns:** Attachment record with ID, filename, URL, content type
- **Notes:** Handles the full 3-step S3 upload flow internally. The tool fetches the file from the provided URL, creates the attachment record, uploads to the presigned S3 URL, then marks complete. Supported use cases: PDF chord charts, lead sheets, MP3 reference recordings, click tracks. The URL must be publicly accessible (or a signed URL) — the MCP server fetches the file server-side.

#### `list_attachments`
- **Type:** READ
- **Endpoint:** `GET /services/v2/songs/{song_id}/arrangements/{arrangement_id}/attachments`
- **Parameters:** `song_id`, `arrangement_id` (required)
- **Returns:** List of attachments with ID, filename, URL, content type, file size

### Media Management

#### `create_media`
- **Type:** WRITE
- **Endpoint:** `POST /services/v2/media` + attachment upload flow
- **Parameters:** `title` (required), `media_type` (required: "image", "video", "countdown", "document"), `url` (required — publicly accessible URL), `filename` (required), `content_type` (required), `creator_name`
- **Returns:** Media record with ID, title, type, thumbnail URL
- **Notes:** Uses same 3-step attachment upload as `create_attachment`. Media items are org-level (backgrounds, countdown videos, bumper videos).

#### `list_media`
- **Type:** READ
- **Endpoint:** `GET /services/v2/media`
- **Parameters:** Optional `media_type` filter
- **Returns:** List of media with ID, title, type, thumbnail URL, creator

#### `update_media`
- **Type:** WRITE
- **Endpoint:** `PATCH /services/v2/media/{media_id}`
- **Parameters:** `media_id` (required), plus any of: `title`, `themes`, `creator_name`
- **Returns:** Updated media record

### CCLI Compliance

#### `get_ccli_reporting`
- **Type:** READ
- **Endpoint:** `GET /services/v2/service_types/{service_type_id}/plans/{plan_id}/items/{item_id}/ccli_reporting`
- **Parameters:** `service_type_id`, `plan_id`, `item_id` (all required)
- **Returns:** CCLI reporting data: print, digital, recording, translation counts
- **Notes:** Read-only endpoint. CCLI reporting is tracked automatically by PCO when songs are added to plans.

#### `get_song_usage_report`
- **Type:** READ
- **Endpoint:** `GET /services/v2/songs/{song_id}/song_schedules`
- **Parameters:** `song_id` (required)
- **Returns:** List of all dates the song was scheduled, with service type, key used, and arrangement used
- **Notes:** Useful for CCLI annual reporting — shows how many times a song was used across all service types.

#### `flag_missing_ccli`
- **Type:** READ
- **Endpoint:** Composite — queries `GET /services/v2/songs` with pagination, filters for songs where `ccli_number` is null/empty
- **Parameters:** None (scans full song library)
- **Returns:** List of songs missing CCLI numbers, with title, author, and last scheduled date
- **Notes:** Proactive compliance tool. Caps at 200 songs to avoid excessive API calls. Returns count of total songs scanned vs. flagged.

### Service Type Creation

#### `create_service_type`
- **Type:** WRITE
- **Endpoint:** `POST /services/v2/service_types`
- **Parameters:** `name` (required), `frequency` (optional: "every 1 week", "every 2 weeks", etc.)
- **Returns:** Created service type with ID, name, frequency
- **Notes:** A blank org needs service types before plans can be created.

---

## Shared Infrastructure

### Attachment Upload Helper
The 3-step S3 upload flow is shared between `create_attachment` and `create_media`. Extract a reusable helper in the PCO client layer:

```
async def upload_attachment(
    self,
    create_url: str,       # POST endpoint to create attachment record
    source_url: str,       # Publicly accessible URL to fetch file from
    filename: str,
    content_type: str,
) -> dict:
    # 1. POST to create_url → get attachment ID + presigned upload URL
    # 2. Read file bytes, PUT to presigned URL
    # 3. PATCH attachment to mark complete
    # Returns attachment record
```

### ServicesAPI Expansion
Add methods to `src/pco_mcp/pco/services.py` for each new endpoint. Follow existing patterns: methods return simplified dicts, handle pagination where needed.

---

## Tool Annotations

Follow existing conventions:
- READ: `readOnlyHint: true, openWorldHint: true`
- WRITE: `readOnlyHint: false, destructiveHint: false, confirmationHint: true, openWorldHint: true`
- DESTRUCTIVE: `readOnlyHint: false, destructiveHint: true, confirmationHint: true, openWorldHint: true`

---

## Testing Strategy

- Unit tests for each new ServicesAPI method (mock HTTP responses with fixtures)
- Unit tests for each MCP tool (mock ServicesAPI, verify parameter passing and response shaping)
- Test the attachment upload helper with mocked S3 presigned URL flow
- Test `flag_missing_ccli` pagination and filtering logic
- Fixtures: add JSON response fixtures under `tests/fixtures/services/` for each new endpoint

---

## Out of Scope

- Custom slides, live controllers, email templates
- Scheduling preferences, folders, tag management
- Song import from external sources (CCLI SongSelect, etc.)
- Bulk operations (batch song creation) — individual CRUD only
