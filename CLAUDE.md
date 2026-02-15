# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Important

- Always use `uv` to run commands (e.g. `uv run`, `uv sync`). Never use `pip` directly.

## Development Commands

```bash
# Install dependencies
uv sync

# Run the server (from project root)
./run.sh
# Or manually:
cd backend && uv run uvicorn app:app --reload --port 8000

# Run a single backend module directly
cd backend && uv run python <module>.py
```

The app serves at `http://localhost:8000` with API docs at `http://localhost:8000/docs`.

## Environment Setup

Requires a `.env` file in the project root with `ANTHROPIC_API_KEY=<key>`.

## Architecture

This is a RAG (Retrieval-Augmented Generation) chatbot for course materials. The backend is a FastAPI server; the frontend is vanilla HTML/CSS/JS served as static files.

### Query Pipeline

User question → `RAGSystem.query()` → `AIGenerator` sends query to Claude with a registered tool → Claude optionally calls `search_course_content` tool → `CourseSearchTool` performs semantic search in ChromaDB → results fed back to Claude → final answer returned with sources.

Key detail: Claude decides whether to search via Anthropic's tool-use API. General knowledge questions are answered directly without retrieval.

### Document Ingestion Pipeline

On startup, `app.py` loads all `.txt`/`.pdf`/`.docx` files from `docs/` → `DocumentProcessor` parses structured course format (title, link, instructor, lessons) → text is split into sentence-aware chunks (800 chars, 100 overlap) → chunks + course metadata stored in ChromaDB via `VectorStore`.

### ChromaDB Collections

- `course_catalog` — One entry per course (title, instructor, link, lessons JSON). Used for semantic course name resolution (partial name → exact title).
- `course_content` — Chunked course text with metadata (course_title, lesson_number, chunk_index). Used for content retrieval.

### Key Design Patterns

- **Tool abstraction**: `search_tools.py` defines a `Tool` ABC and `ToolManager` registry. `CourseSearchTool` implements the interface. New tools can be added by subclassing `Tool` and registering with `ToolManager`.
- **Session management**: In-memory conversation history per session (not persisted across restarts). Capped at `MAX_HISTORY` exchanges (default 2).
- **Config**: All tuneable parameters (chunk size, overlap, model, max results) live in `config.py` as a dataclass.

### Course Document Format

Files in `docs/` follow a structured format:
```
Course Title: <title>
Course Link: <url>
Course Instructor: <name>

Lesson 0: <title>
Lesson Link: <url>
<content...>

Lesson 1: <title>
...
```

## API Endpoints

- `POST /api/query` — `{query, session_id?}` → `{answer, sources, session_id}`
- `GET /api/courses` — Returns `{total_courses, course_titles}`
