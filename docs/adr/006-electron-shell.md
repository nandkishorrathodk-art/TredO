# ADR 006: Electron Shell Before Dashboard

## Problem
AI-generated frontend projects often fail by immediately producing 300-file dashboards with charts, visualizations, and AI interfaces — all of which break when the backend changes. The result is a frontend that hides bugs rather than exposing them.

## Decision
We built an "Electron Shell" — the absolute minimum UI required to verify backend communication works perfectly. Only 3 pages (Dashboard, Events, Settings) with zero charts, zero AI visualization, and zero fancy animations beyond basic micro-interactions.

## Alternatives Considered
- **Full Dashboard (V1):** Build all 20 pages at once. (Rejected: Creates a massive frontend surface area that is impossible to stabilize before the backend is battle-tested).
- **CLI Only:** Skip the UI entirely and use a terminal. (Rejected: We need to verify WebSocket live streaming and REST communication patterns that only a real UI can test).
- **Web App:** Use a browser-based React app instead of Electron. (Rejected: TREDO is a desktop trading platform; Electron is the target runtime. Testing in a different runtime hides platform-specific issues).

## Why this approach
- **Backend Verification:** The shell exists to prove the backend works, not to look pretty.
- **API Contract Testing:** Forces us to freeze and document the API contract (`docs/API_CONTRACT.md`) before the frontend starts depending on it.
- **Incremental Enhancement:** Once the shell is stable, pages and features can be added one at a time without breaking existing functionality.

## Consequences
- **Pros:** Extremely fast iteration on backend without frontend coupling; clean separation of concerns; easy to verify end-to-end flows.
- **Cons:** The UI looks minimal and "unfinished" — which is intentional. Fancy features come after V1 stability.
