# English Tutor Agent - Frontend Integration Guide

This guide shows how to pass user preferences from your frontend to the LiveKit English Tutor agent.

## Quick Start

The agent receives configuration via **room metadata** when the frontend creates or joins a room.

### Minimal Required Code

```javascript
// 1. Create tutor preferences object
const tutorContext = {
  proficiency_level: "intermediate",  // User's English level
  topics: ["technology", "travel"],   // Topics to discuss
  tutor_style: "encouraging"          // Teaching style
};

// 2. Attach to room connection
const room = new Room();
await room.connect(wsURL, token, {
  metadata: JSON.stringify({ tutor_context: tutorContext })
});
```

That's it! The agent will receive this data and personalize the tutoring session.

## Frontend Implementation

### JavaScript/TypeScript Example

```javascript
import { Room } from 'livekit-client';

// 1. Collect user preferences from your UI (forms, dropdowns, etc.)
const tutorContext = {
  proficiency_level: "intermediate",     // "beginner" | "intermediate" | "advanced"
  topics: ["technology", "travel"],       // Array of topics user wants to discuss
  learning_goals: ["fluency", "vocabulary"], // What user wants to improve
  tutor_style: "encouraging",             // "formal" | "casual" | "encouraging" | "patient"
  correction_style: "end-of-turn"         // "immediate" | "end-of-turn" | "summary"
};

// 2. Wrap in metadata structure
const metadata = JSON.stringify({
  tutor_context: tutorContext
});

// 3. Connect to room with metadata
const room = new Room();
await room.connect(wsURL, token, {
  metadata: metadata  // Pass metadata here
});
```

### React Example

```jsx
import { useState } from 'react';
import { useRoomContext } from '@livekit/components-react';

function TutorSetup() {
  const [level, setLevel] = useState('intermediate');
  const [topics, setTopics] = useState([]);
  const [style, setStyle] = useState('encouraging');
  const room = useRoomContext();

  const startLesson = async () => {
    // Prepare tutor context
    const tutorContext = {
      proficiency_level: level,
      topics: topics,
      learning_goals: ["fluency", "vocabulary"],
      tutor_style: style,
      correction_style: "end-of-turn"
    };

    // Convert to JSON metadata
    const metadata = JSON.stringify({
      tutor_context: tutorContext
    });

    // Connect with metadata
    await room.connect(wsURL, token, { metadata });
  };

  return (
    <div>
      <select value={level} onChange={(e) => setLevel(e.target.value)}>
        <option value="beginner">Beginner</option>
        <option value="intermediate">Intermediate</option>
        <option value="advanced">Advanced</option>
      </select>

      {/* Add more UI controls for topics, style, etc. */}

      <button onClick={startLesson}>Start Lesson</button>
    </div>
  );
}
```

### React Native Example

```javascript
import { Room } from '@livekit/react-native';

const connectToTutor = async (userPreferences) => {
  const metadata = JSON.stringify({
    tutor_context: {
      proficiency_level: userPreferences.level,
      topics: userPreferences.selectedTopics,
      learning_goals: userPreferences.goals,
      tutor_style: userPreferences.style,
      correction_style: userPreferences.correctionType
    }
  });

  const room = new Room();
  await room.connect(url, token, { metadata });
};
```

## Metadata Structure

### Complete Example

```json
{
  "tutor_context": {
    "proficiency_level": "intermediate",
    "topics": ["technology", "travel", "daily life"],
    "learning_goals": ["improve fluency", "expand vocabulary"],
    "tutor_style": "encouraging",
    "correction_style": "end-of-turn"
  }
}
```

### Field Reference

| Field | Type | Options | Default |
|-------|------|---------|---------|
| `proficiency_level` | string | `beginner`, `intermediate`, `advanced` | `intermediate` |
| `topics` | string[] | Any topics (e.g., `["sports", "food", "work"]`) | `[]` |
| `learning_goals` | string[] | Any goals (e.g., `["grammar", "pronunciation"]`) | `[]` |
| `tutor_style` | string | `formal`, `casual`, `encouraging`, `patient`, `challenging` | `professional and encouraging` |
| `correction_style` | string | `immediate`, `end-of-turn`, `summary` | `end-of-turn` |

**Note**: All fields are optional. The agent uses sensible defaults if any field is missing.

## Correction Styles Explained

- **`immediate`**: Tutor corrects mistakes as they happen during conversation
- **`end-of-turn`**: Tutor waits until user finishes speaking, then provides gentle corrections
- **`summary`**: Tutor summarizes mistakes at natural break points in the conversation

## Example UI Form Data Mapping

```javascript
// Example: Mapping form data to tutor context
const formData = {
  userLevel: "intermediate",           // from <select>
  interests: ["tech", "movies"],       // from multi-select checkboxes
  goals: ["speak fluently"],           // from checkboxes
  personality: "encouraging",          // from radio buttons
  correctionType: "end-of-turn"        // from dropdown
};

const tutorContext = {
  proficiency_level: formData.userLevel,
  topics: formData.interests,
  learning_goals: formData.goals,
  tutor_style: formData.personality,
  correction_style: formData.correctionType
};

const metadata = JSON.stringify({ tutor_context: tutorContext });
```

## Testing

You can test with minimal context:

```javascript
// Minimal example - uses all defaults
const metadata = JSON.stringify({
  tutor_context: {
    proficiency_level: "beginner"
  }
});
```

## Troubleshooting

- **Context not working?** Check browser console for JSON parsing errors
- **Using defaults?** Verify metadata is passed during room connection
- **Agent logs**: Check agent logs for "Loaded tutor context" message to confirm receipt

## Backend Reference

The Python agent extracts context from `ctx.room.metadata`:

```python
# In main.py (simplified)
metadata = json.loads(ctx.room.metadata)
tutor_context = metadata.get("tutor_context")
agent = Assistant(context=tutor_context)
```
