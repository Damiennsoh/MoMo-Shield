# MoMo Shield · FraudOps Command Center

A polished, mobile-responsive fintech security operations frontend demo for Ghana mobile-money fraud prevention. It is an interactive **mock frontend**, not a live fraud-detection service; transaction events, Glance intelligence, rules, connector status, and intervention actions are simulated locally.

## Stack

Next.js 14 App Router, TypeScript, Tailwind CSS, shadcn/ui-style Radix UI primitives, lucide-react, Recharts, Framer Motion, Zustand, and locally bundled Inter Variable.

## Run locally

```bash
pnpm install
pnpm dev
```

Open `http://localhost:3000`.

## Production build

```bash
pnpm install --frozen-lockfile
pnpm build
```

Next.js statically exports all routes to `out/` for production hosting.

## Routes

- `/` — FraudOps Command Center: mock live telemetry, four KPIs, fraud network graph, risk velocity, alert details, and Release/Block/Escalate demo actions.
- `/lab` — Judge-in-the-loop signal tester with English/Twi/Pidgin selection, voice-call simulation and an audible demo ring, local heuristic scoring, JSON intent output and handset preview.
- `/handset` — MTN MoMo handset simulator inside the shared workspace navigation, with normal, amber cooling-off and red blocked views, larger-text accessibility control and browser speech playback. The customer handset remains a distinct preview surface, while simulated risk state is shared with the Signal Lab.
- `/settings` — Sandbox/API-key placeholder, connector status and local mock-policy controls. No real credentials or APIs are configured.

## Project map

- `app/` — App Router views, metadata, manifest, and global styling.
- `components/` — Responsive shell and route navigation, risk gauge, telemetry row, alert card, handset frame, fraud graph, trend chart, and shared UI primitives.
- `lib/useStore.ts` — Typed Zustand state and seeded Ghanaian sample data.
- `public/manifest.json` — Initial web-app manifest; `public/manus-routes.json` — route inventory.
- `TODO.md` — Source requirements and delivered outcomes.

## PWA extension

An initial manifest and SVG app icon are included. To make this fully installable, add suitable 192×192 and 512×512 raster icons and reference them in the manifest. Then create a service worker (for example, `public/sw.js`) and register it from a client-side effect after page load. No offline caching or request interception is implemented in this demo.

## Demo limitations

No requests are sent to MTN, Rancard Glance, a telecom sandbox, or an LLM. Signal analysis uses deterministic local keyword heuristics. Browser speech playback depends on native speech-synthesis support and installed voices. The settings page intentionally displays only a nonfunctional placeholder key.
