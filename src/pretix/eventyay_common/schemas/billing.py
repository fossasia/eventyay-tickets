from decimal import Decimal

from pydantic import BaseModel, Field


class CollectBillingResponse(BaseModel):
    status: bool = Field(description="Status of collecting billing invoice", default=False)
    voucher_discount: Decimal = Field(default=Decimal('0.00'))
