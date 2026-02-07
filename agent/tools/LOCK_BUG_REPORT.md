# Session Lock Bug Report: macOS `flock()` Self-Deadlock

**Date:** 2026-02-06
**Affected files:**
- `agent/tools/diagnosis_session.py`
- `agent/tools/documentation_tools.py`
- `benchmarks/AgentClinic/uncertainty_aware_doctor.py`

---

## Symptom

During parallel AgentClinic experiments, the uncertainty-aware doctor agent consistently fails with:

```
Error: Could not acquire lock for session scenario_XXXX_XXXX within 30.0s
```

The error appears after several successful iterations and progressively worsens, eventually blocking every subsequent doctor turn. All 7 cases in the experiment produced "No diagnosis reached" (0% accuracy) because the lock timeout prevented the agent from recording diagnostic steps or issuing a final diagnosis.

**Example from report:**
```
Iteration 3 - Doctor: Error: Could not acquire lock for session scenario_4470080080_1770431446 within 30.0s
Iteration 4 - Doctor: Error: Could not acquire lock for session scenario_4470080080_1770431446 within 30.0s
Iteration 5 - Doctor: Error: Could not acquire lock for session scenario_4470080080_1770431446 within 30.0s
```

---

## Root Cause: macOS `flock()` Self-Deadlock

### The platform difference

On **Linux**, `flock()` locks are per-process — the same process can acquire the same lock multiple times via different file descriptors without blocking.

On **macOS (BSD)**, `flock()` locks are per-file-descriptor — the same process trying to acquire an exclusive lock on the same file via a **different** file descriptor is **blocked**, exactly like a different process would be.

### Proof

```python
import fcntl, os

fd1 = os.open("test.lock", os.O_CREAT | os.O_RDWR)
fcntl.flock(fd1, fcntl.LOCK_EX | fcntl.LOCK_NB)  # succeeds

fd2 = os.open("test.lock", os.O_CREAT | os.O_RDWR)
fcntl.flock(fd2, fcntl.LOCK_EX | fcntl.LOCK_NB)  # Linux: succeeds, macOS: DEADLOCK!
# BlockingIOError: [Errno 35] Resource temporarily unavailable
```

### How this manifested in the code

The `_acquire_lock()` function opened the lock file and called `flock(LOCK_EX | LOCK_NB)`. Multiple functions in the codebase used this locking mechanism, creating **nested lock** patterns:

**`final_diagnosis_documented()` in `documentation_tools.py` (the clearest case):**

```python
lock_fd = _acquire_lock(session_id)       # fd1 acquires lock
try:
    session = load_session(session_id)     # internally calls _acquire_lock() -> fd2 -> DEADLOCK!
    ...
    save_session(session_id, session)      # would also try to acquire -> fd3 -> DEADLOCK!
finally:
    _release_lock(lock_fd)
```

1. Outer `_acquire_lock()` opens the lock file as `fd1` and acquires `LOCK_EX`
2. `load_session()` internally calls `_acquire_lock()`, opening the same lock file as `fd2`
3. `flock(fd2, LOCK_EX | LOCK_NB)` fails immediately on macOS (errno 35)
4. The retry loop spins for 30 seconds, then raises `TimeoutError`
5. The error propagates as the doctor's response, breaking the diagnostic flow

**`document_step()` in `documentation_tools.py`:** Had manual locking but did its own file I/O without calling `load_session`/`save_session`, so no nested deadlock — but still used fragile `flock()`.

**`append_step()`, `load_session()`, `save_session()` in `diagnosis_session.py`:** Each individually correct (no nesting), but the mechanism was unreliable on macOS.

---

## Why Locking Was Unnecessary

The file locking was designed for thread-safety in parallel execution. However, analysis of the actual execution model shows locking is unnecessary:

1. **Unique session IDs per process:** Each `agentclinic_api_only.py` process creates a unique `session_id` (e.g., `scenario_{pid}_{uuid}_{timestamp}`). Different parallel cases never access the same session file.

2. **Sequential tool execution within a process:** `SingleAgent.run()` processes tool calls in a sequential `for` loop — there is no concurrent access to the same session file within a process.

3. **No cross-process shared sessions:** The experiment runner (`run_experiment_selected.sh`) uses `xargs -P` to run cases in parallel, but each case is a separate Python process with its own session.

**Conclusion:** There is never concurrent access to the same session file, making locks unnecessary overhead that introduces bugs on macOS.

---

## Fix Applied

### 1. Removed file locking from `diagnosis_session.py`

- Removed `fcntl` import
- `load_session()`, `save_session()`, `append_step()`, `clear_session()` now do direct file I/O without locks
- `_acquire_lock()` and `_release_lock()` converted to no-ops for backward compatibility

### 2. Removed manual locking from `documentation_tools.py`

- `document_step()`: Replaced manual lock + direct file I/O with `load_session()`/`save_session()` calls
- `final_diagnosis_documented()`: Removed outer lock wrapper, uses `load_session()`/`save_session()` directly
- Removed `_acquire_lock`/`_release_lock` imports

### 3. Improved session ID uniqueness in `uncertainty_aware_doctor.py`

Old format: `scenario_{id(scenario)}_{int(time.time())}`
- `id(scenario)` returns memory address — can collide across processes with similar allocation patterns
- `int(time.time())` has 1-second resolution — parallel processes started in the same second get the same timestamp

New format: `scenario_{os.getpid()}_{uuid4_hex[:8]}_{int(time.time())}`
- `os.getpid()` is unique per process
- `uuid4` adds randomness
- Combined: guaranteed unique even under heavy parallelism

### 4. Cleaned up stale artifacts

- Removed 12 stale `.lock` files from `agent/diagnosis_sessions/`

---

## Verification

All changes validated with `uv run python` tests:

```
Session operations (load/save/append/clear): PASSED
Documentation tools (document_step, get_current_documented_response): PASSED
Session ID uniqueness (PID + UUID, different across agents): PASSED
Sequential lock pattern (20/20 iterations): PASSED (pre-fix baseline)
```

---

## Lessons Learned

1. **`flock()` behavior differs between Linux and macOS.** Code developed/tested on Linux can deadlock on macOS. Avoid `flock()` for same-process locking on macOS, or use `fcntl.lockf()` / `fcntl.fcntl()` with `F_SETLK` which has different (but also platform-specific) semantics.

2. **Don't add locking where the execution model doesn't require it.** Analyze whether concurrent access is actually possible before adding synchronization. Unnecessary locks add complexity and bugs.

3. **`id()` is not a good unique identifier across processes.** CPython's `id()` returns memory addresses that can easily collide across separate processes with similar allocation patterns. Use `os.getpid()` + `uuid` for cross-process uniqueness.
