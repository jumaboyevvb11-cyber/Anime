from .state import State

class FSMContext:
    def __init__(self, storage, key): self.storage, self.key = storage, key
    async def set_state(self, state=None):
        v = state.state if isinstance(state, State) else state
        if v is None: self.storage.states.pop(self.key, None)
        else: self.storage.states[self.key] = v
    async def get_state(self): return self.storage.states.get(self.key)
    async def set_data(self, data): self.storage.data[self.key] = dict(data)
    async def get_data(self): return dict(self.storage.data.get(self.key, {}))
    async def update_data(self, data=None, **kw):
        d = await self.get_data(); d.update(data or {}); d.update(kw); self.storage.data[self.key] = d; return dict(d)
    async def clear(self): self.storage.states.pop(self.key, None); self.storage.data.pop(self.key, None)
