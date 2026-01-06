# SnapPlan Web MVP

Next.js frontend for SnapPlan - deterministic extraction of construction document data with 100% traceability.

## Tech Stack

- **Framework**: Next.js 14 (App Router)
- **Language**: TypeScript
- **Styling**: TailwindCSS
- **Auth & Database**: Supabase (Auth, Postgres, Storage)
- **i18n**: next-intl (DE/EN)

## Prerequisites

- Node.js 18+
- npm or yarn
- Supabase project (for auth/database)
- Backend API running (FastAPI on port 8000)

## Setup

### 1. Install dependencies

```bash
npm install
```

### 2. Environment Variables

Create `.env.local` in the frontend directory:

```bash
# Supabase
NEXT_PUBLIC_SUPABASE_URL=https://your-project.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=eyJ...

# Backend API
NEXT_PUBLIC_SNAPGRID_API_URL=http://localhost:8000

# Site URL (for auth redirects)
NEXT_PUBLIC_SITE_URL=http://localhost:3000
```

### 3. Supabase Setup

1. Create a new Supabase project at [supabase.com](https://supabase.com)

2. Run the migration to create tables:
   ```sql
   -- Copy contents from backend/infra/supabase/mvp_schema.sql
   ```

3. Create a storage bucket:
   - Name: `snapplan-files`
   - Public: No (private)
   - Allowed MIME types: `application/pdf`

4. Enable Email Auth in Authentication settings

### 4. Run Development Server

```bash
npm run dev
```

Open [http://localhost:3000](http://localhost:3000)

## Project Structure

```
frontend/
├── app/
│   ├── page.tsx                    # Public landing page
│   ├── auth/
│   │   ├── login/page.tsx          # Login page
│   │   ├── signup/page.tsx         # Signup page
│   │   └── callback/route.ts       # Auth callback
│   └── app/
│       ├── layout.tsx              # Protected AppShell layout
│       ├── page.tsx                # Dashboard
│       ├── projects/
│       │   ├── page.tsx            # Projects list
│       │   ├── new/page.tsx        # Create project
│       │   └── [id]/
│       │       ├── page.tsx        # Project detail
│       │       ├── upload/page.tsx # Upload PDF
│       │       └── results/[jobId]/page.tsx  # Results
│       ├── billing/page.tsx        # Billing (placeholder)
│       └── settings/page.tsx       # Settings
├── components/
│   ├── app/                        # AppShell components
│   ├── results/                    # Results page components
│   └── upload/                     # Upload components
├── lib/
│   └── supabase/                   # Supabase client utilities
└── middleware.ts                   # Auth + i18n middleware
```

## Features

### MVP (Current)

- **Area Extraction**: Extract NRF (Netto-Raumfläche) values from German CAD PDFs
- **Balcony Factor**: Automatic 0.5 factor for Balkon/Terrasse/Loggia
- **Audit Trail**: Full traceability with source_text, page, bbox, confidence
- **JSON Export**: Download results with complete audit data

### Coming Soon (Phase 2)

- Door schedule extraction
- Window detection
- Drywall perimeter calculation
- Excel/PDF export
- Stripe billing integration

## Development

### Build for Production

```bash
npm run build
```

### Lint

```bash
npm run lint
```

## API Integration

The frontend communicates with:

1. **Supabase** (direct):
   - Authentication
   - Database queries (projects, files, jobs, results)
   - File storage

2. **Backend API** (via Supabase Edge Function):
   - PDF processing (`/api/v1/jobs/process`)
   - NRF extraction

## Environment Variables Reference

| Variable | Description | Required |
|----------|-------------|----------|
| `NEXT_PUBLIC_SUPABASE_URL` | Supabase project URL | Yes |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | Supabase anon/public key | Yes |
| `NEXT_PUBLIC_SNAPGRID_API_URL` | FastAPI backend URL | Yes |
| `NEXT_PUBLIC_SITE_URL` | Frontend URL (for auth redirects) | Yes |

## Design System

### Colors

```css
--bg-primary: #0F1B2A;      /* Deep navy background */
--bg-secondary: #1A2942;    /* Card backgrounds */
--bg-card: #243B53;         /* Elevated cards */
--accent-teal: #00D4AA;     /* Primary accent */
--accent-blue: #3B82F6;     /* Secondary accent */
--text-primary: #FFFFFF;
--text-secondary: #94A3B8;
--text-muted: #64748B;
```

### Typography

- Sans: Inter
- Mono: JetBrains Mono (for numbers/code)
