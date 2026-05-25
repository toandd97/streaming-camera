# AI Usage Log

## Tool Used
- **Antigravity (Google DeepMind AI)** — coding assistant in VS Code IDE

## Tasks Assisted By AI

| Task | AI Role | Human Review |
|------|---------|-------------|
| Project structure layout | Suggested based on requirements | Reviewed and approved |
| FastAPI lifespan pattern | Generated boilerplate | Verified against FastAPI docs |
| StreamWorker asyncio + executor pattern | Generated core logic | Tested manually |
| OpenCV RTSP capture settings | Suggested `CAP_PROP_BUFFERSIZE=1` for low latency | Accepted |
| MJPEG multipart response format | Generated generator function | Verified in browser |
| SlidingWindowFPS algorithm | Generated using deque | Verified with test |
| Alert cooldown logic | Generated Dict-based cooldown | Reviewed for race conditions |
| MongoDB Motor async patterns | Generated connection lifecycle | Verified against Motor docs |
| CSS dark mode dashboard | Generated based on TSX reference design | Compared visually |
| Docker Compose health checks | Generated with `mongosh ping` | Tested |
| setup.sh one-command flow | Generated full script | Reviewed error handling |

## What AI Did Well
- Quickly scaffolded the entire project structure
- Generated asyncio-correct patterns (run_in_executor for blocking calls)
- Produced working MJPEG streaming code on first attempt
- Adapted TSX design to vanilla HTML/CSS/JS faithfully
- Generated comprehensive test cases

## What Required Human Judgment
- Deciding on in-memory vs MongoDB for runtime status
- Choosing MJPEG over WebRTC for MVP simplicity
- Setting appropriate timeout/reconnect values
- Deciding `app/` vs `src/` directory convention
- Verifying thread-safety of StreamWorker's `latest_frame` access

## Prompts Used (Summary)
1. "Read requirements file and create implementation plan"
2. "Apply user comments: versioned API folder, one-command setup, structured logging"
3. "Build the system following the plan, UI modeled after the provided TSX simulator"
