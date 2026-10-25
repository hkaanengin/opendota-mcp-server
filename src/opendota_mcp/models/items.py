from pydantic import BaseModel, Field


class ItemAbility(BaseModel):
    kind: str = Field(description="active, passive, toggle, use or upgrade.")
    name: str
    description: str


class ItemResult(BaseModel):
    id: int
    name: str
    cost: int | None = Field(description="Total gold cost, recipe included; null if not sold.")
    stats: list[str] = Field(description='Bonuses the item gives, e.g. "+ 10 Strength".')
    abilities: list[ItemAbility] = Field(description="What the item does, one entry per effect.")
    cooldown: int | float | None = Field(description="Seconds; null if it has none.")
    mana_cost: int | float | None = Field(description="Null if it costs no mana.")
    components: list[str] = Field(description="Items it's built from; empty for basic items.")
    notes: str | None = Field(description="Mechanics notes, e.g. how it stacks.")
    lore: str | None
