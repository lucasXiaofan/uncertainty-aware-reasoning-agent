# Vendored SEA dual-memory

These files are a **vendored copy** of the SEA dual-memory library, bundled here so
the SEA-memory doctor agent works from a fresh `git clone` of this repo (the
canonical `SEA/` lives outside the repo and is not committed).

| File | Source |
|---|---|
| `memory.py` | `SEA/memory.py` (`DualMemory`, `CaseRecord`, `Rule`, retrieval, persistence) |
| `llm.py` | `SEA/llm.py` (`RuleSummarizer`, `MockSummarizer`, `InjectedSummarizer`) |

Both are copied **unchanged** and depend only on the Python standard library.
`memory.py` imports from `llm`; `llm.py` references `memory`'s types only under
`TYPE_CHECKING`, so the two files are self-contained together.

## Re-syncing

If the upstream SEA library changes, re-copy:

```bash
cp ../../../../SEA/memory.py ../../../../SEA/llm.py .   # run from this dir
```

(`sea_doctor_agent.py` and `build_experience.py` import from this directory by
default; set the `SEA_PATH` env var to point at a different SEA checkout for local
development.)
