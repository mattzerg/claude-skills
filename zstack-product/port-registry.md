# Port Registry — Zstack Microproducts

Bootstrap consults this before assigning. Edit when a new product ships.

| Port | Slug | Tier | Status |
|------|------|------|--------|
| 3000 | zergboard | Nitro | live |
| 3001 | zergwallet | Nitro | live (dev: docker zergwallet-db) |
| 3002 | zsend | Nitro | live |
| 3003 | _next available_ | — | — |
| 3004 | _next available_ | — | — |
| 8080 | zmail (API) | FastAPI | live |
| 8080 | zmsg (API) | FastAPI | live (different host) |
| 25 | zmail (SMTP) | FastAPI | live |

## Allocation rules

- Nitro/Node products: 3000–3099 range
- FastAPI/Python services: 8080–8099 range
- SMTP: port 25 (zmail only)
- Bootstrap MUST verify port unused on this list before assigning
- Fly internal_port = NITRO_PORT = registry port (1:1)

## Conflict notes

- zergbox claims port 3000 in dev, conflicting with zergboard. Run one at a time locally.
- zergchat (separate from zchat) — port not in registry; assign on first deploy
