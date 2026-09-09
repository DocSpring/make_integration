# Make app identifiers (non-secret)

- App name: `docspring-sspkqt` (Make auto-suffixes the internal name)
- Connection: `docspring-sspkqt` (type: basic)
- Version: 1
- Zone: us2 · Org: 8931444 · Team: 2910546
- Manifest version: 2
- API base: https://us2.make.com/api/v2 ; auth header `Authorization: Token <token>`

## SDK API routes (discovered)
- App:        `/sdk/apps/{app}/{version}`
- Base:       `/sdk/apps/{app}/{version}/base` (IMLJSON)
- Connection: `/sdk/apps/connections/{conn}/{parameters|api|common|scope|scopes}` (NOT under app path)
- Modules:    `/sdk/apps/{app}/{version}/modules` ; sections `/modules/{module}/{api|expect|interface|parameters|samples}`
- RPCs:       `/sdk/apps/{app}/{version}/rpcs`
- Functions:  `/sdk/apps/{app}/{version}/functions`
- Webhooks:   `/sdk/apps/{app}/webhooks` (app-scoped, like connections)

## Testing note
Validating a connection via `POST /api/v2/connections` fails with "Failed to load manifest"
for an uncommitted dev app. Test connections + modules through the Make scenario editor
(browser) instead — the intended dev-test path.
