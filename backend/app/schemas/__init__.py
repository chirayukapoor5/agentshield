# Deployment guidance

## Local

Use Docker Compose for the full stack or run the backend directly with a local virtual environment.

```bash
cp env.example .env
docker compose up --build
```

## Production recommendations

- Use PostgreSQL instead of SQLite.
- Store secrets in environment variables or a secret manager.
- Enable TLS and secure cookies in front of the app.
- Run background workers separately from the API service.
- Add rate limiting, WAF policies, and log retention controls.
- Review and rotate API keys regularly.

