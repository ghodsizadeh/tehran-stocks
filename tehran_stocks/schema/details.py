from typing import Optional

from pydantic import BaseModel, Field


class Eps(BaseModel):
    eps_value: Optional[float] = Field(alias="epsValue")
    estimated_eps: Optional[float] = Field(alias="estimatedEPS")
    sector_pe: Optional[float] = Field(alias="sectorPE")
    psr: Optional[float] = Field(alias="psr")


class Sector(BaseModel):
    d_even: Optional[int] = Field(alias="dEven")
    sector_code: Optional[str] = Field(alias="cSecVal")
    sector_name: Optional[str] = Field(alias="lSecVal")


class StaticThreshold(BaseModel):
    ins_code: Optional[str] = Field(alias="insCode")
    d_even: Optional[int] = Field(alias="dEven")
    h_even: Optional[int] = Field(alias="hEven")
    max_price: Optional[float] = Field(alias="psGelStaMax")
    min_price: Optional[float] = Field(alias="psGelStaMin")


class InstrumentInfo(BaseModel):
    base_vol: Optional[int] = Field(alias="baseVol")
    cIsin: Optional[str]
    cgrValCot: Optional[str] = Field(alias="cgrValCot")
    contract_size: Optional[int] = Field(alias="contractSize")
    min_week: Optional[float] = Field(alias="minWeek")
    max_week: Optional[float] = Field(alias="maxWeek")
    min_year: Optional[float] = Field(alias="minYear")
    max_year: Optional[float] = Field(alias="maxYear")
    average_monthly_volume: Optional[float] = Field(alias="qTotTran5JAvg")
    d_even: Optional[int] = Field(alias="dEven")
    top_inst: Optional[int] = Field(alias="topInst")
    fara_desc: Optional[str] = Field(alias="faraDesc")
    contract_size: Optional[int] = Field(alias="contractSize")
    nav: Optional[float]
    under_supervision: Optional[int] = Field(alias="underSupervision")
    c_val_mne: Optional[str] = Field(alias="cValMne")
    ins_code: Optional[str] = Field(alias="insCode")
    full_name: Optional[str] = Field(alias="lVal30")
    name: Optional[str] = Field(alias="lVal18AFC")
    eps: Optional[Eps]
    sector: Optional[Sector]


class InstrumentState(BaseModel):
    idn: Optional[int]
    d_even: Optional[int] = Field(alias="dEven")
    h_even: Optional[int] = Field(alias="hEven")
    ins_code: Optional[str] = Field(alias="insCode")
    full_name: Optional[str] = Field(alias="lVal30")
    name: Optional[str] = Field(alias="lVal18AFC")
    c_etaval: Optional[str] = Field(alias="cEtaval")
    real_heven: Optional[int] = Field(alias="realHeven")
    under_supervision: Optional[int] = Field(alias="underSupervision")
    c_etaval_title: Optional[str] = Field(alias="cEtavalTitle")


# {
#     "clientType": {
#         "buy_I_Volume": 117325549.0, # حقیقی
#         "buy_N_Volume": 2400000.0, # حقوقی
#         "buy_DDD_Volume": 0.0,
#         "buy_CountI": 1367, # تعداد حقیقی
#         "buy_CountN": 1,  # تعداد حقوقی
#         "buy_CountDDD": 0,
#         "sell_I_Volume": 99671572.0,
#         "sell_N_Volume": 20053977.0,
#         "sell_CountI": 1713,
#         "sell_CountN": 12
#     }
# }
class TradeClientType(BaseModel):
    buy_volume_individual: Optional[float] = Field(alias="buy_I_Volume")
    buy_volume_legal: Optional[float] = Field(alias="buy_N_Volume")
    buy_volume_legal_foreign: Optional[float] = Field(alias="buy_DDD_Volume")
    buy_count_individual: Optional[int] = Field(alias="buy_CountI")
    buy_count_legal: Optional[int] = Field(alias="buy_CountN")
    buy_count_legal_foreign: Optional[int] = Field(alias="buy_CountDDD")
    sell_volume_individual: Optional[float] = Field(alias="sell_I_Volume")
    sell_volume_legal: Optional[float] = Field(alias="sell_N_Volume")
    sell_count_individual: Optional[int] = Field(alias="sell_CountI")
    sell_count_legal: Optional[int] = Field(alias="sell_CountN")
