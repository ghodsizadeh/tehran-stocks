from pydantic import BaseModel, Field
from typing import Optional

from tehran_stocks.schema.details import InstrumentInfo, InstrumentState


class TradeTopItem(BaseModel):
    instrumentState: Optional[InstrumentState] = Field(
        default=None, alias="instrumentState"
    )
    instrument: Optional[InstrumentInfo] = Field(default=None, alias="instrument")
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


class SelectedIndexItem:
    ins_code: str = Field(default=None, alias="insCode")
    d_even: Optional[int] = Field(default=None, alias="dEven")
    h_even: Optional[int] = Field(default=None, alias="hEven")
    x_dr_niv_j_idx_004: Optional[float] = Field(default=None, alias="xDrNivJIdx004")
    x_ph_niv_j_idx_004: Optional[float] = Field(default=None, alias="xPhNivJIdx004")
    x_pb_niv_j_idx_004: Optional[float] = Field(default=None, alias="xPbNivJIdx004")
    x_var_idx_j_rf_v: Optional[float] = Field(default=None, alias="xVarIdxJRfV")
    last: Optional[bool]
    index_change: Optional[float] = Field(default=None, alias="indexChange")
    l_val_30: Optional[str] = Field(default=None, alias="lVal30")
    c1: Optional[int]
    c2: Optional[int]
    c3: Optional[int]
    c4: Optional[int]


class InstrumentEffectItem(BaseModel):
    ins_code: str = Field(default=None, alias="insCode")
    instrument: Optional[InstrumentInfo] = Field(default=None, alias="instrument")
    p_closing: Optional[float] = Field(default=None, alias="pClosing")
    inst_effect_value: Optional[float] = Field(default=None, alias="instEffectValue")


class MarketOverview(BaseModel):
    last_data_d_even: Optional[int] = Field(default=None, alias="lastDataDEven")
    last_data_h_even: Optional[int] = Field(default=None, alias="lastDataHEven")
    index_last_value: Optional[float] = Field(default=None, alias="indexLastValue")
    index_change: Optional[float] = Field(default=None, alias="indexChange")
    index_equal_weighted_last_value: Optional[float] = Field(
        default=None, alias="indexEqualWeightedLastValue"
    )
    index_equal_weighted_change: Optional[float] = Field(
        default=None, alias="indexEqualWeightedChange"
    )
    market_activity_d_even: Optional[int] = Field(
        default=None, alias="marketActivityDEven"
    )
    market_activity_h_even: Optional[int] = Field(
        default=None, alias="marketActivityHEven"
    )
    market_activity_z_tot_tran: Optional[int] = Field(
        default=None, alias="marketActivityZTotTran"
    )
    market_activity_q_tot_cap: Optional[float] = Field(
        default=None, alias="marketActivityQTotCap"
    )
    market_activity_q_tot_tran: Optional[float] = Field(
        default=None, alias="marketActivityQTotTran"
    )
    market_state: Optional[str] = Field(default=None, alias="marketState")
    market_value: Optional[float] = Field(default=None, alias="marketValue")
    market_value_base: Optional[float] = Field(default=None, alias="marketValueBase")
    market_state_title: Optional[str] = Field(default=None, alias="marketStateTitle")
