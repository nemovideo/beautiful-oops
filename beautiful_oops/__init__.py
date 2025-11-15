from .decorators import oops_moment_auto as oops_moment
from .core.adventure import Adventure, BaseOopsPlugin, AdventureEvent, Event, MomentEvent, OopsError, MomentCtx
from .core.elf import SimpleBackoffElf, BackoffPolicy, Elf
from .core.hero import Advice, Hero, HeroFactory
from .plugins.storybook_plugin import StorybookPlugin
from .plugins.models.storybook import StoryBook
from .core.oops import OopsSolution, OopsCategory
from .plugins.storybook_console_sink_plugin import StorybookConsoleSinkPlugin
from .plugins.tracing_stack_plugin import TracingStackPlugin

__all__ = [
    "oops_moment",
    "Adventure",
    "BaseOopsPlugin",
    "Event",
    "AdventureEvent",
    "MomentEvent",
    "SimpleBackoffElf",
    "BackoffPolicy",
    "Elf",
    "Advice",
    "Hero",
    "HeroFactory",
    "StorybookPlugin",
    "StorybookConsoleSinkPlugin",
    "StoryBook",
    "OopsSolution",
    "OopsCategory",
    "TracingStackPlugin",
    "OopsError",
    "MomentCtx",


]

try:
    from importlib import metadata as importlib_metadata
    __version__ = importlib_metadata.version("beautiful-oops")
except importlib_metadata.PackageNotFoundError:
    __version__ = "0.0.0-dev"
