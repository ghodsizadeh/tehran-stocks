from pydantic import BaseModel, Field
from typing import Optional
# {'insCode': 32097828799138957, 'dEven': 20081204, 'xNivInuClMresIbs': 9248.9, 'xNivInuPbMresIbs': 9233.2, 'xNivInuPhMresIbs': 9248.9}


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
