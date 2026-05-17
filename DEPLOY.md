# Railway Deployment Guide

This repo is prepared for Railway's GitHub flow:

- `Dockerfile` builds the FastAPI app and downloader tools.
- `railway.json` tells Railway to use the Dockerfile and healthcheck `/api/health`.
- The server listens on Railway's injected `$PORT`.
- Runtime data is written under `/app/data`.

## Create The Project

1. Go to Railway and click `New Project`.
2. Choose `Deploy from GitHub repo`.
3. Pick `datasentient1/SoundCloud_YouTube_Downloader_Experiment`.
4. Let Railway create the service and start the first deploy.
5. Open the service, go to `Variables`, and add:
   - `APP_APP_ORIGIN=https://your-domain.com`
   - `APP_DATABASE_PATH=/app/data/app.db`
   - `APP_DOWNLOADS_DIR=/app/data/downloads`
   - `APP_MAX_CONCURRENT_JOBS=2`
6. Redeploy after adding variables.

## Add Persistent Storage

1. In the Railway project canvas, create a volume.
2. Attach it to the web service.
3. Set the mount path to `/app/data`.
4. Redeploy the service.

This preserves the SQLite database and generated zip archives across deploys.

## Test On Railway

1. In the service `Networking` tab, generate a Railway domain.
2. Visit the generated URL.
3. Try one short YouTube or SoundCloud playlist first.
4. Confirm the job reaches `complete` and the zip link downloads.

## Add Your Own Domain

1. In the service `Networking` tab, add a custom domain.
2. Enter your domain or subdomain, for example `app.your-domain.com`.
3. Copy the DNS record Railway shows.
4. Add that DNS record at your domain registrar or DNS host.
5. Once Railway verifies it, update `APP_APP_ORIGIN` to `https://app.your-domain.com`.
6. Redeploy one more time.

Using a subdomain is usually smoother than the root/apex domain. If you want the root domain too, add it separately after the subdomain is working.

## If Deploy Fails

- `Application failed to respond`: confirm the deploy logs show Uvicorn listening on Railway's `$PORT`.
- Healthcheck failure: open `/api/health` on the Railway domain; it should return `{"status":"ok"}`.
- Data disappears after redeploy: confirm the volume is mounted to `/app/data`.
- Downloads fail: check service logs for `yt-dlp` or `scdl` output; some private or restricted catalogs may require additional auth handling.

## Before Public Launch

- Add quotas or billing before opening signups broadly.
- Move jobs to a separate worker and store archives in object storage once downloads get large.
