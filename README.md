# backend-curavita

Django 5 + DRF backend for Health Hub Connect.

## Stack

- Django 5, Django REST Framework, SimpleJWT
- PostgreSQL (Docker) + Redis (Docker)
- Celery 5 (async tasks + scheduled jobs)
- drf-spectacular (OpenAPI docs at `/api/docs/`)

## Quickstart (local dev)

1. Start PostgreSQL + Redis via Docker (they should already be running).
2. Install deps and run migrations:

   ```bash
   uv sync
   python manage.py migrate
   ```

3. Run the API:

   ```bash
   python manage.py runserver
   ```

## Running Celery (async tasks and scheduled jobs)

Celery is configured in `backend_curavita/celery.py` using Redis as broker and result backend.

**Start the worker** (required for: appointment reminder tasks scheduled via `eta`, review-request notifications, and any `.delay()` / `.apply_async()` dispatch):

```bash
celery -A backend_curavita worker -l info
```

**Start beat** (required for daily slot generation at 00:00 and cleanup at 01:00):

```bash
celery -A backend_curavita beat -l info
```

Both processes need to run alongside Django for the scheduled flows to work. In development you can open two terminals.

**Verify beat schedule:**

```bash
celery -A backend_curavita inspect scheduled
```

Expected output includes `generate-daily-slots` and `cleanup-expired-slots`.

## Running tests

```bash
python manage.py test
```

Specific app:

```bash
python manage.py test apps.users
python manage.py test apps.appointments
python manage.py test apps.reviews
```

## API

- Root: `http://localhost:8000/api/v1/`
- Docs: `http://localhost:8000/api/docs/`
- Auth: JWT in `Authorization: Bearer <token>` header.
