from pydantic import BaseModel, Field
from typing import Optional


class IndexHistoryItem(BaseModel):
    ins_code: Optional[int] = Field(default=None, alias="insCode")
    d_even: Optional[int] = Field(default=None, alias="dEven")
    x_niv_inu_cl_mres_ibs: Optional[float] = Field(
        default=None, alias="xNivInuClMresIbs"
    )
    x_niv_inu_pb_mres_ibs: Optional[float] = Field(
        default=None, alias="xNivInuPbMresIbs"
    )
    x_niv_inu_ph_mres_ibs: Optional[float] = Field(
        default=None, alias="xNivInuPhMresIbs"
    )
