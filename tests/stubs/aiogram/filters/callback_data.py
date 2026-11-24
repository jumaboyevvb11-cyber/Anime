from pydantic import BaseModel


class CallbackData(BaseModel):
    __prefix__ = ""
    __sep__ = ":"

    def __init_subclass__(cls, *, prefix, sep=":", **kw):
        super().__init_subclass__(**kw)
        cls.__prefix__, cls.__sep__ = prefix, sep

    def pack(self) -> str:
        parts = [self.__prefix__]
        for name in type(self).model_fields:
            v = getattr(self, name)
            v = "" if v is None else str(v)
            if self.__sep__ in v: raise ValueError(f"separator in value: {v!r}")
            parts.append(v)
        data = self.__sep__.join(parts)
        if len(data.encode()) > 64: raise ValueError(f"callback_data too long: {data!r}")
        return data

    @classmethod
    def unpack(cls, value):
        prefix, *parts = value.split(cls.__sep__)
        names = list(cls.model_fields)
        if prefix != cls.__prefix__: raise ValueError("bad prefix")
        if len(parts) != len(names): raise TypeError("bad parts count")
        return cls(**dict(zip(names, parts)))

    @classmethod
    def filter(cls, rule=None):
        return _CBFilter(cls, rule)


class _CBFilter:
    def __init__(self, cls, rule): self.cls, self.rule = cls, rule
    def __call__(self, query):
        if not query.data: return False
        try: cd = self.cls.unpack(query.data)
        except (TypeError, ValueError): return False
        if self.rule is not None and not self.rule(cd): return False
        return {"callback_data": cd}
