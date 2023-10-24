from pydantic import BaseModel, Field
from typing import Optional

from tehran_stocks.schema.details import InstrumentInfo, InstrumentState
# {"tradeTop":[{"instrumentState":null,"instrument":{"cValMne":null,"lVal18":null,"cSocCSAC":null,"lSoc30":null,"yMarNSC":null,"yVal":null,"insCode":"65883838195688438","lVal30":"ايران‌ خودرو","lVal18AFC":"خودرو","flow":0,"cIsin":null,"zTitad":0.0,"baseVol":0,"instrumentID":null,"cgrValCot":null,"cComVal":null,"lastDate":0,"sourceID":0,"flowTitle":null,"cgrValCotTitle":null},"lastHEven":0,"finalLastDate":0,"nvt":0.0,"mop":0,"thirtyDayClosingHistory":null,"priceChange":-124.0,"priceMin":2427.0,"priceMax":2550.0,"priceYesterday":2554.0,"priceFirst":2550.0,"last":false,"id":0,"insCode":"65883838195688438","dEven":20231024,"hEven":0,"pClosing":2443.0,"iClose":false,"yClose":false,"pDrCotVal":2430.0,"zTotTran":11041.0,"qTotTran5J":359187582.0,"qTotCap":877671955345.0},}


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


# {"indexB1":[{"insCode":"32097828799138957","dEven":0,"hEven":192810,"xDrNivJIdx004":2000340.38,"xPhNivJIdx004":2021882.25,"xPbNivJIdx004":2000176.92,"xVarIdxJRfV":-1.0665,"last":false,"indexChange":-21563.19,"lVal30":"شاخص كل","c1":0,"c2":0,"c3":0,"c4":0},


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


# {"instEffect":[{"insCode":"46348559193224090","instrument":{"cValMne":null,"lVal18":null,"cSocCSAC":null,"lSoc30":"فولاد مباركه اصفهان","yMarNSC":null,"yVal":null,"insCode":"46348559193224090","lVal30":"فولاد مباركه اصفهان","lVal18AFC":"فولاد","flow":0,"cIsin":null,"zTitad":0.0,"baseVol":0,"instrumentID":null,"cgrValCot":null,"cComVal":null,"lastDate":0,"sourceID":0,"flowTitle":null,"cgrValCotTitle":null},"pClosing":5320.00,"instEffectValue":-1607.22},
class InstrumentEffectItem(BaseModel):
    ins_code: str = Field(default=None, alias="insCode")
    instrument: Optional[InstrumentInfo] = Field(default=None, alias="instrument")
    p_closing: Optional[float] = Field(default=None, alias="pClosing")
    inst_effect_value: Optional[float] = Field(default=None, alias="instEffectValue")


# {"marketOverview":{"lastDataDEven":0,"lastDataHEven":0,"indexLastValue":2000340.38,"indexChange":-21563.19,"indexEqualWeightedLastValue":676145.13,"indexEqualWeightedChange":-9759.97,"marketActivityDEven":20231024,"marketActivityHEven":180754,"marketActivityZTotTran":334358,"marketActivityQTotCap":63225765978423.00,"marketActivityQTotTran":9516840742.00,"marketState":"F","marketValue":69466091335710101.00,"marketValueBase":0.0,"marketStateTitle":"بسته"}}
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
