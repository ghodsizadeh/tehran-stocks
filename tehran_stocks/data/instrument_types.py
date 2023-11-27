from enum import Enum, unique


@unique
class InstrumentType(Enum):
    Stock_Exchange_Stocks = "O1"  # O1
    Farabourse_Stocks = "O3"  # O3
    Futures = "O4"  # O4
    Small_Company_in_Farabourse = "O5"  # O5
    Mortgage_Securities = "O6"  # O6
    Base_Market_Stocks = "O7"  # O7
    Call_Option = "OA"  # OA
    Put_Option = "OF"  # OF
    Subordinate_Put_Option = "S4"  # S4
    Commodities = "K1"  # Gold Coin, Saffron, Pistachio, Rice
    Unknown = "K2"  # Original: ???
    Fund = "T1"  # T1
    Farabourse_Fund = "T3"  # T3
    Commodity_Forward = "BK"  # BK
    Murabaha_Sukuk = "B3"  # B3
    Participation_Bonds = "B5"  # B5
    Governmental_Murabaha = "B4"  # B4
    Leasing_Sukuk = "B6"  # B6
    GAM_Sukuk = "B7"  # B7
    Right_of_Preemption = "R5"  # R5


# all O* and all T*
basic_instrument_types = [
    InstrumentType.Stock_Exchange_Stocks.value,
    InstrumentType.Farabourse_Stocks.value,
    InstrumentType.Futures.value,
    InstrumentType.Small_Company_in_Farabourse.value,
    InstrumentType.Base_Market_Stocks.value,
    InstrumentType.Call_Option.value,
    InstrumentType.Put_Option.value,
    InstrumentType.Commodities.value,
    InstrumentType.Fund.value,
    InstrumentType.Farabourse_Fund.value,
]
