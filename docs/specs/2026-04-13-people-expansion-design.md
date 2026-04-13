# People Expansion — MCP Tool Design Spec

**Date:** 2026-04-13
**Sub-project:** 2 of 4 (People Expansion)
**Goal:** Complete the people management story — contact details (emails, phones, addresses), notes, blockout creation, and workflow management. Fills gaps needed for org bootstrap and ongoing pastoral care.

---

## Context

The pco-mcp server has 8 People tools covering search, get, create, update, list membership, and blockout viewing. Missing: the ability to manage contact details (emails, phones, addresses), add pastoral notes, create blockout dates, or interact with workflows. These are essential for both bootstrapping a new org and day-to-day staff operations.

**PCO API base:** `https://api.planningcenteronline.com/people/v2`

---

## New Tools (12)

### Contact Details

#### `add_email`
- **Type:** WRITE
- **Endpoint:** `POST /people/v2/people/{person_id}/emails`
- **Parameters:** `person_id` (required), `address` (required), `location` (optional: "Home", "Work", "Other"), `is_primary` (optional, boolean)
- **Returns:** Created email record with ID, address, location, primary status
- **Notes:** PCO email addresses are globally unique login identifiers. If the email is already associated with another person, the API returns a 422. The tool should return a clear error message explaining the conflict rather than a generic failure.

#### `update_email`
- **Type:** WRITE
- **Endpoint:** `PATCH /people/v2/people/{person_id}/emails/{email_id}`
- **Parameters:** `person_id`, `email_id` (required), plus any of: `address`, `location`, `is_primary`
- **Returns:** Updated email record

#### `add_phone_number`
- **Type:** WRITE
- **Endpoint:** `POST /people/v2/people/{person_id}/phone_numbers`
- **Parameters:** `person_id` (required), `number` (required), `location` (optional: "Home", "Work", "Mobile", "Other"), `is_primary` (optional, boolean)
- **Returns:** Created phone record with ID, number, formatted number, location

#### `update_phone_number`
- **Type:** WRITE
- **Endpoint:** `PATCH /people/v2/people/{person_id}/phone_numbers/{phone_id}`
- **Parameters:** `person_id`, `phone_id` (required), plus any of: `number`, `location`, `is_primary`
- **Returns:** Updated phone record

#### `add_address`
- **Type:** WRITE
- **Endpoint:** `POST /people/v2/people/{person_id}/addresses`
- **Parameters:** `person_id` (required), `street` (required), `city` (required), `state` (required), `zip` (required), `location` (optional: "Home", "Work", "Other"), `is_primary` (optional, boolean)
- **Returns:** Created address record with ID, full address, location

#### `update_address`
- **Type:** WRITE
- **Endpoint:** `PATCH /people/v2/people/{person_id}/addresses/{address_id}`
- **Parameters:** `person_id`, `address_id` (required), plus any of: `street`, `city`, `state`, `zip`, `location`, `is_primary`
- **Returns:** Updated address record

### Person Details

#### `list_person_details`
- **Type:** READ
- **Endpoint:** Composite — fetches in parallel:
  1. `GET /people/v2/people/{person_id}/emails`
  2. `GET /people/v2/people/{person_id}/phone_numbers`
  3. `GET /people/v2/people/{person_id}/addresses`
- **Parameters:** `person_id` (required)
- **Returns:** Unified object: `{ emails: [...], phone_numbers: [...], addresses: [...] }`
- **Notes:** The existing `get_person` returns basic profile info but not contact details. This fills that gap with a single tool call instead of requiring three separate calls.

### Notes

#### `add_note`
- **Type:** WRITE
- **Endpoint:** `POST /people/v2/people/{person_id}/notes`
- **Parameters:** `person_id` (required), `note` (required, text content), `note_category_id` (optional — if omitted, uses the default/general category)
- **Returns:** Created note with ID, content, category, created_at, created_by
- **Notes:** Pastoral care use case — staff can ask the agent to log a note about a conversation or visit.

#### `list_notes`
- **Type:** READ
- **Endpoint:** `GET /people/v2/people/{person_id}/notes`
- **Parameters:** `person_id` (required)
- **Returns:** List of notes with ID, content, category name, created_at, created_by name
- **Notes:** Returns most recent first. Paginated, capped at 50 notes per request.

### Blockouts

#### `add_blockout`
- **Type:** WRITE
- **Endpoint:** `POST /people/v2/people/{person_id}/blockouts`
- **Parameters:** `person_id` (required), `description` (required), `starts_at` (required, ISO datetime), `ends_at` (required, ISO datetime), `repeat_frequency` (optional: "no_repeat", "every_1_week", "every_2_weeks", "every_1_month"), `repeat_until` (optional, ISO date)
- **Returns:** Created blockout with ID, description, dates, repeat info
- **Notes:** Use case: team manager gets a text "I'm out next Sunday" and can immediately add a blockout via the agent. The existing `get_person_blockouts` tool handles reading.

### Workflows

#### `list_workflows`
- **Type:** READ
- **Endpoint:** `GET /people/v2/workflows`
- **Parameters:** None (returns all workflows for the org)
- **Returns:** List of workflows with ID, name, card counts (ready, completed, total)
- **Notes:** Shows available workflows like "New Member Follow-up", "Baptism Prep", etc.

#### `add_person_to_workflow`
- **Type:** WRITE
- **Endpoint:** `POST /people/v2/workflows/{workflow_id}/cards`
- **Parameters:** `workflow_id` (required), `person_id` (required)
- **Returns:** Created workflow card with ID, person name, workflow name, current step
- **Notes:** Creates a new card (entry) in the workflow for the specified person. The person will appear at the first step of the workflow.

---

## PeopleAPI Expansion

Add methods to `src/pco_mcp/pco/people.py`. Follow existing patterns:
- Methods return simplified dicts (not raw API responses)
- Error handling via `safe_tool_call` wrapper
- Pagination handled by the PCO client's `get_all()` where needed

New methods needed:
- `add_email()`, `update_email()`
- `add_phone_number()`, `update_phone_number()`
- `add_address()`, `update_address()`
- `get_person_details()` — parallel fetch of emails + phones + addresses
- `add_note()`, `get_notes()`
- `add_blockout()`
- `get_workflows()`, `add_person_to_workflow()`

---

## Tool Annotations

Same conventions as existing tools:
- READ: `readOnlyHint: true, openWorldHint: true`
- WRITE: `readOnlyHint: false, destructiveHint: false, confirmationHint: true, openWorldHint: true`

No DESTRUCTIVE tools in this sub-project (no delete operations for contact details).

---

## Testing Strategy

- Unit tests for each new PeopleAPI method (mock HTTP responses)
- Unit tests for each MCP tool
- Test `list_person_details` parallel fetch behavior
- Test email 422 conflict error handling specifically (known PCO behavior)
- Test `add_blockout` with and without repeat parameters
- Fixtures: add JSON response fixtures under `tests/fixtures/people/` for each new endpoint

---

## Out of Scope

- Delete operations for emails, phones, addresses (risky, low value)
- Forms and form submissions
- Social profiles
- People imports / bulk operations
- Household management
- Custom field definitions (admin setup)
- Messages
