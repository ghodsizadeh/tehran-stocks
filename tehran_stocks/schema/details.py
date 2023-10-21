from typing import  Optional

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
