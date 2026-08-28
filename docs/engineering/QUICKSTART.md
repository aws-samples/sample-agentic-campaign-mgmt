<!-- Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved. -->
<!-- SPDX-License-Identifier: MIT-0 -->

# Quick Start — Campaign Optimization Agent UI

## What's Here

- **prototype-v1/data/** — 7 JSON files with synthetic campaign data
- **prototype-v1/ui/** — React + TypeScript frontend
- **prototype-v1/api-server/** — Express backend API
- **scripts/** — Data generation and exploration tools
- **docs/** — Documentation

## Quick Start (5 Minutes)

### Step 1: Open Terminal in Project Root

```bash
cd campaign-mgmt
```

### Step 2: Install Dependencies

#### Backend

```bash
cd prototype-v1/api-server
npm install
cd ../..
```

#### Frontend

```bash
cd prototype-v1/ui
npm install
cd ../..
```

### Step 3: Start the Application

#### Option A: Use the Launcher (Recommended for Windows)

```bash
uv run python prototype-v1/start_servers.py
```

This opens two terminal windows:

- Backend API on <http://localhost:8000>
- Frontend UI on <http://localhost:3000>

#### Option B: Manual Start (Two Terminals)

Terminal 1 — Backend:

```bash
cd prototype-v1/api-server
npm run dev
```

Wait for: `Campaign Optimization API server running on port 8000`

Terminal 2 — Frontend:

```bash
cd prototype-v1/ui
npm run dev
```

Wait for: `Local: http://localhost:3000/`

### Step 4: Open Browser

Navigate to: [http://localhost:3000](http://localhost:3000)

## Verify Everything Works

### Check 1: Backend Health

Open: <http://localhost:8000/health>

Should see:

```json
{"status":"ok","timestamp":"2026-02-17T..."}
```

### Check 2: Data Files

```bash
ls prototype-v1/data/
```

Should see 7 JSON files.

### Check 3: Frontend Loading

Open <http://localhost:3000> and verify:

- Campaign Agent logo in sidebar
- Chat Assistant page with gradient background
- Trader selector showing "Trader Alpha (intermediate)"

## Try These Queries

In the Chat Assistant, click these sample queries:

1. **"Show me campaign 4782"** — See campaign metrics, Status: At Risk
2. **"What's wrong with campaign 4782?"** — See diagnosis: Bid too low
3. **"Give me recommendations for 4782"** — See recommended bid increase
4. **"Show all at-risk campaigns"** — See list of 15 at-risk campaigns

## Explore the UI

### 1. Chat Assistant

- Natural language queries
- AI-powered responses
- Sample query buttons

### 2. Dashboard

- Click "Dashboard" in sidebar
- View key metrics
- See charts (Pie, Bar)
- Browse campaign table

### 3. Campaign Explorer

- Click "Campaign Explorer" in sidebar
- Select campaign #4782
- Click "Diagnose" button
- Click "Recommend" button
- Click "Market" button

## Project Structure

```text
campaign-mgmt/
├── agent/          Strands Agent (Python)
├── prototype-v1/   Demo Prototype UI
│   ├── ui/         React Frontend
│   ├── api-server/ Express Backend
│   └── data/       Synthetic data (7 JSON files)
├── docs/           Documentation
├── deploy/         Deployment scripts (boto3)
├── ml/             ML models (scikit-learn)
├── lambda/         AWS Lambda handlers
├── scripts/        Utility scripts
└── tests/          All tests (unit, smoke, e2e)
```

## Useful Commands

### Development

```bash
# Start backend dev server
cd prototype-v1/api-server && npm run dev

# Start frontend dev server
cd prototype-v1/ui && npm run dev

# Explore synthetic data
uv run python scripts/explore_data.py
```

### Build for Production

```bash
# Build frontend
cd prototype-v1/ui && npm run build

# Build backend
cd prototype-v1/api-server && npm run build && npm start
```

## Key URLs

- **Frontend:** <http://localhost:3000>
- **Backend API:** <http://localhost:8000/api>
- **Health Check:** <http://localhost:8000/health>
- **API Docs:** See [prototype-v1/api-server/README.md](../../prototype-v1/api-server/README.md) for all endpoints

## Troubleshooting

### Port Already in Use

If port 3000 or 8000 is already used:

1. **Use the kill script:** Run `uv run python prototype-v1/kill_ports.py` from the project root

2. **Or find and kill manually:**

   ```bash
   netstat -ano | findstr :3000
   taskkill /PID <PID> /F
   ```

3. **Or change the frontend port** in `prototype-v1/ui/vite.config.ts`:

   ```typescript
   server: {
     port: 3001,
     proxy: { '/api': { target: 'http://localhost:8000', changeOrigin: true } },
   }
   ```

4. **Or change the backend port:**

   ```bash
   set PORT=8001 && npm run dev        # Command Prompt
   $env:PORT=8001; npm run dev         # PowerShell
   ```

### Dependencies Issue

```bash
cd prototype-v1/ui
rm -rf node_modules package-lock.json
npm install

cd ../api-server
rm -rf node_modules package-lock.json
npm install
```

### Data Not Loading

1. Verify data files exist:

   ```bash
   ls prototype-v1/data/
   ```

2. Check backend is running:

   ```bash
   curl http://localhost:8000/health
   ```

3. Check browser console (F12) for errors

## Next Steps

1. **Run the application** — Follow steps above
2. **Customize** — Edit colors in `prototype-v1/ui/tailwind.config.js`
3. **Deploy** — See [OPERATIONS.md](OPERATIONS.md) for AWS deployment options
4. **Architecture** — See [ARCHITECTURE-1.md](ARCHITECTURE-1.md) for system design

## Success Checklist

- [ ] Backend running on port 8000
- [ ] Frontend running on port 3000
- [ ] Can open <http://localhost:3000>
- [ ] Can see Campaign Agent interface
- [ ] Chat queries return responses
- [ ] Dashboard shows charts
- [ ] Campaign Explorer shows campaigns

If all checked, you're ready to demo!
