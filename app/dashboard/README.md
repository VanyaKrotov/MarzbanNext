# MarzbanNext Dashboard

The dashboard is the React frontend embedded into the MarzbanNext backend.

## Requirements

- Node.js `20.19.0` or newer.
- npm.
- A running MarzbanNext backend for API integration.

## Stack

- React 18 and TypeScript.
- Vite 8.
- Tailwind CSS 4.
- shadcn and Radix UI as the primary component system.
- TanStack Query for server state and mutations.
- Axios clients from `src/service/http.ts`.
- react-hook-form with Zod validation.
- Monaco Editor for Xray JSON.
- Recharts for statistics.
- i18next for localization.

Do not add Chakra UI or native fetch calls. New UI primitives should be added
through shadcn and all destructive confirmations should use `AlertDialog`.

## Install

From `app/dashboard`:

```bash
cp example.env .env
npm ci
```

On PowerShell:

```powershell
Copy-Item example.env .env
npm ci
```

Configure the backend API in `.env`:

```env
VITE_BASE_API=http://127.0.0.1:8000/api/
```

For a same-origin deployment, use:

```env
VITE_BASE_API=/api/
```

## Commands

```bash
npm run dev
npm run build
npm run preview
npm run ui:info
```

The development server listens on port `3000`. The production build performs
TypeScript checking before Vite compilation.

## Add a UI component

Use the repository wrapper instead of calling a remote registry preset directly:

```bash
npm run ui:add -- button
npm run ui:add -- alert-dialog
```

The wrapper keeps generated components compatible with the local shadcn
configuration and import aliases. The `@/*` alias maps to `src/*`.

## Application pages

| Route | Feature |
| --- | --- |
| `/` | Users table, URL filters, create/edit dialog and usage actions |
| `/nodes` | Node connection and profiles with configuration, certificates and runtime logs |
| `/hosts` | Host CRUD, copying, enabling and drag-and-drop ordering |
| `/inbounds` | Managed inbound JSON and node assignment |
| `/outbounds` | Managed outbound JSON and node assignment |
| `/routing` | Routing rule JSON, assignments and ordering |
| `/stats` | Traffic and user charts |
| `/login` | Administrator authentication |

The application also links to same-origin `/docs`.

## Data and forms

- Keep endpoint functions in the relevant service module.
- Use TanStack Query hooks close to the page or feature that consumes them.
- Use `useMutation` for writes and invalidate only affected query keys.
- Use the shared authenticated `api` or unauthenticated `publicApi` Axios client.
- Keep filter state that must survive reloads in URL query parameters.
- Use react-hook-form `Controller` for controlled fields.
- Keep schemas and reusable form helpers in the feature-local `lib` directory.
- Split large dialogs into local `components`, `lib`, and query modules.

Objects sourced from a node Xray template have read-only JSON content and cannot
be deleted. Their metadata, enabled state and node assignments can still be edited.

### Host form subscriptions

The host form keeps validation subscriptions in individual fields with
`useFormState({ name, exact: true })` or `useController`. Do not read
`form.formState.errors` in section containers: this subscribes the form provider
to errors and redraws unrelated sections when an error changes.

The optional-field menu and selected sections have separate subscriptions.
Client balancer sections watch a computed list of client keys rather than all
client settings. Only the Xray least-load fields watch the effective strategy.
Keep the available-host and selected-template arrays stable while searching.

For performance checks, compare the same edit before and after a change with all
three client sections open. Typing a client probe URL should update its field
without rendering other client editors. Correcting an address validation error
should update `AddressField` without rendering the form container.

## JSON editor

The shared Monaco editor accepts an optional JSON schema. Feature-specific
schemas currently cover:

- complete Xray configuration;
- inbound configuration;
- outbound configuration;
- routing rules with inbound tag completion;
- node Xray templates;
- subscription templates for Xray JSON, Clash (JSON and YAML), sing-box and Outline.

Schema descriptions are written in English. Keep the schema optional so the
editor remains reusable.
Subscription schemas live in `subscription-templates-page/lib/schemas`; the Xray
client schema extends the shared core schema without changing server validation.
`monaco-yaml` provides YAML validation, completion and hover descriptions using
the same Clash schema. Its worker adapter handles Monaco 0.55's worker API.
Template variables and filters have format-specific Jinja completion and hover
descriptions, including plain-text URI templates. Raw Jinja blocks are validated
by the backend after rendering rather than reported as JSON/YAML syntax errors.

## Styling and localization

- Prefer Tailwind utility classes and existing design tokens.
- Support both light and dark themes.
- Use Lucide icons.
- Put all user-facing strings in i18next resources.
- Use `Tooltip`, `Popover`, `Empty`, `Dialog`, `Tabs` and other shared UI
  components instead of feature-specific replacements.
- Verify desktop and mobile layouts.

## Verification

Before submitting dashboard changes:

```bash
npm test
npm run build
```

`npm test` runs the TypeScript tests in `tests/` through Node's built-in test runner
and the project's TypeScript loader. The build performs full source type checking.

Mapper editor tests use Monaco's bundled JSON language service to check validation,
completion and hover text. `tests/fixtures/host-mapper-schema.json` is generated from
`HostMapperOptions.model_json_schema()` in `app/models/host_mapper.py`;
`tests/test_host_mapper_schema.py` in the repository root checks that it stays in sync
with the backend capabilities schema. Regenerate this fixture when the mapper contract changes.

Final mask follows the same approach: `tests/fixtures/finalmask-schema.json` comes
from `FinalMask.model_json_schema()` in `app/models/finalmask/`. The Python schema
tests verify API parity, and `tests/finalmask-editor.test.ts` exercises validation,
transport-specific completion and hover descriptions through Monaco's language service.

Socket options use `SocketOptions.model_json_schema()` in `app/models/socket_options.py`.
`tests/fixtures/socket-options-schema.json` is verified by the backend schema tests;
`tests/socket-options-editor.test.ts` checks field/strategy completion, nested custom
options, validation and hover text. Regenerate the Final mask fixture as well when
this contract changes, because its ECH socket options use the same model.

For visual changes, also open the affected page against a running backend and
verify loading, empty, error and populated states.
