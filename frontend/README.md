# WillChain SL Frontend

This folder contains the Next.js and TypeScript user interface.

## Intended layout

- `app/` — future Next.js routes and route layouts.
- `components/` — reusable interface components, organised by responsibility.
- `hooks/` — reusable frontend hooks.
- `lib/` — frontend utilities and configuration.
- `services/` — typed communication with the Django REST API.
- `types/` — shared TypeScript type definitions.
- `styles/` — global and shared styling.
- `public/` — public static assets.
- `tests/` — frontend tests.

Set `NEXT_PUBLIC_GOOGLE_OAUTH2_CLIENT_ID` to the Google Identity Services web client ID and `NEXT_PUBLIC_API_BASE_URL` to the backend API URL. The Google client ID is public; never put a client secret in frontend configuration.

The login screen sends the Google ID token to the backend for verification. The beneficiary release page reads the one-time token from the URL fragment and keeps it out of query strings. The beneficiary dashboard only requests allocations released to the authenticated account.
