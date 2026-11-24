import re
from dataclasses import dataclass
from .callback_data import CallbackData  # noqa: F401


class BaseFilter:
    async def __call__(self, *a, **k): raise NotImplementedError


@dataclass
class CommandObject:
    prefix: str = "/"
    command: str = ""
    mention: str | None = None
    args: str | None = None


class Command:
    def __init__(self, *commands, prefix="/", ignore_case=False):
        self.commands = commands
    def __call__(self, message):
        text = getattr(message, "text", None)
        if not text or not text.startswith("/"): return False
        m = re.match(r"^/(\w+)(?:@(\w+))?(?:\s+(.*))?$", text, re.S)
        if not m or m.group(1) not in self.commands: return False
        return {"command": CommandObject("/", m.group(1), m.group(2), (m.group(3) or None))}


def CommandStart(): return Command("start")


class StateFilter:
    def __init__(self, *states): self.states = states
