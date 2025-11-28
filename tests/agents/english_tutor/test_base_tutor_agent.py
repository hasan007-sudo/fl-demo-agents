import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from livekit.agents.llm import ChatContext, ChatMessage
from core.session.checkpoints import Checkpoint
from src.agents.english_tutor.agents.base_tutor_agent import BaseTutorAgent
from src.agents.english_tutor.context import EnglishTutorContext

# Mock concrete implementation of abstract BaseTutorAgent
class MockTutorAgent(BaseTutorAgent):

    def get_timing_config(self):
        return MagicMock()
    
    async def _on_enter_hook(self):
        pass

@pytest.mark.asyncio
async def test_checkpoint_instruction_queued():
    """
    Verify that _on_checkpoint_reached queues the instruction as a system message
    instead of generating an immediate reply.
    """
    # Setup mocks
    mock_session = AsyncMock()
    mock_chat_ctx = MagicMock(spec=ChatContext)
    mock_chat_ctx.items = []
    # Mock add_message to return a new context (or self for simplicity in mock)
    mock_chat_ctx.add_message.return_value = mock_chat_ctx
    
    mock_session.chat_ctx = mock_chat_ctx
    mock_session.update_chat_ctx = AsyncMock()
    mock_session.generate_reply = AsyncMock()
    
    # Initialize agent
    agent = MockTutorAgent(
        instructions="System prompt",
        context=MagicMock(spec=EnglishTutorContext)
    )
    # Inject mock session manually since we're not running full agent lifecycle
    agent._agent_session = mock_session
    
    # Create checkpoint with instruction
    checkpoint = Checkpoint(
        time=60,
        ai_instruction="Please wrap up soon",
        frontend_event=None,
        is_final=False
    )
    
    # Patch the session property to return our mock
    with patch.object(MockTutorAgent, 'session', new_callable=MagicMock) as mock_session_prop:
        # Configure the property mock to return our mock_session
        mock_session_prop.__get__ = MagicMock(return_value=mock_session)
        
        # Execute method under test
        await agent._on_checkpoint_reached(checkpoint, idx=0)
    
    # Verification 1: generate_reply should NOT be called
    mock_session.generate_reply.assert_not_called()
    
    # Verification 2: chat_ctx.add_message SHOULD be called with the instruction
    mock_chat_ctx.add_message.assert_called_once()
    call_kwargs = mock_chat_ctx.add_message.call_args.kwargs
    assert call_kwargs['role'] == 'system'
    assert call_kwargs['content'] == "Please wrap up soon"
    
    # Verification 3: update_chat_ctx SHOULD be called to persist changes
    mock_session.update_chat_ctx.assert_called_once()
