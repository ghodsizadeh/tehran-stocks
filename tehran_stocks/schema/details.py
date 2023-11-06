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
    full_name_en: Optional[str] = Field(default=None, alias="lVal18")
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


class TradeClientType(BaseModel):
    buy_volume_individual: Optional[float] = Field(default=None, alias="buy_I_Volume")
    buy_volume_legal: Optional[float] = Field(default=None, alias="buy_N_Volume")
    buy_volume_legal_foreign: Optional[float] = Field(
        default=None, alias="buy_DDD_Volume"
    )
    buy_count_individual: Optional[int] = Field(default=None, alias="buy_CountI")
    buy_count_legal: Optional[int] = Field(default=None, alias="buy_CountN")
    buy_count_legal_foreign: Optional[int] = Field(default=None, alias="buy_CountDDD")
    sell_volume_individual: Optional[float] = Field(default=None, alias="sell_I_Volume")
    sell_volume_legal: Optional[float] = Field(default=None, alias="sell_N_Volume")
    sell_count_individual: Optional[int] = Field(default=None, alias="sell_CountI")
    sell_count_legal: Optional[int] = Field(default=None, alias="sell_CountN")


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


class ClosingPriceData(BaseModel):
    instrument_state: InstrumentState = Field(default=None, alias="instrumentState")
    instrument: Optional[InstrumentInfo]
    last_h_even: Optional[int] = Field(default=None, alias="lastHEven")
    final_last_date: Optional[int] = Field(default=None, alias="finalLastDate")
    nvt: Optional[float]
    mop: Optional[int]
    thirty_day_closing_history: Optional[str] = Field(
        default=None, alias="thirtyDayClosingHistory"
    )
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


class BestLimit(BaseModel):
    number: Optional[int]
    volume_buy: Optional[int] = Field(default=None, alias="qTitMeDem")
    count_buy: Optional[int] = Field(default=None, alias="zOrdMeDem")
    price_buy: Optional[float] = Field(default=None, alias="pMeDem")
    price_sell: Optional[float] = Field(default=None, alias="pMeOf")
    count_sell: Optional[int] = Field(default=None, alias="zOrdMeOf")
    volume_sell: Optional[int] = Field(default=None, alias="qTitMeOf")
    ins_code: Optional[str] = Field(default=None, alias="insCode")


class BestLimitHistory(BaseModel):
    idn: Optional[int]
    d_even: Optional[int] = Field(default=None, alias="dEven")
    h_even: Optional[int] = Field(default=None, alias="hEven")
    ref_id: Optional[int] = Field(default=None, alias="refID")
    number: Optional[int]
    volume_buy: Optional[int] = Field(default=None, alias="qTitMeDem")
    count_buy: Optional[int] = Field(default=None, alias="zOrdMeDem")
    price_buy: Optional[float] = Field(default=None, alias="pMeDem")
    price_sell: Optional[float] = Field(default=None, alias="pMeOf")
    count_sell: Optional[int] = Field(default=None, alias="zOrdMeOf")
    volume_sell: Optional[int] = Field(default=None, alias="qTitMeOf")
    ins_code: Optional[str] = Field(default=None, alias="insCode")
