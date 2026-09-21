# WillChain SL

Secure digital will-management academic project for Sierra Leone.

The repository contains a Next.js frontend and a Django REST Framework backend. Module 1 authentication and the Module 2 will-management foundation are implemented incrementally under the approved architecture.

Module 2 currently covers private owner drafts, lifecycle state, versioning, finalization, object-level authorization, audit events, and the authenticated owner dashboard workflow. Blockchain integrity and AI services are reserved for later modules.

## Local Docker setup

Copy the backend environment template to `backend/.env` and set the local PostgreSQL password and Django secret before starting the stack:

```cmd
copy backend\.env.example backend\.env
docker compose up --build
```

The services are available at:

- Frontend: `http://localhost:3000`
- Backend API: `http://localhost:8000/api/v1/`
- PostgreSQL: `localhost:5432`

Stop the stack with:

```cmd
docker compose down
```

The database volume is preserved between restarts. Remove it only when you intentionally want to delete local database data:

```cmd
docker compose down -v
```
