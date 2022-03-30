from curry_quest.items import Item


class DummyItem(Item):
    @classmethod
    @property
    def name(cls) -> str: pass

    def cannot_use_reason(self, context) -> str:
        pass

    def use(self, context) -> str:
        pass
