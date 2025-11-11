# Agent Architecture Documentation

## Table of Contents
1. [Overview](#overview)
2. [Request Flow](#request-flow)
3. [Core Components](#core-components)
4. [Agent-Specific Implementation](#agent-specific-implementation)
5. [Adding New Agents](#adding-new-agents)
6. [Code Examples](#code-examples)

## Overview

This system supports multiple AI agents (English Tutor and Interview Preparer) with a scalable architecture that makes it easy to add new agents without modifying existing code.

### Problem We're Solving
- Previously: All code was specific to English Tutor, making it hard to add new agent types
- Now: Clean separation between agents with shared infrastructure
- Result: Easy to add new agents, maintain existing ones, and ensure consistency

### High-Level Architecture
```
Frontend (sends agentType + context)
    ↓
main.py (routes based on agentType)
    ↓
Agent Factory (creates the right agent)
    ↓
Specific Agent (English Tutor or Interview Preparer)
    ↓
LiveKit Session (handles the conversation)
```

## Request Flow

### Step-by-Step: What Happens When a User Connects

1. **Frontend Sends Data**
   ```json
   {
     "agentType": "english_tutor",
     "tutorPersona": "friendly",
     "correctionPreference": "let_me_finish",
     // ... other preferences
   }
   ```

2. **main.py Receives Request**
   - Parses the room metadata from LiveKit
   - Extracts `agentType` field
   - Routes to appropriate agent

3. **Agent Factory Creates Agent**
   - Looks up agent type in Registry
   - Creates the specific agent (EnglishTutorAgent or InterviewPreparerAgent)
   - Passes the context data to the agent

4. **Agent Initialization**
   - Agent receives context (user preferences)
   - PromptBuilder creates AI instructions based on context
   - Session manager sets up LiveKit connection

5. **Conversation Starts**
   - Agent is now ready with proper instructions
   - User can start talking
   - Agent responds according to its configuration

### Visual Flow Diagram
```
┌──────────┐     ┌──────────┐     ┌──────────┐     ┌──────────┐
│ Frontend │────>│  main.py │────>│  Factory │────>│  Agent   │
└──────────┘     └──────────┘     └──────────┘     └──────────┘
     │                │                 │                │
     │                │                 │                │
  Sends:          Extracts:         Creates:         Becomes:
  agentType       agentType        Correct Agent    Active Session
  + context       from JSON        with context     with User
```

## Core Components

### 1. BaseAgent (`src/core/agents/base.py`)
**What it is:** The blueprint all agents follow

**Real-world analogy:** Like a franchise manual - all restaurants need kitchen, seating, menu, but each location customizes

**Key responsibilities:**
- Defines what every agent must have (metadata, instructions, session handling)
- Handles LiveKit integration
- Manages agent lifecycle (start, stop, session management)

**What agents inherit:**
- Session management
- Instruction building framework
- Context handling
- LiveKit connection logic

### 2. BaseContext (`src/core/context/base.py`)
**What it is:** The data structure for user preferences

**Real-world analogy:** Like an order form - standardizes how preferences are captured

**Key responsibilities:**
- Defines the `agent_type` field that all contexts have
- Provides validation
- Handles JSON conversion

**How it's used:**
```python
# English Tutor adds its specific fields
@dataclass
class EnglishTutorContext(BaseContext):
    tutor_persona: str  # "friendly", "strict", etc.
    correction_preference: str  # "immediate", "let_me_finish", etc.
    # ... other English Tutor specific fields

# Interview Preparer adds different fields
@dataclass
class InterviewContext(BaseContext):
    interview_type: str  # "technical", "behavioral", etc.
    role: str  # "software_engineer", "product_manager", etc.
    # ... other Interview specific fields
```

### 3. BasePromptBuilder (`src/core/prompts/base.py`)
**What it is:** Creates AI instructions from user preferences

**Real-world analogy:** Like a recipe builder - takes ingredients (preferences) and creates a recipe (AI instructions)

**Key responsibilities:**
- Takes context and builds prompt
- Provides consistent structure (role, personality, instructions, constraints)
- Each agent customizes for their needs

**Example output:**
```
# For English Tutor with friendly persona:
"You are a friendly English tutor. Speak slowly.
Only correct major errors. Be encouraging..."

# For Interview Preparer in technical mode:
"You are conducting a technical interview for a senior engineer.
Ask algorithm questions. Evaluate problem-solving approach..."
```

### 4. Agent Registry (`src/core/agents/registry.py`)
**What it is:** A list of all available agents

**Real-world analogy:** Like a restaurant menu - lists what's available

**Key responsibilities:**
- Keeps track of available agents
- Maps "english_tutor" → EnglishTutorAgent class
- Maps "interview_preparer" → InterviewPreparerAgent class

### 5. Agent Factory (`src/core/agents/factory.py`)
**What it is:** Creates agents with proper configuration

**Real-world analogy:** Like a car factory - builds the specific model with chosen options

**Key responsibilities:**
- Takes agent type and context
- Creates the right agent instance
- Applies configuration
- Returns ready-to-use agent

### 6. Session Manager (`src/core/session/manager.py`)
**What it is:** Handles LiveKit session setup

**Real-world analogy:** Like a conference room manager - sets up the room with right equipment

**Key responsibilities:**
- Sets up OpenAI Realtime connection
- Configures voice settings
- Enables noise cancellation
- Manages session lifecycle

## Agent-Specific Implementation

### English Tutor Agent

**Location:** `src/agents/english_tutor/`

**Components:**
1. **agent.py** - Main agent class
2. **context.py** - TutorContext with all existing fields (NO CHANGES)
3. **prompt_builder.py** - Builds tutor-specific instructions

**Context fields (unchanged):**
- `tutor_persona`: "encouraging", "neutral", "strict", "fun"
- `user_proficiency`: "A1", "A2", "B1", "B2", "C1", "C2"
- `correction_preference`: "immediate", "let_me_finish", "major_only", "focus_on_fluency"
- `speaking_speed`: "slow", "moderate", "fast", "natural"
- `user_native_language`: User's native language
- All other existing fields remain exactly the same

### Interview Preparer Agent

**Location:** `src/agents/interview_preparer/`

**Components:**
1. **agent.py** - Main agent class
2. **context.py** - InterviewContext with interview-specific fields
3. **prompt_builder.py** - Builds interview-specific instructions

**Context fields (new):**
- `interview_type`: "technical", "behavioral", "hr", "case_study"
- `role`: "software_engineer", "product_manager", "data_scientist", etc.
- `experience_level`: "entry", "mid", "senior", "executive"
- `industry`: "tech", "finance", "healthcare", etc.
- `interview_style`: "friendly", "formal", "challenging"
- `feedback_mode`: "immediate", "end_of_answer", "summary"

## Adding New Agents

### Step-by-Step Guide to Add a New Agent

Let's say you want to add a "Language Translator" agent:

#### 1. Create the folder structure
```
src/agents/language_translator/
├── __init__.py
├── agent.py
├── context.py
└── prompt_builder.py
```

#### 2. Define the context (`context.py`)
```python
from dataclasses import dataclass
from src.core.context.base import BaseContext

@dataclass
class TranslatorContext(BaseContext):
    source_language: str
    target_language: str
    formality_level: str  # "casual", "formal", "business"
    domain: str  # "general", "technical", "medical", etc.
```

#### 3. Create the prompt builder (`prompt_builder.py`)
```python
from src.core.prompts.base import BasePromptBuilder

class TranslatorPromptBuilder(BasePromptBuilder):
    def build(self, context):
        return f"""
        You are a professional translator.
        Translate from {context.source_language} to {context.target_language}.
        Use {context.formality_level} tone.
        Focus on {context.domain} terminology.
        """
```

#### 4. Implement the agent (`agent.py`)
```python
from src.core.agents.base import BaseAgent

class LanguageTranslatorAgent(BaseAgent):
    # Auto-register this agent
    auto_register = True
    registration_name = "language_translator"

    @property
    def metadata(self):
        return AgentMetadata(
            name="Language Translator",
            version="1.0.0",
            description="Translates between languages",
            supported_languages=["all"],
            capabilities=["translation", "interpretation"]
        )
```

#### 5. Register in main.py
The agent will be automatically discovered and registered!

#### 6. Frontend sends
```json
{
  "agentType": "language_translator",
  "sourceLanguage": "english",
  "targetLanguage": "spanish",
  "formalityLevel": "casual",
  "domain": "general"
}
```

## Code Examples

### Example 1: How Context Flows Through the System

```python
# 1. Frontend sends JSON
frontend_data = {
    "agentType": "english_tutor",
    "tutorPersona": "friendly",
    "userProficiency": "B1"
}

# 2. main.py parses it
agent_type = frontend_data["agentType"]  # "english_tutor"

# 3. Factory creates agent with context
agent = factory.create(
    agent_type="english_tutor",
    context=EnglishTutorContext(
        agent_type="english_tutor",
        tutor_persona="friendly",
        user_proficiency="B1"
    )
)

# 4. Agent uses context to build instructions
instructions = agent.prompt_builder.build(agent.context)
# Result: "You are a friendly English tutor for a B1 level student..."
```

### Example 2: How the Factory Works

```python
class AgentFactory:
    def create(self, agent_type: str, context: BaseContext):
        # 1. Look up agent in registry
        agent_class = registry.get(agent_type)

        # 2. Create agent instance
        agent = agent_class(context=context)

        # 3. Return ready agent
        return agent
```

### Example 3: Complete Flow for English Tutor

```python
# Room metadata from frontend
room_metadata = '''
{
    "agentType": "english_tutor",
    "tutorPersona": "encouraging",
    "userProficiency": "B2",
    "correctionPreference": "let_me_finish",
    "speakingSpeed": "moderate"
}
'''

# main.py processes this
async def entrypoint(room: Room):
    # Parse metadata
    data = json.loads(room.metadata)
    agent_type = data["agentType"]

    # Create appropriate context
    if agent_type == "english_tutor":
        context = EnglishTutorContext(**data)
    elif agent_type == "interview_preparer":
        context = InterviewContext(**data)

    # Create agent
    agent = factory.create(agent_type, context)

    # Start session
    session = await session_manager.create_session(agent, room)
```

## Benefits of This Architecture

1. **Scalability**: Easy to add new agents without changing existing code
2. **Maintainability**: Each agent is isolated in its own module
3. **Consistency**: All agents follow the same patterns
4. **Testability**: Each component can be tested independently
5. **Flexibility**: Agents can have completely different behaviors while sharing infrastructure
6. **No Frontend Changes**: English Tutor works exactly as before

## Summary

The architecture follows these principles:
- **Separation of Concerns**: Each agent handles its own logic
- **Don't Repeat Yourself (DRY)**: Common code is shared
- **Open/Closed Principle**: Open for extension (new agents), closed for modification
- **Single Responsibility**: Each class has one clear purpose
- **Dependency Inversion**: Depend on abstractions (BaseAgent), not concrete implementations

This design ensures that:
- Adding a new agent is straightforward
- Existing agents remain unaffected
- Frontend changes are minimal (just add `agentType`)
- Code is easy to understand and maintain