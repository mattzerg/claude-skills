# Durable Robotics — billing app probing notes (2026-06-01)

Notes from my first look at the app. We hand off to the client Thursday.
THIS IS A SHARED LIVE APP — the Durable ops team is already entering real data into it.

## App basics

- Live URL: https://durable-billing.fly.dev (Fly app `durable-billing`, region ord)
- Stack: Nuxt 3 + Nitro server routes, Postgres (Fly managed cluster)
- Repo: ~/clients/durable-billing (I have a local checkout, may be slightly behind prod)
- Login: https://durable-billing.fly.dev/login
- My account: matt@zergai.com / (password in ~/.config/zerg/secrets/durable.env) — role: super admin
- The Durable ops team accounts: 4 active users entering invoices daily

## Modules in scope for handoff

1. **Invoices** — list + detail, line items, tax handling, status workflow (draft → sent → paid → overdue)
2. **Payments** — payment records, application against invoices, partial payments
3. **Customer balances** — per-customer outstanding balance, aging buckets (0-30/31-60/61-90/90+), statement export

## What I found poking around (~30 min)

- API pattern: `/api/billing/{invoices,payments,customers,balances,aging}.get` — responses are JSON, the UI renders straight from these
- The session cookie is `db_session`, httpOnly — can't read it from JS, but replaying the login POST to `/api/auth/login` with email/password returns it
- DB access: `flyctl ssh console -a durable-billing -C "printenv DATABASE_URL"` works. No psql in the container but node + the app's pg driver are there
- ⚠ The app's own db helper (server/utils/db.ts) runs pending migrations on first import — do NOT use it for queries
- Data state right now: 47 invoices, 31 payments, 12 customers. Payments module has real money flowing — the ops team applied $84,312.50 in payments last week
- The aging report screen exists but I'm not sure the bucket math is right — one customer (Apex Manufacturing) showed $12,400 in 31-60 but their oldest unpaid invoice is dated 2026-05-18 (14 days ago)
- Statement export button exists but I didn't click it — not sure if it generates server-side state
- There's also a "Credit Notes" screen in the nav but it 404s — I think it's unreleased

## Who's doing what

- I (Matt) am covering UX/design feedback separately — that's NOT what this audit is for
- This audit = functionality lane: does the math add up, do the workflows behave correctly
- Jamie on the Durable side asked specifically: "can we trust the balances screen for month-end close?"
