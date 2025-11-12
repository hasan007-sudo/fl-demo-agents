"""Agent behavior mixins for composable functionality."""

from .timing import TimingMixin
from .shutdown import ShutdownMixin

__all__ = ["TimingMixin", "ShutdownMixin"]
