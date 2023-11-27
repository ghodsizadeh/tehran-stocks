from typing import Optional

from pydantic import BaseModel, Field


class PriceAdjustItem(BaseModel):
    ins_code: Optional[str | int] = Field(default=None, alias="insCode")
    d_even: Optional[int] = Field(default=None, alias="dEven")
    p_closing: Optional[float] = Field(default=None, alias="pClosing")
    p_closing_not_adjusted: Optional[float] = Field(
        default=None, alias="pClosingNotAdjusted"
    )
    corporate_type_code: Optional[int] = Field(default=None, alias="corporateTypeCode")
    instrument: Optional[int] = Field(default=None, alias="instrument")
