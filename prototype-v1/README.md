<!-- Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved. -->
<!-- SPDX-License-Identifier: MIT-0 -->

# Prototype UI

Demo prototype for the Campaign Optimization Agent. React + TypeScript frontend with an Express backend serving synthetic campaign data.

## Contents

```text
prototype/
├── ui/                  React frontend (Vite + TypeScript + Tailwind)
├── api-server/          Express backend API (TypeScript)
├── data/                Synthetic campaign data (7 JSON files)
├── start_servers.py     Cross-platform launcher (kills stale ports, starts both servers)
└── kill_ports.py        Utility to free ports 3000 and 8000
```

## Prerequisites

- **Node.js** >= 18
- **Python** >= 3.12 (for the launcher scripts)
- **uv** (recommended) or pip

## Starting the Prototype

### Option A: Automated Launcher (Recommended)

From the **project root**:

```bash
uv run python prototype/start_servers.py
```

This will:
1. Kill any existing processes on ports 3000 and 8000
2. Start the backend API server (port 8000)
3. Start the frontend dev server (port 3000)

On Windows, two new terminal windows open automatically.

### Option B: Manual Start (Two Terminals)

**Terminal 1 - Backend:**

```bash
cd prototype/api-server
npm install    # first time only
npm run dev
```

Wait for: `Campaign Optimization API server running on port 8000`

**Terminal 2 - Frontend:**

```bash
cd prototype/ui
npm install    # first time only
npm run dev
```

Wait for: `Local: http://localhost:3000/`

### Open the App

Navigate to **<http://localhost:3000>** in your browser.

## Stopping the Prototype

### If started with the launcher (Option A)

Close the two terminal windows that were opened, or run:

```bash
uv run python prototype/kill_ports.py
```

### If started manually (Option B)

Press `Ctrl+C` in each terminal window.

## Verifying It Works

| Check | URL | Expected |
|-------|-----|----------|
| Backend health | <http://localhost:8000/health> | `{"status":"ok","timestamp":"..."}` |
| Frontend | <http://localhost:3000> | Campaign Agent UI with sidebar |
| API data | <http://localhost:8000/api/campaigns> | JSON array of campaigns |

## Troubleshooting

### Port Already in Use

If port 3000 or 8000 is occupied:

1. **Use the kill script:**

   ```bash
   uv run python prototype/kill_ports.py
   ```

2. **Or find and kill manually (Windows):**

   ```bash
   netstat -ano | findstr :3000
   taskkill /PID <PID> /F
   ```

3. **Or find and kill manually (macOS/Linux):**

   ```bash
   lsof -ti :3000 | xargs kill -9
   ```

4. **Or change ports:**

   - Frontend: edit `ui/vite.config.ts` and change the `server.port` value
   - Backend: set the `PORT` environment variable before running:

     ```bash
     # Windows (Command Prompt)
     set PORT=8001 && npm run dev

     # Windows (PowerShell)
     $env:PORT=8001; npm run dev

     # macOS/Linux
     PORT=8001 npm run dev
     ```

### Dependencies Not Installed

```bash
cd prototype/api-server
npm install

cd ../ui
npm install
```

### Fresh Install (Nuclear Option)

```bash
cd prototype/ui
rm -rf node_modules package-lock.json
npm install

cd ../api-server
rm -rf node_modules package-lock.json
npm install
```

### Data Not Loading

1. Verify the backend is running: `curl http://localhost:8000/health`
2. Check the browser console (F12) for CORS or network errors
3. Ensure the `prototype/data/` directory contains 7 JSON files

### Frontend Shows Blank Page

1. Check the terminal running the frontend for compilation errors
2. Try a hard refresh: `Ctrl+Shift+R`
3. Clear the Vite cache: delete `prototype/ui/node_modules/.vite` and restart

## Key URLs

| Service | URL |
|---------|-----|
| Frontend UI | <http://localhost:3000> |
| Backend API | <http://localhost:8000/api> |
| Health Check | <http://localhost:8000/health> |

## Further Reading

- [ui/README.md](ui/README.md) - Detailed frontend documentation, component guide, and customization
