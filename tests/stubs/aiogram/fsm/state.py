class State:
    def __init__(self, state=None): self.state = state; self.group = None
    def __set_name__(self, owner, name): self._name = name
    def __repr__(self): return f"<State {self.state}>"

class StatesGroup:
    def __init_subclass__(cls, **kw):
        super().__init_subclass__(**kw)
        for name, val in list(vars(cls).items()):
            if isinstance(val, State): val.state = f"{cls.__name__}:{name}"; val.group = cls
