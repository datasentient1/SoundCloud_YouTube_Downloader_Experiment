# Artist Catalog Downloader

A small full-stack app for authenticated artists to export playlists they own or are authorized to download. The backend uses:

- [`yt-dlp`](https://github.com/yt-dlp/yt-dlp) for YouTube and YouTube Music playlist exports.
- [`scdl`](https://github.com/scdl-org/scdl) for SoundCloud playlist exports.

Users must create an account, sign in, and accept the usage terms before starting a download job. Completed jobs are packaged as zip files.

## Important Use Boundary

This app should only be used for catalogs the user owns, controls, or has explicit permission to download. You are responsible for complying with copyright law and each platform's terms.

## Local Development

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python3 -m uvicorn backend.app.main:app --reload
```

Open `http://localhost:8000`.

For a Docker-first local run:

```bash
cp .env.example .env
docker compose up --build
```

## Railway Deployment

This repo is ready to deploy directly from GitHub on Railway. See [`DEPLOY.md`](DEPLOY.md) for the click-by-click setup, required variables, persistent volume mount, and custom domain steps.

## Production Notes

- Replace `APP_JWT_SECRET` with a long random value before deploying.
- Keep `/app/data` on persistent storage.
- Downloads are handled by in-process background threads for speed of setup. Move jobs to Redis/RQ, Celery, or a managed worker once multiple users run large exports.
- Consider adding email verification, password reset, billing/quotas, and an admin dashboard before opening signups broadly.
- Some platforms may require cookies, tokens, or user-provided authentication for private catalogs. Do not store third-party credentials until you have a secure secrets design.

## Smoke Check

```bash
bash scripts/smoke.sh
```
