# Agentic Company Platform

![alt text](image.png)

Internal AI platform for company use. A chat interface backed by LangGraph agents, a RAG pipeline over documents pulled from Notion, Google Drive and S3, a Jira integration for filing tickets from a conversation, and tools for admins to build, test and monitor agents.

## Stack

- **Backend:** FastAPI (Python 3.12), SQLAlchemy async ORM, Alembic migrations
- **Frontend:** React 19, Vite, TailwindCSS, Zustand
- **Agent engine:** LangGraph with PostgreSQL checkpointing
- **Vector store:** Qdrant (dense + keyword search combined, then reranked)
- **Task queue:** Celery with Redis
- **LLMs:** OpenAI models, plus optional local models through Ollama
- **Infra:** Docker Compose

## Architecture

### Backend (`backend/`)

**Agent runtime** (`app/agents/`): a compiled LangGraph that routes each message to an agent node. Agents are rows in the `agent_settings` table (slug, system prompt, model, tools, knowledge sources) and can be edited as a draft, then published. Every published version is kept, so an agent can be rolled back.

**Agent conscience** (`app/services/emotion.py`, `app/services/memory.py`): optional, three separate switches per agent.
- **Memory**: the agent remembers facts, preferences and commitments about each user, merges duplicates, and updates a fact instead of contradicting itself when something changes (e.g. a job change keeps the old fact as history and marks it no longer current). Each memory keeps a link back to the exact message it came from, so the agent can quote the original conversation when asked to recall something specific. Old, unused memories fade over time through a weekly cleanup task.
- **Emotions**: the agent keeps a running emotional state toward each user that settles back to a baseline over time, and reads the mood of the user's current message. Both quietly shape the tone of the reply, never stated out loud.
- **Episodes**: a memory of moments that genuinely went wrong (not just strong feelings) for the agent to be more careful next time.
- When memory is on, the agent also checks its own draft reply against what it knows before sending, and rewrites it if it contradicts itself.

**RAG pipeline** (`app/services/rag.py`): documents are split into chunks, embedded, and stored in Qdrant. A search combines a semantic (embedding) search and a keyword search, then reranks the combined results before handing them to the agent. Answers link back to the original document.

**Knowledge sources and connectors** (`app/services/gdrive.py`, `notion.py`, `s3.py`): a knowledge source is a named, syncable set of documents (a Drive folder, a Notion database or page tree, an S3 bucket/prefix) tied to one saved, encrypted connector credential. Syncing is incremental by default: only new or changed files are re-processed, and files removed from the source are removed from the index too. PDF, Word, text, Markdown, CSV and Excel files are supported; CSV/Excel rows are converted to plain text tables rather than dumped as raw data.

**Jira** (`app/services/jira.py`): not part of the RAG index. From a chat conversation, an admin can ask the agent to draft a ticket summary and description, review it, and create the real Jira issue through the Jira REST API.

**Agent workflows** (`app/api/agent_workflows.py`): an optional fixed pipeline for one agent, defined as a set of steps with explicit inputs and outputs (a step can reference the original message or the output of an earlier step). When enabled, the agent runs this pipeline instead of its normal free form reasoning.

**Skills** (`app/api/admin_skills.py`): reusable written instructions an agent can pull in on demand, shared across agents or private to one. The agent only sees a skill's name and short description in its prompt, and fetches the full instructions only when it decides they're relevant, keeping the prompt short.

**Agent evaluation** (`app/api/agent_eval.py`): question and expected answer pairs grouped into test sets per agent. Running a test set replays each question through the real agent and scores the answer for correctness, relevance and faithfulness to the retrieved sources. Runs can be triggered manually or on a schedule.

**Agent templates** (`app/data/agent_templates/`): ready made starting configurations (chat assistant, general router, finance, HR, IT support, deep research) an admin can deploy in one step to get a new, unpublished agent to review and adjust.

**Usage and budgets** (`app/services/token_tracker.py`): every LLM call is logged with token counts and estimated cost. Admins can set a monthly budget per user or per agent; going over it shows a warning in the chat but does not block the request.

**Feedback** (`app/api/feedback.py`): thumbs up or down on any assistant reply, with an optional comment and screenshot, snapshotting the conversation at the time.

**Health** (`app/api/health.py`, `admin_status.py`): checks that the database, Qdrant and Redis are reachable, and gives admins a combined view of that plus every knowledge source's sync status.

### Frontend (`frontend/`)

- **Pages:** chat, and admin screens for agents, agent templates, skills, connectors, knowledge sources, users, LLM models, usage and health.
- **Chat components:** agent switcher, composer, message list, and a memory panel where a user can see, search and delete what an agent remembers about them (only shown for agents with memory turned on).
- **State:** Zustand for auth and global state.
- **API client:** `src/lib/api.ts` handles REST calls and reads the SSE chat stream.

## Services (Docker Compose)

| Service | Role | Port |
|---|---|---|
| `postgres` | Primary database | 5433 |
| `qdrant` | Vector database | 6333 |
| `redis` | Celery broker/cache | 6379 |
| `ollama` | Optional local LLM runtime | 11434 |
| `backend` | FastAPI app | 8000 |
| `frontend` | Vite dev server | 5173 |
| `celery-worker` | Background task worker | - |
| `celery-beat` | Periodic task scheduler | - |

## Setup

1. **Copy environment variables:**
   ```bash
   cp .env.example .env
   # edit .env and fill in API keys (OpenAI and others)
   ```

2. **Run everything:**
   ```bash
   docker compose up --build
   ```

3. **Run migrations (first time, or after pulling schema changes):**
   ```bash
   docker compose exec backend uv run alembic upgrade head
   ```
   If migrations were already applied before a schema change landed, `upgrade head` does nothing (Alembic thinks the single migration is already done). Reset with:
   ```bash
   docker compose exec backend uv run alembic downgrade base
   docker compose exec backend uv run alembic upgrade head
   docker compose restart backend
   ```

4. **Seed demo data (optional, first time only):**
   ```bash
   docker compose exec backend uv run python scripts/seed_users.py
   ```
   Creates the admin user from `ADMIN_EMAIL`/`ADMIN_PASSWORD` plus any demo accounts in `backend/scripts/demo_users.json` or the `DEMO_USERS` env var.

5. **Access the app:**
   - Frontend: http://localhost:5173
   - API docs: http://localhost:8000/api/docs

## Key Concepts

- **Agents:** rows in `agent_settings`. Each has a slug, system prompt, model, tools, and optional knowledge sources, and can act as a router or orchestrator that hands off to other agents.
- **Conscience:** memory, emotions and episodes, each a separate switch per agent (see Architecture above).
- **Knowledge sources:** synced document sets stored in Qdrant, scoped to specific agents.
- **Connectors:** saved, encrypted credentials for Notion, Google Drive, S3 and Jira.
- **Context modes:** chat supports `quick`, `mid`, and `deep` modes, adjusting how much is retrieved and how large the token budget is.
- **Agent versioning:** agents are edited as a draft and published; every published version is kept and can be restored.
