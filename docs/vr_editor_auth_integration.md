# VR browser API — production integration contract

This module adds an **opt-in WSGI endpoint factory**, not an anonymous web
server or a replacement for PlanReader's Streamlit/SQLite session system.

## Canonical request

`GET /api/editor/workspaces/{workspace_id}/manifest`

The server must create the application with two real callbacks:

```python
from pb_vr_editor_readonly_wsgi import make_editor_readonly_wsgi_app

app = make_editor_readonly_wsgi_app(
    authenticate_session=existing_planreader_session_verifier,
    load_authorized_workspace=tenant_scoped_workspace_loader,
)
```

Do **not** use those illustrative callback names as if they were implemented.
The deployed app must supply its actual authenticated user identity and
tenant-restricted DB access. No default app, test identity, fake admin account,
public source directory or source-hash override is provided.

The session verifier must derive a server-owned `EditorPrincipal`, including
its actual tenant ID and allowed workspace ID set, from existing user grants.
It must NEVER treat a workspace ID supplied in the URL or JSON as a grant.

The workspace loader must return `AuthorizedSceneWorkspace` whose tenant,
workspace, document, revision, snapshot and original source SHA-256 have
been independently checked against server-side records. Canonical ID
mappings must come from the existing PlanReader physical/canonical
resolver. If the customer-created `model_masses` records lack source PDF
ownership, return no authenticated scene or mark those objects unresolved:
**do not attach a hash to them because the files happen to be in the same
workspace**.

This is a scoped **read-only** renderer DTO. It never grants billable
measurement authority, computes a customer quantity or changes geometry.

## Typed command preview (separate stacked PR)

`POST /api/editor/workspaces/{workspace_id}/commands/preview` is added
by the subsequent command API. In addition to the above providers, it
requires a server-side CSRF verifier and workspace-scoped correction ledger.
The preview validates the client source SHA/revision/snapshot/object revision
against the authoritative server snapshot and replays existing correction
formulas on a deep copy. It performs **no** persistent correction, approval,
or commercial publication. Every request is bounded to 32 KiB and strict JSON.

## Production deployment requirements

- HTTPS / secure browser context and no cross-origin credentialed API.
- Real session authentication, tenant isolation and permission audit.
- Strict content security policy and WebXR permission policy where supported.
- Current source hash and canonical IDs from original source evidence.
- Explicit signed, approved correction transaction with durable idempotency
  before any mutation route is introduced.
- Full exact-head Python3.13+3.14, frontend TypeScript, source/security,
  original signed fixture and real headset/browser acceptance tests.

Do not expose the optional WSGI factory publicly before all callbacks are
actually implemented, reviewed and tested. No existing production route is
modified by this PR.
