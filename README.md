# CCTV AI Search

A local-first Windows application for searching hundreds of existing CCTV recordings for a person, starting from a reference photo. All processing stays on your computer.

> **This is a candidate-search tool.** Visual similarity is not proof of identity. A person must review every result. See [docs/privacy.md](docs/privacy.md).

## Status

| Milestone | Scope | State |
|---|---|---|
| 1 | Repo structure, config, FastAPI health, SQLite schema + migrations, React UI, Windows setup | ✅ Done |
| 2 | Recursive folder scan, ffprobe metadata, duplicate/change detection, tests | ✅ Done |
| 3 | Background indexing, frame sampling, timestamps, cancel/resume | ⏳ Next |
| 4 | Face detection + embeddings (licence documented first) | — |
| 5 | Person detection + body re-identification | — |
| 6 | FAISS indexes, reference-photo search, grouping, ranking | — |
| 7 | Results gallery, playback, seeking, clips | — |
| 8 | Security review, end-to-end tests, benchmarks, packaging | — |

What works today:
- Scanning a folder and all its subfolders for `.mp4 .avi .mkv .mov .m4v` files. Extensions are matched case-insensitively.
- Reading duration, resolution, frame rate, codec, container and creation time from each file with ffprobe.
- Skipping unchanged files on re-scan, using size and mtime. Files whose content changed are re-probed and their derived data is cleared.
- Flagging exact duplicates (the same content at another path) with a fast fingerprint: SHA-256 of the size plus the first, middle and last 1 MB.
- Marking corrupted files as `failed` and files with no video stream as `unsupported`. Deleted files become `missing` and are restored if they reappear.
- Running scans as background jobs stored in the database. You can cancel a job, and any job interrupted by a shutdown resumes on the next start.
- Dashboard with counts, hardware info (CPU/GPU/RAM, inference provider), FFmpeg status and model status. Video library with filters and paging. Jobs page with live progress.
- Security: binds to `127.0.0.1` only, checks the Host header (blocks DNS rebinding), rejects cross-origin writes, uses a strict CORS policy and CSP, and calls FFmpeg with argument lists, never a shell.

Not built yet: indexing, AI models, search, playback and clips (Milestones 3–8). `POST /api/index-jobs`, the `/api/search*` endpoints and the stream/clip endpoints do not exist yet. The UI only shows pages that work.

---

## 1. Install prerequisites (Windows 10/11, PowerShell)

```powershell
winget install --id Python.Python.3.12 -e
winget install --id OpenJS.NodeJS.LTS -e
winget install --id Gyan.FFmpeg -e
winget install --id Git.Git -e
```

Close and reopen PowerShell so the new `PATH` takes effect, then check:

```powershell
py -3.12 --version     # Python 3.12.x
node --version         # v20 or v22
ffprobe -version       # ffprobe version ...
```

If `ffprobe` is not found, add FFmpeg's `bin` folder to PATH. You can also set `CCTV_FFPROBE_PATH` / `CCTV_FFMPEG_PATH` in `.env` (see `.env.example`).

Optional: enable long paths (more than 260 characters). Run this once in an **Administrator** PowerShell:

```powershell
New-ItemProperty -Path "HKLM:\SYSTEM\CurrentControlSet\Control\FileSystem" -Name LongPathsEnabled -Value 1 -PropertyType DWORD -Force
```

## 2. Set up the project

```powershell
git clone https://github.com/symus/cctvaisearch.git
cd cctvaisearch

# Python virtual environment
py -3.12 -m venv .venv
# If activation is blocked: Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r backend\requirements-dev.txt

# Frontend (uses the lockfile)
cd frontend
npm ci
cd ..

# Optional: local settings
Copy-Item .env.example .env

# Check Python, FFmpeg, RAM, GPU, data folder
python scripts\check_env.py
```

By default, the database and derived data go to `cctvaisearch\data\`. To put them somewhere else, set `CCTV_DATA_DIR` in `.env`. Original recordings are never copied or modified.

## 3. Run the app

**Option A: development mode (two terminals, hot reload)**

```powershell
# Terminal 1 - backend API on http://127.0.0.1:8000
.\.venv\Scripts\Activate.ps1
cd backend
python -m app
```

```powershell
# Terminal 2 - UI on http://127.0.0.1:5173
cd frontend
npm run dev
```

Open **http://127.0.0.1:5173**.

**Option B: single process**

```powershell
cd frontend; npm run build; cd ..
.\.venv\Scripts\Activate.ps1
cd backend
python -m app
```

Open **http://127.0.0.1:8000**. The backend serves the built UI.

Interactive API docs (OpenAPI) are at **http://127.0.0.1:8000/docs**.

## 4. Try it with synthetic test videos

These are generated test patterns, so no real people appear in them:

```powershell
# From the repo root, venv active
python scripts\make_test_videos.py sample-videos
(Resolve-Path sample-videos).Path        # copy this absolute path
```

In the UI, go to **Video library**, paste the path and click **Scan recursively**. Watch the job on **Jobs**, then return to the library. You should see:
- 7 videos found
- `front door 0800 (copy).mp4` flagged as a duplicate
- `corrupted.mp4` marked as failed
- the Unicode folder `Caméra 3 – entrée` handled correctly

Click **Re-scan**. All 7 files should come back as unchanged.

The same scan from the command line:

```powershell
python scripts\scan_folder.py "$((Resolve-Path sample-videos).Path)"
```

The same through the API:

```powershell
$body = @{ path = (Resolve-Path sample-videos).Path } | ConvertTo-Json
$job = Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/api/videos/scan -ContentType application/json -Body $body
Invoke-RestMethod http://127.0.0.1:8000/api/index-jobs/$($job.id)
Invoke-RestMethod "http://127.0.0.1:8000/api/videos?limit=10" | Select-Object -ExpandProperty items | Format-Table id, filename, duration_seconds, width, height, indexing_status
```

After that, scan your real footage folder, for example `D:\CCTV\Exports`.

## 5. Run the tests

```powershell
# Backend (pytest). Video tests need ffmpeg on PATH and are skipped otherwise.
cd backend
python -m pytest -q

# Frontend (Vitest + Testing Library) and type check
cd ..\frontend
npm test
npm run typecheck
```

## API (implemented so far)

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/health` | Liveness, DB status, schema revision |
| GET | `/api/system-info` | OS/CPU/RAM/GPU, inference provider, FFmpeg, storage, model status |
| GET | `/api/stats` | Dashboard counts |
| POST | `/api/videos/scan` | `{"path": "D:\\CCTV"}` → 202 + job (runs in background) |
| GET | `/api/videos` | `?q=&status=&limit=&offset=` |
| GET | `/api/videos/{id}` | One video |
| GET | `/api/library-folders` | Approved (scanned) folders |
| GET | `/api/index-jobs` | Recent jobs |
| GET | `/api/index-jobs/{id}` | Job status/progress |
| POST | `/api/index-jobs/{id}/cancel` | Cancel a queued/running job |

API errors use the form `{"error": {"code": "...", "message": "...", "details": ...}}`.

## Project layout

```
backend/
  app/
    main.py            FastAPI app factory, lifespan, static UI
    config.py          Settings (CCTV_* env vars / .env)
    models.py          SQLAlchemy models (Video, Detection, Embedding, IndexJob, SearchSession, SearchResult, LibraryFolder)
    security.py        Host/Origin/CORS protection
    api/               Routers: system, videos, jobs
    services/          scanner, ffprobe (media), fingerprint, paths, hardware, job runner
  migrations/          Alembic migrations (applied automatically at startup)
  tests/               pytest suite (synthetic fixtures generated with ffmpeg)
frontend/              React + TypeScript + Vite
scripts/               check_env.py, make_test_videos.py, scan_folder.py
docs/                  privacy.md
```

Schema changes need a new migration:

```powershell
cd backend
alembic revision --autogenerate -m "describe change"
```

## Troubleshooting

- **`ffprobe not found`**: install FFmpeg (step 1) and reopen PowerShell, or set `CCTV_FFPROBE_PATH`.
- **Video shows `failed: Could not read video metadata`**: the file is truncated or is a proprietary DVR format. Convert a **copy** to a new file. The original is never modified.
  ```powershell
  ffmpeg -i "D:\Exports\cam1.dav" -c copy "D:\Converted\cam1.mkv"
  # If stream copy fails, re-encode:
  ffmpeg -i "D:\Exports\cam1.dav" -c:v libx264 -crf 20 "D:\Converted\cam1.mp4"
  ```
  Some NVR vendors (for example Dahua `.dav` or Hikvision exports) ship their own converter or player. Use it when FFmpeg cannot read the file.
- **`unsupported`**: the file has no video stream (for example audio only).
- **`missing`**: the file was moved or the drive is disconnected. Reconnect it and re-scan, and the earlier results come back.
- **`Folder overlaps the application data directory`**: don't scan the app's own data folder or any folder that contains it.
- **Paths with spaces or Unicode**: supported. In PowerShell, wrap paths in quotes.
- **Long paths fail**: enable `LongPathsEnabled` (step 1).
- **Activate.ps1 cannot be loaded**: run `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`.
- **CPU only / no GPU**: fully supported. The dashboard shows which inference provider will be used and why.
- **Low memory**: keep `CCTV_MAX_CONCURRENT_JOBS=1`. Scanning reads only small parts of each file.
- **Port 8000 or 5173 already in use**: set `CCTV_PORT`. For the UI, also run `$env:CCTV_BACKEND_URL="http://127.0.0.1:<port>"` before `npm run dev`.
- **AI models**: none are installed or downloaded yet. Models will need explicit install commands, and their licences will be documented in `docs/model-licenses.md` before any weights are used (Milestone 4).
