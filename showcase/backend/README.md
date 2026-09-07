# BackEnd

Prima implementazione del daemon backend separato per Appunti Vision.

Caratteristiche iniziali:

- server `FastAPI` con API `REST`
- supporto `HTTPS` con certificato locale
- connessione `MySQL` via `localhost TCP` usando `127.0.0.1:3306`
- autenticazione `JWT`
- endpoint per upload e download di file grandi in streaming
- endpoint `state` per migrare gradualmente il frontend attuale

## Avvio rapido

### 1. Ambiente virtuale

```powershell
cd BackEnd
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e .
```

### 2. Configurazione

```powershell
Copy-Item .env.example .env
```

Configura MySQL in locale e crea il database:

```sql
CREATE DATABASE appunti_backend CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'appunti'@'127.0.0.1' IDENTIFIED BY 'appunti';
GRANT ALL PRIVILEGES ON appunti_backend.* TO 'appunti'@'127.0.0.1';
FLUSH PRIVILEGES;
```

### 3. Certificato HTTPS locale

Con `mkcert`, ad esempio:

```powershell
mkcert -key-file certs/dev-key.pem -cert-file certs/dev-cert.pem localhost 127.0.0.1
```

### 4. Avvio

```powershell
uvicorn appunti_backend.main:app --host 127.0.0.1 --port 8443 --reload --ssl-keyfile certs/dev-key.pem --ssl-certfile certs/dev-cert.pem
```

Oppure:

```powershell
appunti-backend
```

## Endpoint iniziali

- `GET /api/v1/health`
- `POST /api/v1/auth/register`
- `POST /api/v1/auth/login`
- `GET /api/v1/auth/me`
- `GET /api/v1/state`
- `PUT /api/v1/state`
- `POST /api/v1/files/upload`
- `GET /api/v1/files`
- `GET /api/v1/files/{file_id}`
- `GET /api/v1/files/{file_id}/download`
- `DELETE /api/v1/files/{file_id}`

## Note

- MySQL usa `127.0.0.1` per forzare la connessione TCP locale.
- I file caricati vengono salvati su disco locale in `BackEnd/data/uploads`.
- Gli script SQL di supporto sono raccolti in `BackEnd/sql_scripts/` (`schema.sql` e una copia dello schema SQLite storico del client).
- Questa prima versione usa `create_all()` all'avvio; il passo successivo consigliato e aggiungere `Alembic`.
