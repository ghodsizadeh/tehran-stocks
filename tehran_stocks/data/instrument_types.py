from enum import Enum, unique


@unique
class InstrumentType(Enum):
    Small_Company_in_Farabourse = "O5"
    Put_Option = "OF"
    Farabourse_Stocks = "O3"
    Fund = "T1"
    Commodity_Forward = "BK"
    Murabaha_Sukuk = "B3"
    Commodities = "K1"  # Gold Coin, Saffron, Pistachio, Rice
    Mortgage_Securities = "O6"
    Participation_Bonds = "B5"
    Base_Market_Stocks = "O7"
    Call_Option = "OA"
    Right_of_Preemption = "R5"
    Farabourse_Fund = "T3"
    GAM_Sukuk = "B7"
    Subordinate_Put_Option = "S4"
    Stock_Exchange_Stocks = "O1"
    Governmental_Murabaha = "B4"
    Futures = "O4"
    Leasing_Sukuk = "B6"
