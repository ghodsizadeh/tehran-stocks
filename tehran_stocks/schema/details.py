from typing import Optional

from pydantic import BaseModel, Field


class Eps(BaseModel):
    eps_value: Optional[float] = Field(default=None, alias="epsValue")
    estimated_eps: Optional[float] = Field(default=None, alias="estimatedEPS")
    sector_pe: Optional[float] = Field(default=None, alias="sectorPE")
    psr: Optional[float] = Field(default=None, alias="psr")


class Sector(BaseModel):
    d_even: Optional[int] = Field(default=None, alias="dEven")
    sector_code: Optional[str] = Field(default=None, alias="cSecVal")
    sector_name: Optional[str] = Field(default=None, alias="lSecVal")


class StaticThreshold(BaseModel):
    ins_code: Optional[str] = Field(default=None, alias="insCode")
    d_even: Optional[int] = Field(default=None, alias="dEven")
    h_even: Optional[int] = Field(default=None, alias="hEven")
    max_price: Optional[float] = Field(default=None, alias="psGelStaMax")
    min_price: Optional[float] = Field(default=None, alias="psGelStaMin")


class InstrumentInfo(BaseModel):
    base_vol: Optional[int] = Field(default=None, alias="baseVol")
    cIsin: Optional[str]
    cgrValCot: Optional[str] = Field(default=None, alias="cgrValCot")
    contract_size: Optional[int] = Field(default=None, alias="contractSize")
    min_week: Optional[float] = Field(default=None, alias="minWeek")
    max_week: Optional[float] = Field(default=None, alias="maxWeek")
    min_year: Optional[float] = Field(default=None, alias="minYear")
    max_year: Optional[float] = Field(default=None, alias="maxYear")
    average_monthly_volume: Optional[float] = Field(default=None, alias="qTotTran5JAvg")
    d_even: Optional[int] = Field(default=None, alias="dEven")
    top_inst: Optional[int] = Field(default=None, alias="topInst")
    fara_desc: Optional[str] = Field(default=None, alias="faraDesc")
    contract_size: Optional[int] = Field(default=None, alias="contractSize")
    nav: Optional[float]
    under_supervision: Optional[int] = Field(default=None, alias="underSupervision")
    c_val_mne: Optional[str] = Field(default=None, alias="cValMne")
    ins_code: Optional[str] = Field(default=None, alias="insCode")
    full_name: Optional[str] = Field(default=None, alias="lVal30")
    name: Optional[str] = Field(default=None, alias="lVal18AFC")
    eps: Optional[Eps]
    sector: Optional[Sector]


class InstrumentState(BaseModel):
    idn: Optional[int]
    d_even: Optional[int] = Field(default=None, alias="dEven")
    h_even: Optional[int] = Field(default=None, alias="hEven")
    ins_code: Optional[str] = Field(default=None, alias="insCode")
    full_name: Optional[str] = Field(default=None, alias="lVal30")
    name: Optional[str] = Field(default=None, alias="lVal18AFC")
    c_etaval: Optional[str] = Field(default=None, alias="cEtaval")
    real_heven: Optional[int] = Field(default=None, alias="realHeven")
    under_supervision: Optional[int] = Field(default=None, alias="underSupervision")
    c_etaval_title: Optional[str] = Field(default=None, alias="cEtavalTitle")


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
    buy_volume_individual: Optional[float] = Field(default=None, alias="buy_I_Volume")
    buy_volume_legal: Optional[float] = Field(default=None, alias="buy_N_Volume")
    buy_volume_legal_foreign: Optional[float] = Field(default=None, alias="buy_DDD_Volume")
    buy_count_individual: Optional[int] = Field(default=None, alias="buy_CountI")
    buy_count_legal: Optional[int] = Field(default=None, alias="buy_CountN")
    buy_count_legal_foreign: Optional[int] = Field(default=None, alias="buy_CountDDD")
    sell_volume_individual: Optional[float] = Field(default=None, alias="sell_I_Volume")
    sell_volume_legal: Optional[float] = Field(default=None, alias="sell_N_Volume")
    sell_count_individual: Optional[int] = Field(default=None, alias="sell_CountI")
    sell_count_legal: Optional[int] = Field(default=None, alias="sell_CountN")
# {"insCode":null,"dEven":0,"nTran":1,"hEven":90016,"qTitTran":71391,"pTran":4350.00,"qTitNgJ":0,"iSensVarP":"\u0000","pPhSeaCotJ":0.0,"pPbSeaCotJ":0.0,"iAnuTran":0,"xqVarPJDrPRf":0.0,"canceled":0},

class Trade(BaseModel):
    ins_code: Optional[str] = Field(default=None, alias="insCode")
    d_even: Optional[int] = Field(default=None, alias="dEven")
    n_tran: Optional[int] = Field(default=None, alias="nTran")
    h_even: Optional[int] = Field(default=None, alias="hEven")
    volume: Optional[int] = Field(default=None, alias="qTitTran")
    price: Optional[float] = Field(default=None, alias="pTran")
    volume_ng: Optional[int] = Field(default=None, alias="qTitNgJ")
    i_sens_varp: Optional[str] = Field(default=None, alias="iSensVarP")
    p_ph_sea_cotj: Optional[float] = Field(default=None, alias="pPhSeaCotJ")
    p_pb_sea_cotj: Optional[float] = Field(default=None, alias="pPbSeaCotJ")
    i_anu_tran: Optional[int] = Field(default=None, alias="iAnuTran")
    xq_var_pjdr_prf: Optional[float] = Field(default=None, alias="xqVarPJDrPRf")
    canceled: Optional[int]


# {"closingPriceInfo":{"instrumentState":{"idn":0,"dEven":0,"hEven":0,"insCode":null,"cEtaval":"A ","realHeven":0,"underSupervision":0,"cEtavalTitle":"مجاز"},"instrument":null,"lastHEven":103950,"finalLastDate":20231022,"nvt":0.0,"mop":0,"thirtyDayClosingHistory":null,"priceChange":0.0,"priceMin":4296.00,"priceMax":4429.00,"priceYesterday":4371.00,"priceFirst":4350.00,"last":false,"id":0,"insCode":"0","dEven":20231022,"hEven":103950,"pClosing":4378.00,"iClose":false,"yClose":false,"pDrCotVal":4360.00,"zTotTran":2509.0,"qTotTran5J":55169799.0,"qTotCap":241525532962.00}}

class ClosingPriceData(BaseModel):
    instrument_state: InstrumentState = Field(default=None, alias="instrumentState")
    instrument: Optional[InstrumentInfo]
    last_h_even: Optional[int] = Field(default=None, alias="lastHEven")
    final_last_date: Optional[int] = Field(default=None, alias="finalLastDate")
    nvt: Optional[float]
    mop: Optional[int]
    thirty_day_closing_history: Optional[str] = Field(default=None, alias="thirtyDayClosingHistory")
    price_change: Optional[float] = Field(default=None, alias="priceChange")
    price_min: Optional[float] = Field(default=None, alias="priceMin")
    price_max: Optional[float] = Field(default=None, alias="priceMax")
    price_yesterday: Optional[float] = Field(default=None, alias="priceYesterday")
    price_first: Optional[float] = Field(default=None, alias="priceFirst")
    last: Optional[bool]
    id: Optional[int]
    ins_code: Optional[str] = Field(default=None, alias="insCode")
    d_even: Optional[int] = Field(default=None, alias="dEven")
    h_even: Optional[int] = Field(default=None, alias="hEven")
    p_closing: Optional[float] = Field(default=None, alias="pClosing")
    i_close: Optional[bool] = Field(default=None, alias="iClose")
    y_close: Optional[bool] = Field(default=None, alias="yClose")
    p_dr_cot_val: Optional[float] = Field(default=None, alias="pDrCotVal")
    z_tot_tran: Optional[float] = Field(default=None, alias="zTotTran")
    q_tot_tran_5j: Optional[float] = Field(default=None, alias="qTotTran5J")
    q_tot_cap: Optional[float] = Field(default=None, alias="qTotCap")
