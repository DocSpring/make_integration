# Make app identifiers (non-secret)

- App name: `docspring-sspkqt` (Make auto-suffixes the internal name)
- Connection: `docspring-sspkqt` (type: basic)
- Version: 1
- Zone: us2 · Org: 8931444 · Team: 2910546
- Manifest version: 2
- API base: https://us2.make.com/api/v2 ; auth header `Authorization: Token <token>`

## SDK API routes

From Make's API reference (base above; every path starts `/sdk/apps`). `app/UPLOAD.md` uses them step by step.

- App:        `GET /{app}/{version}` ; `PUT /{app}/{version}/groups` ; `PUT /{app}/{version}/readme` (text/markdown) ;
  `PUT /{app}/{version}/icon`
- Base:       `POST /{app}/{version}/base` (set, IMLJSON) ; `PATCH` (merge)
- Connection: `GET /{app}/connections` ; `PUT /connections/{conn}/{parameters|api|common|scope|scopes}` (NOT under the
  app path)
- Modules:    `GET|POST /{app}/{version}/modules` ; `PATCH|DELETE /{app}/{version}/modules/{module}` (label, description,
  connection) ; `PUT /modules/{module}/{api|expect|interface|parameters|samples|scope|epoch}` ;
  `POST /modules/{module}/{public|private}` ; `POST /modules/{module}/{deprecate|undeprecate}`
- RPCs:       `GET|POST /{app}/{version}/rpcs` ; `PATCH|DELETE /{app}/{version}/rpcs/{rpc}` ;
  `PUT /rpcs/{rpc}/{api|parameters}`
- Functions:  `/{app}/{version}/functions` (none: custom IML functions need Make support to enable them)
- Webhooks:   `GET|POST /{app}/webhooks` (app-scoped, like connections) ; `PATCH|DELETE /webhooks/{name}` ;
  `PUT /webhooks/{name}/{api|parameters|attach|detach|update|scope}`

## Components (API v2, sc-5981)

- 29 modules in `app/modules/` (labels, types and bindings in `app/UPLOAD.md`). `createDataRequest` was replaced by
  `createSignatureRequest`; Make keeps the old module hidden and deprecated if it won't delete it.
- 5 RPCs, all on connection `docspring-sspkqt`: `listTemplates` and `listFolders` (`GET /templates`, `GET /folders`,
  cursor paging, up to 1,000 items), `templateFields` (`GET /templates/{id}/schema?version=`, the typed template fields
  as mappable inputs), `templateFieldNames` (the schema's field names) and `templateFieldIds` (`GET
  /templates/{id}/fields`).
- 1 dedicated webhook (Watch events): attach creates a version 4 DocSpring webhook (`POST /webhooks`), detach deletes
  it if it still exists.

## Testing note
Validating a connection via `POST /api/v2/connections` fails with "Failed to load manifest"
for an uncommitted dev app. Test connections + modules through the Make scenario editor
(browser) instead — the intended dev-test path.
