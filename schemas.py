
from pydantic import BaseModel
from datetime import datetime
from typing import List

class TradeHistoryBase(BaseModel):
    account_id: int
    position_id: int
    magic: int
    symbol: str
    balance_start: float
    balance_end: float
    profit: float
    profit_percents: float
    ticket_in: int
    ticket_out: int
    order_in: int
    order_out: int
    type_in: int
    type_out: int
    entry_in: int
    entry_out: int
    reason_in: int
    reason_out: int
    volume_in: float
    volume_out: float
    price_in: float
    price_out: float
    comment_in: str
    comment_out: str
    external_id_in: str
    external_id_out: str
    time_in: datetime
    time_out: datetime
    time_duration: float  # seconds
    margin: float
    margin_load: float
    draw_down: float
    draw_down_level: float
    draw_down_max_high: float
    draw_down_min_low: float

class TradeHistoryCreate(TradeHistoryBase):
    pass

class TradeHistory(TradeHistoryBase):
    id: int

    class Config:
        # orm_mode = True
        from_attributes = True

class AccountBase(BaseModel):
    login: int
    password: str
    server: str
    title: str
    description: str
    active: bool
    is_online: bool
    is_draw: bool

class AccountCreate(AccountBase):
    pass

class Account(AccountBase):
    id: int
    trade_history: List[TradeHistory] = []

    class Config:
        # orm_mode = True
        from_attributes = True
