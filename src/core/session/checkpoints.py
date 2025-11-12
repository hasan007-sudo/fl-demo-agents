"""Session checkpoint configuration and management."""

from dataclasses import dataclass
from typing import Optional, List, Dict, Any


@dataclass
class Checkpoint:
    """Represents a time checkpoint in a session."""
    time: int
    frontend_event: bool
    ai_instruction: Optional[str]
    is_final: bool


@dataclass
class SessionTimingConfig:
    """Configuration for session timing and checkpoints."""
    max_duration: int
    checkpoints: List[Checkpoint]

    def get_checkpoint_at_index(self, idx: int) -> Optional[Checkpoint]:
        """Get checkpoint at specific index."""
        if 0 <= idx < len(self.checkpoints):
            return self.checkpoints[idx]
        return None

    def get_final_checkpoint(self) -> Optional[Checkpoint]:
        """Get the final checkpoint that triggers shutdown."""
        for cp in self.checkpoints:
            if cp.is_final:
                return cp
        return None


def create_checkpoint_metadata(
    checkpoint: Checkpoint,
    idx: int,
    max_duration: int
) -> Dict[str, Any]:
    """Create metadata dict for checkpoint event."""
    remaining = max_duration - checkpoint.time
    return {
        "elapsed_seconds": checkpoint.time,
        "remaining_seconds": remaining,
        "checkpoint_index": idx,
        "total_duration": max_duration,
        "is_final": checkpoint.is_final
    }
