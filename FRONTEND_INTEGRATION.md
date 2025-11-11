# Frontend Integration Guide

## Required Changes for Frontend

### 1. English Tutor (Minimal Change)

Add ONE field to existing payload:

```typescript
// Existing EnglishTutorContext interface - NO CHANGES except adding agentType
export interface EnglishTutorContext {
  agentType: "english_tutor",  // <-- ADD THIS FIELD
  student_name: string;
  proficiency_level: ProficiencyLevel;
  gender_preference: GenderPreference;  // "male" | "female" | "no_preference"
  speaking_speed: SpeakingSpeed;
  interests: Interest[];
  comfortable_language: IndianLanguage;
  tutor_styles: NewTutorStyle[];
  correction_preference: CorrectionPreference;
  email?: string;
  whatsapp?: string;
}
```

**Voice Selection**: Uses `gender_preference` field
- "male" → voice: "echo"
- "female" → voice: "nova"
- "no_preference" → voice: "alloy"

### 2. Interview Preparer (New Agent)

```typescript
export interface InterviewContext {
  agentType: "interview_preparer",

  // Required fields
  candidate_name: string;
  interview_type: "technical" | "behavioral" | "hr" | "case_study";
  job_role: string;  // e.g., "software_engineer", "product_manager", "data_scientist"
  experience_level: "entry" | "mid" | "senior" | "executive";
  focus_areas: string[];  // Topics to focus on during the interview

  // Optional fields
  target_industry?: string;  // e.g., "tech", "finance", "healthcare", "retail"
  company_size?: string;  // e.g., "startup", "small", "medium", "large", "enterprise"
  interview_format?: string;  // e.g., "phone", "video", "in_person", "panel"
  preparation_level?: string;  // e.g., "beginner", "intermediate", "advanced"
  weak_points?: string[];  // Areas candidate struggles with
  practice_goals?: string[];  // What candidate wants to achieve in practice
}
```

**Note**: The `gender_preference` field has been removed. Voice selection for Interview Preparer will use a default voice.

## Example Requests

### English Tutor Request
```json
{
  "agentType": "english_tutor",
  "student_name": "John",
  "proficiency_level": "B1",
  "gender_preference": "male",
  "speaking_speed": "slow",
  "interests": ["travel", "technology"],
  "comfortable_language": "hindi",
  "tutor_styles": ["encouraging"],
  "correction_preference": "let_me_finish",
  "email": "john@example.com"
}
```

### Interview Preparer Request
```json
{
  "agentType": "interview_preparer",
  "candidate_name": "Jane Smith",
  "interview_type": "technical",
  "job_role": "software_engineer",
  "experience_level": "senior",
  "focus_areas": ["system design", "algorithms", "leadership"],
  "target_industry": "tech",
  "company_size": "enterprise",
  "interview_format": "video",
  "preparation_level": "intermediate",
  "weak_points": ["behavioral questions", "salary negotiation"],
  "practice_goals": ["improve confidence", "practice STAR method"]
}
```

## Voice Selection Logic

**English Tutor** uses `gender_preference`:

```typescript
// Voice mapping for English Tutor
const voiceMap = {
  "male": "echo",
  "female": "nova",
  "no_preference": "alloy"
};

const selectedVoice = voiceMap[context.gender_preference] || "alloy";
```

**Interview Preparer** uses default voice "alloy" (no gender_preference field).

## Backward Compatibility

If frontend sends old format (without agentType), system defaults to English Tutor:

```json
{
  "tutor_context": {
    "studentName": "John",
    "proficiencyLevel": "B1",
    // ... other fields (camelCase)
  }
}
```

This will automatically be converted to:
- agentType: "english_tutor"
- All fields converted to snake_case

## Summary

- **English Tutor**: Add `"agentType": "english_tutor"` - everything else stays the same
- **Interview Preparer**: New agent with `"agentType": "interview_preparer"` and updated field schema
  - **Required fields**: candidate_name, interview_type, job_role, experience_level, focus_areas
  - **Optional fields**: target_industry, company_size, interview_format, preparation_level, weak_points, practice_goals
- **Voice Selection**:
  - English Tutor uses `gender_preference` field (male/female/no_preference)
  - Interview Preparer uses default voice "alloy"
- **Backward Compatible**: Old format still works, defaults to English Tutor

---

## Session Events and Timeout Handling

### Overview

Both agents enforce a **5-minute hard timeout** on all sessions with **time checkpoint notifications**:
1. The agent sends `time_checkpoint` events to the frontend at 3min and 4.5min
2. The agent is silently informed about elapsed time (doesn't mention it to users)
3. At 5 minutes, the agent sends a `session_status` event and delivers a natural goodbye
4. The session automatically disconnects

This ensures predictable session duration, provides frontend with progress tracking, and prevents runaway sessions.

### Timeline & Checkpoints

**English Tutor & Interview Preparer:**
- **3 minutes (180s)**: Checkpoint 1 - Frontend notified, AI silently informed, conversation continues naturally
- **4.5 minutes (270s)**: Checkpoint 2 - Frontend notified, AI starts wrapping up naturally (no time mention to user)
- **5 minutes (300s)**: **FINAL CHECKPOINT** - Session ending event sent, natural goodbye with feedback, disconnect

**Key Point**: The AI is aware of time checkpoints but **never mentions the time** to users. Goodbyes are natural without saying "time is up".

### Event Formats

#### 1. Time Checkpoint Event

Sent at 3min and 4.5min to inform frontend of progress:

```typescript
interface TimeCheckpointEvent {
  type: "time_checkpoint";
  status: "in_progress";  // "in_progress" for regular checkpoints
  reason: "checkpoint";
  timestamp: string;  // ISO 8601 format (e.g., "2025-11-11T10:30:00.000Z")
  metadata: {
    elapsed_seconds: 180;  // 180 for 3min, 270 for 4.5min
    remaining_seconds: 120;  // Time remaining until session end
    checkpoint_index: 0;  // 0-indexed (0 = first checkpoint, 1 = second, 2 = final)
    total_duration: 300;
    is_final: false;  // false for regular checkpoints, true at 5min
  };
}
```

#### 2. Final Checkpoint Event (5 minutes)

Sent at exactly 5 minutes when session is ending:

```typescript
interface FinalCheckpointEvent {
  type: "time_checkpoint";
  status: "ending";  // "ending" for final checkpoint
  reason: "checkpoint";
  timestamp: string;
  metadata: {
    elapsed_seconds: 300;
    remaining_seconds: 0;
    checkpoint_index: 2;
    total_duration: 300;
    is_final: true;  // Always true for final checkpoint
  };
}
```

#### 3. Session Status Event (Legacy - Still Sent)

Also sent at 5 minutes for backward compatibility:

```typescript
interface SessionStatusEvent {
  type: "session_status";
  status: "ending";
  reason: "timeout";
  timestamp: string;
  metadata: {
    duration_seconds: 300;
  };
}
```

### Frontend Implementation

#### 1. Listen for Data Channel Messages

Use LiveKit's `RoomEvent.DataReceived` to listen for session events:

```typescript
import { Room, RoomEvent, DataPacket_Kind } from 'livekit-client';

const room = new Room();

// Listen for data messages
room.on(RoomEvent.DataReceived, (
  payload: Uint8Array,
  participant?: RemoteParticipant,
  kind?: DataPacket_Kind
) => {
  try {
    // Decode the message
    const decoder = new TextDecoder();
    const message = decoder.decode(payload);
    const data = JSON.parse(message);

    // Handle time checkpoint events (NEW)
    if (data.type === 'time_checkpoint') {
      handleTimeCheckpoint(data);
    }

    // Handle session status events
    if (data.type === 'session_status') {
      handleSessionStatusEvent(data);
    }

    // Handle transcript events (existing functionality)
    if (data.type === 'transcript') {
      handleTranscriptEvent(data);
    }
  } catch (error) {
    console.error('Failed to parse data message:', error);
  }
});
```

#### 2. Handle Time Checkpoint Events

```typescript
function handleTimeCheckpoint(event: TimeCheckpointEvent) {
  const { elapsed_seconds, remaining_seconds, is_final, checkpoint_index } = event.metadata;

  console.log(`Checkpoint ${checkpoint_index + 1}: ${elapsed_seconds}s elapsed, ${remaining_seconds}s remaining`);

  if (is_final) {
    // Final checkpoint - session is ending
    console.log('Session is ending - agent will say goodbye');
    showSessionEndingBanner();
    disableUserMicrophone(); // Optional
  } else {
    // Regular checkpoint - update progress UI
    updateProgressBar(elapsed_seconds, event.metadata.total_duration);

    // Optionally show a subtle notification
    if (checkpoint_index === 0) {
      // 3-minute mark
      showNotification('3 minutes elapsed', 'info');
    } else if (checkpoint_index === 1) {
      // 4.5-minute mark - warn user session will end soon
      showNotification('Session wrapping up soon', 'warning');
    }
  }
}
```

#### 3. Handle Session Ending Event (Legacy)

```typescript
function handleSessionStatusEvent(event: SessionStatusEvent) {
  if (event.status === 'ending' && event.reason === 'timeout') {
    console.log('Session is ending due to timeout');

    // Update UI to show session is ending
    showSessionEndingNotification();

    // Optionally disable user microphone
    disableUserMicrophone();

    // Show a banner or modal
    displayMessage('Session ending - Thank you for your time!');

    // Prepare for disconnection
    // The room will disconnect automatically after the agent finishes speaking
  }
}
```

#### 4. Example React Hook with Checkpoint Tracking

```typescript
import { useEffect, useState } from 'react';
import { Room, RoomEvent } from 'livekit-client';

interface SessionProgress {
  elapsedSeconds: number;
  remainingSeconds: number;
  percentComplete: number;
  currentCheckpoint: number;
  isEnding: boolean;
}

export function useSessionProgress(room: Room | null) {
  const [progress, setProgress] = useState<SessionProgress>({
    elapsedSeconds: 0,
    remainingSeconds: 300,
    percentComplete: 0,
    currentCheckpoint: -1,
    isEnding: false
  });

  useEffect(() => {
    if (!room) return;

    const handleDataReceived = (payload: Uint8Array) => {
      try {
        const decoder = new TextDecoder();
        const message = decoder.decode(payload);
        const data = JSON.parse(message);

        // Handle time checkpoint events
        if (data.type === 'time_checkpoint') {
          const { elapsed_seconds, remaining_seconds, checkpoint_index, total_duration, is_final } = data.metadata;

          setProgress({
            elapsedSeconds: elapsed_seconds,
            remainingSeconds: remaining_seconds,
            percentComplete: (elapsed_seconds / total_duration) * 100,
            currentCheckpoint: checkpoint_index,
            isEnding: is_final
          });
        }

        // Handle legacy session_status events
        if (data.type === 'session_status' && data.status === 'ending') {
          setProgress(prev => ({ ...prev, isEnding: true }));
        }
      } catch (error) {
        console.error('Failed to parse session event:', error);
      }
    };

    room.on(RoomEvent.DataReceived, handleDataReceived);

    return () => {
      room.off(RoomEvent.DataReceived, handleDataReceived);
    };
  }, [room]);

  return progress;
}
```

#### 5. Example Usage in React Component with Progress Bar

```tsx
import React from 'react';
import { useSessionProgress } from './hooks/useSessionProgress';

function SessionView({ room }) {
  const progress = useSessionProgress(room);

  // Format time for display
  const formatTime = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  return (
    <div className="session-container">
      {/* Progress bar */}
      <div className="progress-header">
        <div className="progress-bar-container">
          <div
            className="progress-bar-fill"
            style={{ width: `${progress.percentComplete}%` }}
          />
        </div>
        <div className="time-display">
          <span>{formatTime(progress.elapsedSeconds)}</span>
          <span> / </span>
          <span>{formatTime(300)}</span>
        </div>
      </div>

      {/* Checkpoint notifications */}
      {progress.currentCheckpoint === 1 && !progress.isEnding && (
        <div className="checkpoint-banner warning">
          <span>⏰ Session will end soon</span>
        </div>
      )}

      {/* Session ending banner */}
      {progress.isEnding && (
        <div className="session-ending-banner">
          <span>👋 Session ending - The agent is saying goodbye...</span>
        </div>
      )}

      {/* Your existing session UI */}
      <div className="video-container">
        {/* Video/audio components */}
      </div>

      {/* Final overlay */}
      {progress.isEnding && (
        <div className="overlay">
          <p>Thank you for your session!</p>
          <p>Disconnecting shortly...</p>
        </div>
      )}
    </div>
  );
}
```

### User Experience Recommendations

1. **Progress Bar**: Show a visual progress bar that updates at each checkpoint (3min, 4.5min)
2. **Subtle Checkpoints**: At 3min, optionally show a subtle notification (not intrusive)
3. **Warning at 4.5min**: Show a gentle warning that the session will end soon
4. **Session Ending UI**: At 5min, show a clear "Session ending" banner
5. **Disable Input**: Optionally disable the user's microphone at final checkpoint
6. **Graceful Transition**: Wait 10-15 seconds for the agent's goodbye, then redirect or show completion screen

### Important Notes

- **Time Checkpoints**: Frontend receives progress updates at 3min, 4.5min, and 5min
- **AI is Time-Aware**: The AI knows the elapsed time but **never mentions it to users**
- **Natural Goodbyes**: Agent provides feedback and says goodbye naturally without saying "time is up"
- **No User Interruption at 5 Minutes**: When final checkpoint triggers, user speech is no longer processed
- **Automatic Disconnect**: Session disconnects automatically after ~10 seconds
- **Data Channel is Reliable**: All events are sent with `reliable=true`, ensuring delivery

### Event Types Reference

| Event Type | Status | Reason | When Sent | Purpose |
|------------|--------|--------|-----------|---------|
| `time_checkpoint` | `in_progress` | `checkpoint` | 180s (3min) | Update frontend progress, inform AI silently |
| `time_checkpoint` | `in_progress` | `checkpoint` | 270s (4.5min) | Warn frontend, AI starts wrapping up |
| `time_checkpoint` | `ending` | `checkpoint` | 300s (5min) | Final checkpoint, trigger shutdown |
| `session_status` | `ending` | `timeout` | 300s (5min) | Legacy event, still sent for compatibility |
| `transcript` | N/A | N/A | During conversation | Real-time transcription (existing feature) |

### Testing Checkpoints and Timeout

To test the checkpoint and timeout behavior:

1. Start a session (English Tutor or Interview Preparer)
2. Listen for data channel messages in your frontend
3. Verify you receive checkpoints:
   - At **3:00** (180s): `time_checkpoint` with `checkpoint_index: 0`, `status: "in_progress"`
   - At **4:30** (270s): `time_checkpoint` with `checkpoint_index: 1`, `status: "in_progress"`
   - At **5:00** (300s): `time_checkpoint` with `checkpoint_index: 2`, `status: "ending"`, `is_final: true`
4. Verify the agent says a natural goodbye without mentioning time
5. Verify the session disconnects automatically

**For faster testing**: Modify the `CHECKPOINTS` array in the agent files to use shorter times (e.g., 30s, 60s, 90s)

### Troubleshooting

**Issue**: Not receiving checkpoint events

**Solution**:
- Ensure you're listening to `RoomEvent.DataReceived`
- Check that you're decoding the payload correctly (Uint8Array → string → JSON)
- Look for both `time_checkpoint` and `session_status` event types
- Verify the agent is running the latest version with checkpoint support
- Check browser console for parsing errors

**Issue**: Agent mentions time to users (unexpected)

**Solution**:
- This should NOT happen with the latest version
- The AI instructions explicitly prevent time mentions
- If it occurs, check that you're using the updated agent code with the `CHECKPOINTS` array
- The goodbye messages should be natural without "time is up" phrases

**Issue**: Session not disconnecting

**Solution**:
- The disconnect happens automatically from the agent side
- If the room doesn't disconnect, check network connectivity
- The agent calls `room.disconnect()` after the goodbye message (~10 seconds)
- Ensure you're not preventing disconnection in your frontend code

**Issue**: Progress bar not updating

**Solution**:
- Verify you're handling `time_checkpoint` events (not just `session_status`)
- Check that `metadata.elapsed_seconds` and `metadata.remaining_seconds` are being used
- Ensure your state management is updating correctly on each checkpoint

---