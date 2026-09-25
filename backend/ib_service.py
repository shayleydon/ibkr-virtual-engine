import asyncio
import threading

from typing import Dict, List, Callable
from ib_async import IB, Stock, Contract, util
import pandas as pd

class IBKRService:
    def __init__(self, host='127.0.0.1', port=4002, client_id=1):
        self.host = host
        self.port = port
        self.client_id = client_id
        self.ib = IB()
        self.live_prices: Dict[str, float] = {}
        self.active_subscriptions: Dict[str, Contract] = {}
        self.tick_callback: Callable = None

    def start(self):
        """Starts the IBKR asyncio connection loop in a background thread."""
        thread = threading.Thread(target=self._run_loop, daemon=True)
        thread.start()

    def _run_loop(self):
        asyncio.set_event_loop(asyncio.new_event_loop())
        self.ib.connect(self.host, self.port, clientId=self.client_id)
        self.ib.pendingTickersEvent += self._on_pending_tickers
        self.ib.run()

    def _on_pending_tickers(self, tickers):
        for t in tickers:
            symbol = t.contract.symbol
            price = t.marketPrice() or t.last or t.close
            if price and price > 0:
                self.live_prices[symbol] = price
                if self.tick_callback:
                    self.tick_callback(symbol, price)

    def fetch_historical_bars(self, symbol: str, duration: str = '1 Y', bar_size: str = '1 day') -> pd.DataFrame:
        """Fetch historical bar data for a single stock symbol."""
        contract = Stock(symbol, 'SMART', 'USD')
        self.ib.qualifyContracts(contract)
        
        bars = self.ib.reqHistoricalData(
            contract,
            endDateTime='',
            durationStr=duration,
            barSizeSetting=bar_size,
            whatToShow='TRADES',
            useRTH=True
        )
        return util.df(bars)[['date', 'close']]

    def subscribe_live_ticks(self, symbols: List[str]):
        """Subscribe to real-time market data for specified leg symbols."""
        for sym in symbols:
            if sym not in self.active_subscriptions:
                contract = Stock(sym, 'SMART', 'USD')
                self.ib.qualifyContracts(contract)
                self.ib.reqMktData(contract, '', False, False)
                self.active_subscriptions[sym] = contract

    def unsubscribe_all(self):
        """Unsubscribe from all active market data streams."""
        for contract in self.active_subscriptions.values():
            self.ib.cancelMktData(contract)
        self.active_subscriptions.clear()
