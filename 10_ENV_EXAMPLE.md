# AttendAI — Environment Variables

Do not commit real values.

## Backend

```env
DATABASE_URL=postgresql://USER:PASSWORD@HOST:5432/DB
SECRET_KEY=replace-with-long-random-secret
FRONTEND_ORIGIN=https://your-frontend-domain.example
CORS_ORIGINS=https://your-frontend-domain.example
```

## Frontend

```env
VITE_API_BASE_URL=https://your-backend-domain.example/api
```

Use the actual variable names expected by the repository.

## Production rules

- Keep secrets in hosting provider environment settings.
- Do not put credentials in GitHub.
- Do not paste secrets into issue trackers.
- Rotate credentials if accidentally committed.
