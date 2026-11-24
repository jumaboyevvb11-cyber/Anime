from .base import BaseStorage
class MemoryStorage(BaseStorage):
    def __init__(self): self.states, self.data = {}, {}
