# AI Retrospective

## Overall Experience

Using an AI coding assistant for this project significantly accelerated development of boilerplate-heavy components (FastAPI setup, Pydantic schemas, Docker configuration) while requiring careful human oversight for the core business logic.

## What Worked Exceptionally Well

**1. Project Scaffolding**
The AI generated the entire folder structure and all `__init__.py` files instantly, saving ~30 minutes of setup work.

**2. Asyncio Patterns**
The `run_in_executor` pattern for OpenCV's blocking `cap.read()` was correctly suggested without prompting. This is a subtle correctness issue that many developers miss.

**3. Multi-component Coordination**
The AI understood the requirement that `GET /api/v1/cameras` must merge MongoDB config with in-memory runtime status, and correctly separated the concerns across Repository → Service → API layers.

**4. Design Adaptation**
Converting the React TSX dashboard design to vanilla HTML/CSS/JS while maintaining the exact visual appearance was done accurately.

## What Required Iteration

**1. Alert Cooldown**
Initial implementation tracked cooldown globally. Had to revise to track per `(camera_id, event_type)` tuple.

**2. MJPEG Blank Frame**
First version of the MJPEG generator crashed if no frame was available. Added `get_blank_frame()` fallback after testing.

**3. Docker Healthcheck**
Initial `docker-compose.yml` didn't have a health check for MongoDB, causing the backend to start before MongoDB was ready. Fixed with `mongosh ping` healthcheck + `depends_on: condition: service_healthy`.

## Key Lesson

> AI excels at generating *correct structure* and *standard patterns*. Human oversight is essential for *edge cases*, *failure modes*, and *system-level correctness* (timing, concurrency, resource cleanup).

## Time Estimate

| Phase | Estimated Time |
|-------|---------------|
| Requirements reading + planning | 20 min |
| AI-assisted code generation | 60 min |
| Review and corrections | 30 min |
| Manual testing | 30 min |
| Documentation | 20 min |
| **Total** | **~2.5 hours** |

Without AI assistance, estimated time would be 8-12 hours for the same scope.
