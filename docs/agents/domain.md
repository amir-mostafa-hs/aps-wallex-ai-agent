# Domain Docs

How the engineering skills should consume this repo's domain documentation when exploring the codebase.

## Before exploring, read these

1. **`GLOSSARY.md`** at the repo root (if present; created lazily by `/domain-modeling`).
2. **`docs/adr/`**: read ADRs touching the area you are about to work in.
3. **Core Domain Reference Files**:
   - `docs/specs/GRILL_ME_HISTORY_FA.md`
   - `docs/specs/DECISION_REGISTER_FA.md`
   - `docs/specs/AGENT_CONTRACT_FA.md`
   - `docs/specs/SPEC_FA.md`
   - `docs/specs/ARCHITECTURE_FA.md`
   - `docs/specs/MARKET_SCANNING_DECISION_LOGIC_FA.md`
   - `docs/specs/TODO_48H_FA.md`
   - `docs/specs/TESTING_REPORTING_FA.md`
   - `docs/specs/WALLEX_API_NOTES.md`
   - `docs/specs/PACKAGE_CONTENTS_FA.md`
   - Original sources & denylist in `docs/sources/` (`assets.md`, `inactive_markets.json`, `intro-text.md`, `task.md`) and media in `docs/media/`.

If `GLOSSARY.md` or `docs/adr/` do not exist yet, **proceed silently**. Do not flag their absence; the `/domain-modeling` skill creates them as domain terms or architectural decisions are finalized.

## File structure

Single-context repo layout:

```
/
├── AGENTS.md
├── README_FA.md
├── .env.example
├── GLOSSARY.md (lazy)
├── docs/
│   ├── adr/
│   ├── agents/
│   │   ├── domain.md
│   │   ├── issue-tracker.md
│   │   └── triage-labels.md
│   ├── media/
│   ├── prompts/
│   ├── reports/
│   ├── sources/
│   └── specs/ (domain specs and decision registers)
└── .scratch/
```

## Use the domain vocabulary

- Follow `docs/specs/AGENT_CONTRACT_FA.md` as the strict single source of truth for Agent actions and horizon profile values.
- Follow the terms established in `docs/specs/DECISION_REGISTER_FA.md` and `GLOSSARY.md`. Do not invent synonyms or deviate from agreed terms.

## Flag ADR & Decision conflicts

If any proposed change contradicts an existing ADR or an entry in `docs/DECISION_REGISTER_FA.md`, surface it explicitly to the maintainer rather than silently overriding it.
