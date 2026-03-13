import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.agents.interview_agent.context import (
    InterviewAgentContext,
    InterviewMode,
    Question,
)
from src.agents.interview_agent.config import get_timing_config
from src.agents.interview_agent.prompt_builder import InterviewPromptBuilder
from src.agents.interview_agent.agent import InterviewAgent


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_questions():
    """Return a standard two-question list used across tests."""
    return [
        {"text": "Tell me about yourself", "hint": "Focus on strengths",
         "identifier": "q1", "description": "Intro question"},
        {"text": "Why this role?", "hint": "Show research",
         "identifier": "q2", "description": "Motivation"},
    ]


def _make_metadata(extra_context=None, questions=None):
    """Build a full metadata dict with optional overrides."""
    ctx = {
        "studentName": "John",
        "email": "john@test.com",
        "mode": "practice",
        "questions": questions if questions is not None else _make_questions(),
    }
    if extra_context:
        ctx.update(extra_context)
    return {"agentType": "interview_agent", "context": ctx}


def _make_run_context(userdata):
    """Create a mock RunContext whose .userdata is the given context."""
    rc = MagicMock()
    rc.userdata = userdata
    return rc


# ===========================================================================
# 1. Context Parsing  (InterviewAgentContext.from_metadata)
# ===========================================================================

class TestContextParsing:

    def test_valid_metadata(self):
        metadata = _make_metadata()
        ctx = InterviewAgentContext.from_metadata(metadata)

        assert ctx.student_name == "John"
        assert ctx.email == "john@test.com"
        assert ctx.mode == InterviewMode.PRACTICE
        assert len(ctx.questions) == 2
        assert ctx.questions[0].identifier == "q1"
        assert ctx.questions[1].text == "Why this role?"

    def test_missing_optional_fields_use_defaults(self):
        metadata = {
            "agentType": "interview_agent",
            "context": {
                "questions": _make_questions(),
            },
        }
        ctx = InterviewAgentContext.from_metadata(metadata)

        assert ctx.student_name is None
        assert ctx.email is None
        assert ctx.mode == InterviewMode.PRACTICE  # default
        assert ctx.is_resumed is False
        assert ctx.questions_discussed == []

    def test_resume_state_applied(self):
        metadata = _make_metadata(extra_context={
            "resumeState": {
                "questionsDiscussed": ["q1"],
                "currentQuestionId": "q2",
                "conversationSummary": "Discussed q1 about background",
            },
        })
        ctx = InterviewAgentContext.from_metadata(metadata)

        assert ctx.is_resumed is True
        assert ctx.questions_discussed == ["q1"]
        assert ctx.current_question_id == "q2"
        assert ctx.conversation_summary == "Discussed q1 about background"
        assert ctx.resume_rejected_reason is None

    def test_resume_state_invalid_schema(self):
        """Non-dict resume_state should be rejected with invalid_schema."""
        metadata = _make_metadata(extra_context={
            "resumeState": "not_a_dict",
        })
        ctx = InterviewAgentContext.from_metadata(metadata)

        assert ctx.is_resumed is False
        assert ctx.resume_rejected_reason == "invalid_schema"

    def test_resume_state_question_mismatch(self):
        """questionsDiscussed with IDs not in the questions list => question_mismatch."""
        metadata = _make_metadata(extra_context={
            "resumeState": {
                "questionsDiscussed": ["nonexistent_id"],
                "currentQuestionId": None,
            },
        })
        ctx = InterviewAgentContext.from_metadata(metadata)

        assert ctx.is_resumed is False
        assert ctx.resume_rejected_reason == "question_mismatch"

    def test_camel_case_keys(self):
        metadata = {
            "agentType": "interview_agent",
            "context": {
                "studentName": "Alice",
                "genderPreference": "female",
                "comfortableLanguage": "Hindi",
                "isFeedbackEnabled": False,
                "questions": _make_questions(),
                "mode": "mock",
            },
        }
        ctx = InterviewAgentContext.from_metadata(metadata)

        assert ctx.student_name == "Alice"
        assert ctx.gender_preference == "female"
        assert ctx.comfortable_language == "Hindi"
        assert ctx.is_feedback_enabled is False
        assert ctx.mode == InterviewMode.MOCK


# ===========================================================================
# 2. Tool Behaviour  (start_question / record_question_discussed)
# ===========================================================================

class TestToolBehaviour:

    def _build_agent_and_context(self):
        """Create an InterviewAgent with a minimal context, mock _publish_session_event."""
        ctx = InterviewAgentContext.from_metadata(_make_metadata())
        agent = InterviewAgent(context=ctx)
        agent._publish_session_event = AsyncMock()
        return agent, ctx

    @pytest.mark.asyncio
    async def test_start_question_valid(self):
        agent, ctx = self._build_agent_and_context()
        rc = _make_run_context(ctx)

        result = await agent.start_question(rc, "q1")

        assert "Tell me about yourself" in result
        assert ctx.current_question_id == "q1"

    @pytest.mark.asyncio
    async def test_start_question_invalid_identifier(self):
        agent, ctx = self._build_agent_and_context()
        rc = _make_run_context(ctx)

        result = await agent.start_question(rc, "nonexistent")

        assert "not found" in result.lower()

    @pytest.mark.asyncio
    async def test_record_question_discussed_success(self):
        agent, ctx = self._build_agent_and_context()
        rc = _make_run_context(ctx)

        # Set current question first
        ctx.set_current_question("q1")
        result = await agent.record_question_discussed(rc, "q1")

        assert result is True
        assert "q1" in ctx.questions_discussed

    @pytest.mark.asyncio
    async def test_record_question_discussed_already_discussed(self):
        agent, ctx = self._build_agent_and_context()
        rc = _make_run_context(ctx)

        ctx.set_current_question("q1")
        await agent.record_question_discussed(rc, "q1")
        result = await agent.record_question_discussed(rc, "q1")

        assert result is False

    @pytest.mark.asyncio
    async def test_record_question_discussed_unknown_identifier(self):
        agent, ctx = self._build_agent_and_context()
        rc = _make_run_context(ctx)

        result = await agent.record_question_discussed(rc, "nonexistent")

        assert result is False


# ===========================================================================
# 3. Timing Config
# ===========================================================================

class TestTimingConfig:

    def test_practice_mode(self):
        config = get_timing_config(InterviewMode.PRACTICE)

        assert config.max_duration == 300
        assert len(config.checkpoints) == 3
        assert config.checkpoints[0].time == 180
        assert config.checkpoints[1].time == 270
        assert config.checkpoints[2].time == 300
        assert config.checkpoints[2].is_final is True

    def test_mock_mode(self):
        config = get_timing_config(InterviewMode.MOCK)

        assert config.max_duration == 300
        assert len(config.checkpoints) == 1
        assert config.checkpoints[0].time == 280
        assert config.checkpoints[0].is_final is True

    def test_diagnostic_mode(self):
        config = get_timing_config(InterviewMode.DIAGNOSTIC)

        assert config.max_duration == 300
        assert len(config.checkpoints) == 0


# ===========================================================================
# 4. Prompt Rendering
# ===========================================================================

class TestPromptRendering:

    def _build_context(self, mode: str, **overrides):
        extra = {"mode": mode}
        extra.update(overrides)
        metadata = _make_metadata(extra_context=extra)
        return InterviewAgentContext.from_metadata(metadata)

    def test_practice_mode_renders(self):
        ctx = self._build_context("practice")
        builder = InterviewPromptBuilder()
        prompt = builder.build(ctx)

        assert len(prompt) > 0
        assert "John" in prompt  # student_name
        assert "q1" in prompt    # questions summary contains identifiers

    def test_mock_mode_renders(self):
        ctx = self._build_context("mock")
        builder = InterviewPromptBuilder()
        prompt = builder.build(ctx)

        assert len(prompt) > 0
        assert "MOCK INTERVIEW" in prompt.upper() or "mock" in prompt.lower()

    def test_diagnostic_mode_renders(self):
        ctx = self._build_context("diagnostic", isFeedbackEnabled=False)
        builder = InterviewPromptBuilder()
        prompt = builder.build(ctx)

        assert len(prompt) > 0
        assert "DIAGNOSTIC" in prompt.upper() or "diagnostic" in prompt.lower()
        assert "Never mention tools" in prompt
        assert "PER-QUESTION FLOW (TEXT EXAMPLE)" in prompt
        assert "┌" not in prompt

    def test_all_modes_produce_nonempty_output(self):
        builder = InterviewPromptBuilder()
        for mode in ("practice", "mock", "diagnostic"):
            ctx = self._build_context(mode)
            prompt = builder.build(ctx)
            assert len(prompt) > 0, f"Prompt was empty for mode={mode}"
