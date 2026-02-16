# Forever Learning Agents

A multi-agent voice AI platform for real-time conversational AI experiences including English tutoring, interview preparation, and general conversation practice.

## Agents

| Agent | Description |
|-------|-------------|
| **English Tutor** | Multi-agent English conversation practice with sequential handoff: conversation partner (4 min) then feedback provider (1 min) |
| **Interview Preparer** | AI mock interview coach with behavioral/technical/HR questions, powered by Gemini 2.5 Flash realtime audio |
| **Interview Agent** | Structured question-guided interviews with MOCK, PRACTICE, and DIAGNOSTIC modes. Optional Simli avatar support |
| **Speak With AI** | General question-guided conversation practice with evaluation support |

## Architecture

```
src/
├── main.py                          # Entry point, agent routing
├── agents/                          # Agent implementations
│   ├── english_tutor/               # Multi-agent orchestration (conversation + feedback)
│   ├── interview_agent/             # Question-guided interviews
│   ├── interview_preparer/          # Mock interview coach
│   └── speak_with_ai/              # General conversation
├── core/                            # Shared framework
│   ├── agents/                     # Base classes, factory, registry, mixins
│   ├── context/                    # Context management
│   ├── evaluation/                 # DeepEval evaluation framework
│   ├── instrumentation/            # Langfuse observability
│   ├── prompts/                    # Prompt building system
│   ├── session/                    # Session lifecycle, timing, checkpoints
│   └── transcripts/                # Transcript management
└── utils/                           # Utilities
```

Agents are registered via a **factory/registry pattern** - new agents can be added by implementing `BaseAgent` and registering in `main.py`. Reusable behaviors (session timing, graceful shutdown) are provided as mixins.

## Tech Stack

- **LiveKit Agents** v1.3.6 - Real-time voice agent framework
- **LLM/STT/TTS** - OpenAI, Google Gemini, Cartesia, Deepgram, Sarvam, Inworld
- **VAD** - Silero voice activity detection
- **Observability** - Langfuse + OpenTelemetry
- **Evaluation** - DeepEval
- **Noise Cancellation** - LiveKit Cloud

## Dev Setup

**Prerequisites:** Python 3.10+, [uv](https://docs.astral.sh/uv/)

```bash
# Install dependencies
uv sync

# Copy environment config
cp .env.example .env.local
```

Fill in `.env.local`:

```bash
LIVEKIT_URL=
LIVEKIT_API_KEY=
LIVEKIT_API_SECRET=
OPENAI_API_KEY=

# Optional - Simli Avatar for Interview Agent
SIMLI_API_KEY=
SIMLI_FACE_ID=
```

Or load LiveKit config via CLI:

```bash
lk cloud auth
lk app env -w -d .env.local
```

## Running

```bash
# Download required models (VAD, turn detector) - first run only
uv run python src/main.py download-files

# Console mode (talk in terminal)
uv run python src/main.py console

# Dev mode (with frontend)
uv run python src/main.py dev

# Production
uv run python src/main.py start
```

## Agent Routing

The frontend selects an agent via room metadata:

```json
{
  "agent_type": "english_tutor",
  "tutor_context": {
    "proficiency_level": "intermediate",
    "topics": ["technology", "travel"]
  }
}
```

Supported `agent_type` values: `english_tutor`, `speak_with_ai`, `interview_agent`, `interview_preparer`

## Tests

```bash
uv run pytest
```

## Deployment

A `Dockerfile` is included for production deployment. See the [LiveKit deployment guide](https://docs.livekit.io/agents/ops/deployment/) for details.

## Frontend

Compatible with any [LiveKit frontend](https://docs.livekit.io/agents/start/frontend/) or [SIP telephony](https://docs.livekit.io/agents/start/telephony/).

## License

MIT - see [LICENSE](LICENSE) for details.
