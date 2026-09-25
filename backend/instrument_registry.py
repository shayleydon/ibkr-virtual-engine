from typing import List, Dict, Union, Optional
from dataclasses import dataclass, field

@dataclass
class SingleContractConfig:
    symbol: str
    sec_type: str = 'STK'    # STK, OPT, FUT, CRYPTO, CASH
    exchange: str = 'SMART'
    currency: str = 'USD'

@dataclass
class BAGLegConfig:
    symbol: str
    ratio: int              # e.g., 1 for Long, 1 for Short
    action: str             # 'BUY' or 'SELL'
    sec_type: str = 'STK'
    exchange: str = 'SMART'
    currency: str = 'USD'

@dataclass
class InstrumentDefinition:
    id: str                 # Unique Registry Identifier (e.g., 'HYG_SHY_RATIO')
    name: str               # Human readable name
    is_bag: bool
    # For single contracts
    single_config: Optional[SingleContractConfig] = None
    # For virtual/BAG contracts
    bag_legs: Optional[List[BAGLegConfig]] = None
    calc_mode: str = 'RATIO'  # 'RATIO' (Leg1/Leg2) or 'SPREAD' (Leg1 - Leg2)

class InstrumentRegistry:
    """Central registry for standard contracts and synthetic virtual instruments."""
    def __init__(self):
        self._registry: Dict[str, InstrumentDefinition] = {}
        self._seed_default_instruments()

    def register(self, instrument: InstrumentDefinition):
        self._registry[instrument.id] = instrument

    def get(self, instrument_id: str) -> Optional[InstrumentDefinition]:
        return self._registry.get(instrument_id)

    def list_all(self) -> List[Dict]:
        return [
            {
                "id": inst.id,
                "name": inst.name,
                "is_bag": inst.is_bag,
                "calc_mode": inst.calc_mode,
                "legs": [leg.symbol for leg in inst.bag_legs] if inst.is_bag else [inst.single_config.symbol]
            }
            for inst in self._registry.values()
        ]

    def _seed_default_instruments(self):
        """Seed default instruments and BAG spreads."""
        # 1. Straightforward Single Instrument: SPY
        self.register(InstrumentDefinition(
            id="SPY",
            name="SPDR S&P 500 ETF Trust",
            is_bag=False,
            single_config=SingleContractConfig(symbol="SPY")
        ))

        # 2. Virtual BAG Ratio: Credit/Rates Risk Ratio (HYG / SHY)
        self.register(InstrumentDefinition(
            id="HYG_SHY_RATIO",
            name="High Yield / Short Treasury Ratio",
            is_bag=True,
            calc_mode="RATIO",
            bag_legs=[
                BAGLegConfig(symbol="HYG", ratio=1, action="BUY"),
                BAGLegConfig(symbol="SHY", ratio=1, action="BUY")
            ]
        ))

        # 3. Virtual BAG Spread: Energy Pair Spread (XLE - XOP)
        self.register(InstrumentDefinition(
            id="XLE_XOP_SPREAD",
            name="Energy Select vs E&P Spread",
            is_bag=True,
            calc_mode="SPREAD",
            bag_legs=[
                BAGLegConfig(symbol="XLE", ratio=1, action="BUY"),
                BAGLegConfig(symbol="XOP", ratio=1, action="SELL")
            ]
        ))


registry = InstrumentRegistry()
