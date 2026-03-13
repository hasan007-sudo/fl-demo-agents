from src.core.instrumentation import langfuse_setup
from src.agents.interview_agent.context import InterviewAgentContext


class _DummyRoom:
    def __init__(self, name: str):
        self.name = name


class _DummyCtx:
    def __init__(self, room_name: str):
        self.room = _DummyRoom(room_name)
        self._callbacks = []

    def add_shutdown_callback(self, fn):
        self._callbacks.append(fn)


def _make_metadata():
    return {
        "agentType": "interview_agent",
        "context": {
            "studentName": "John",
            "email": "john@test.com",
            "mode": "diagnostic",
            "questions": [
                {
                    "text": "Tell me about yourself",
                    "hint": "Focus on strengths",
                    "identifier": "q1",
                    "description": "Intro question",
                }
            ],
        },
    }


def test_langfuse_metadata_includes_room_name(monkeypatch):
    captured = {}

    def _fake_setup_langfuse(metadata=None):
        captured["metadata"] = metadata
        return False

    monkeypatch.setattr(langfuse_setup, "setup_langfuse", _fake_setup_langfuse)

    ctx = _DummyCtx("room-123")
    context = InterviewAgentContext.from_metadata(_make_metadata())

    langfuse_setup.setup_langfuse_for_session(ctx, context)

    metadata = captured["metadata"]
    assert metadata is not None
    assert "room-123" in metadata.get("langfuse.session.id", "")
    assert "room-123" in metadata.get("langfuse.trace.name", "")
