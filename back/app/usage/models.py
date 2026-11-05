from decimal import Decimal
from pydantic import BaseModel, ConfigDict, Field


class PriceInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    provider: str = Field(default="openai", pattern="^[a-z][a-z0-9_-]{0,39}$")
    model: str = Field(min_length=1, max_length=180, pattern="^[A-Za-z0-9_.:/-]+$")
    input_per_million: Decimal = Field(ge=0, le=1000000)
    cached_per_million: Decimal = Field(ge=0, le=1000000)
    output_per_million: Decimal = Field(ge=0, le=1000000)
    source: str = Field(min_length=1, max_length=500)
