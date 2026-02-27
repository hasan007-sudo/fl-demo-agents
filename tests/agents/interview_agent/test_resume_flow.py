from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agents.interview_agent.agent import InterviewAgent
from agents.interview_agent.context import (
    InterviewAgentContext,
    InterviewMode,
    Question,
    ResumeTranscriptTurn,
)


def _build_metadata_with_resume(resume_state: dict) -> dict:
    return {
        "agent_type": "interview_agent",
        "context": {
            "mode": "diagnostic",
            "questions": [
                {
                    "identifier": "q1",
                    "text": "Q1",
                    "hint": "h1",
                    "description": "d1",
                },
                {
                    "identifier": "q2",
                    "text": "Q2",
                    "hint": "h2",
                    "description": "d2",
                },
            ],
            "resume_state": resume_state,
        },
    }


def test_context_parses_minimal_resume_payload_and_filters_invalid_data():
    metadata = _build_metadata_with_resume(
        {
            "current_question_id": "q2",
            "questions_discussed": ["q1", "unknown", "q1"],
            "transcript_turns": [
                {
                    "turn_id": "t1",
                    "role": "assistant",
                    "text": "Question one",
                    "question_id": "q1",
                    "timestamp": "2026-02-25T18:31:05Z",
                    "is_final": True,
                },
                {
                    "turn_id": "t2",
                    "role": "user",
                    "text": "My answer",
                    "question_id": "q1",
                    "timestamp": "2026-02-25T18:31:21Z",
                    "is_final": True,
                },
                {
                    "turn_id": "t3",
                    "role": "user",
                    "text": "partial",
                    "question_id": "q2",
                    "is_final": False,
                },
                {
                    "turn_id": "t4",
                    "role": "assistant",
                    "text": "unknown question",
                    "question_id": "unknown",
                    "is_final": True,
                },
                {"turn_id": "t5", "role": "system", "text": "bad role", "is_final": True},
            ],
        }
    )

    context = InterviewAgentContext.from_metadata(metadata)

    assert context.is_resumed is True
    assert context.current_question_id == "q2"
    assert context.questions_discussed == ["q1"]
    assert len(context.resume_transcript_turns) == 2
    assert context.resume_transcript_turns[0].turn_id == "t1"
    assert context.resume_transcript_turns[1].turn_id == "t2"


def test_context_ignores_invalid_current_question():
    metadata = _build_metadata_with_resume(
        {
            "current_question_id": "unknown",
            "questions_discussed": ["q1"],
            "transcript_turns": [],
        }
    )

    context = InterviewAgentContext.from_metadata(metadata)
    assert context.current_question_id is None
    assert context.questions_discussed == ["q1"]
    assert context.is_resumed is True
    assert context.resume_rejected_reason is None


def test_context_rejects_invalid_schema_resume_state():
    metadata = _build_metadata_with_resume("invalid")
    context = InterviewAgentContext.from_metadata(metadata)

    assert context.is_resumed is False
    assert context.resume_rejected_reason == "invalid_schema"


def test_context_rejects_question_mismatch_resume_state():
    metadata = _build_metadata_with_resume(
        {
            "current_question_id": "unknown",
            "questions_discussed": ["unknown-q"],
            "transcript_turns": [
                {
                    "turn_id": "x1",
                    "role": "assistant",
                    "text": "hello",
                    "question_id": "unknown-q",
                    "is_final": True,
                }
            ],
        }
    )
    context = InterviewAgentContext.from_metadata(metadata)

    assert context.is_resumed is False
    assert context.resume_rejected_reason == "question_mismatch"


@pytest.mark.asyncio
async def test_on_enter_diagnostic_resumes_from_current_question():
    context = InterviewAgentContext(
        agent_type="interview_agent",
        mode=InterviewMode.DIAGNOSTIC,
        questions=[
            Question(identifier="q1", text="Q1", hint="", description=""),
            Question(identifier="q2", text="Q2", hint="", description=""),
        ],
        questions_discussed=["q1"],
        current_question_id="q2",
        is_resumed=True,
        resume_transcript_turns=[
            ResumeTranscriptTurn(role="assistant", text="Q1"),
            ResumeTranscriptTurn(role="user", text="A1"),
        ],
    )

    agent = InterviewAgent(context=context)
    agent._init_timing = MagicMock()
    agent._restore_resume_chat_context = AsyncMock(return_value=2)
    agent._publish_session_event = AsyncMock()
    agent._graceful_shutdown = AsyncMock()

    mock_session = AsyncMock()
    mock_session.generate_reply = AsyncMock()
    agent._agent_session = mock_session

    with patch.object(InterviewAgent, "session", new_callable=MagicMock) as mock_session_prop:
        mock_session_prop.__get__ = MagicMock(return_value=mock_session)
        await agent.on_enter()

    mock_session.generate_reply.assert_called_once()
    instructions = mock_session.generate_reply.call_args.kwargs["instructions"]
    assert 'start_question("q2")' in instructions

    agent._publish_session_event.assert_any_await(
        event_type="resume_state_applied",
        status="ready",
        metadata={
            "is_resumed": True,
            "current_question_id": "q2",
            "questions_discussed": ["q1"],
            "remaining_count": 1,
            "restored_turn_count": 2,
        },
    )
    rejected_calls = [
        c for c in agent._publish_session_event.await_args_list
        if c.kwargs.get("event_type") == "resume_state_rejected"
    ]
    assert not rejected_calls
    agent._graceful_shutdown.assert_not_awaited()


@pytest.mark.asyncio
async def test_on_enter_ends_when_all_questions_discussed():
    context = InterviewAgentContext(
        agent_type="interview_agent",
        mode=InterviewMode.DIAGNOSTIC,
        questions=[Question(identifier="q1", text="Q1", hint="", description="")],
        questions_discussed=["q1"],
        current_question_id=None,
        is_resumed=True,
    )

    agent = InterviewAgent(context=context)
    agent._init_timing = MagicMock()
    agent._restore_resume_chat_context = AsyncMock(return_value=0)
    agent._publish_session_event = AsyncMock()
    agent._graceful_shutdown = AsyncMock()

    mock_session = AsyncMock()
    mock_session.generate_reply = AsyncMock()
    agent._agent_session = mock_session

    with patch.object(InterviewAgent, "session", new_callable=MagicMock) as mock_session_prop:
        mock_session_prop.__get__ = MagicMock(return_value=mock_session)
        await agent.on_enter()

    agent._graceful_shutdown.assert_awaited_once()
    mock_session.generate_reply.assert_not_called()


@pytest.mark.asyncio
async def test_on_enter_publishes_resume_rejected_event():
    context = InterviewAgentContext(
        agent_type="interview_agent",
        mode=InterviewMode.DIAGNOSTIC,
        questions=[Question(identifier="q1", text="Q1", hint="", description="")],
        is_resumed=False,
        resume_rejected_reason="invalid_schema",
    )

    agent = InterviewAgent(context=context)
    agent._init_timing = MagicMock()
    agent._restore_resume_chat_context = AsyncMock(return_value=0)
    agent._publish_session_event = AsyncMock()
    agent._graceful_shutdown = AsyncMock()

    mock_session = AsyncMock()
    mock_session.generate_reply = AsyncMock()
    agent._agent_session = mock_session

    with patch.object(InterviewAgent, "session", new_callable=MagicMock) as mock_session_prop:
        mock_session_prop.__get__ = MagicMock(return_value=mock_session)
        await agent.on_enter()

    agent._publish_session_event.assert_any_await(
        event_type="resume_state_rejected",
        status="warning",
        reason="invalid_schema",
        metadata={
            "is_resumed": False,
            "current_question_id": None,
            "questions_discussed": [],
            "restored_turn_count": 0,
        },
    )
