import pandas as pd
from typing import Dict, List, Any

def compute_instrument_series(
    leg_dataframes: Dict[str, pd.DataFrame], 
    calc_mode: str = 'RATIO', 
    sma_period: int = 20
) -> Dict[str, Any]:
    """
    Takes a dictionary of {symbol: DataFrame('date', 'close')} for each leg,
    aligns timestamps, calculates synthetic series, and derives indicators.
    """
    symbols = list(leg_dataframes.keys())
    
    if len(symbols) == 1:
        # Single instrument path
        df = leg_dataframes[symbols[0]].copy()
        df['value'] = df['close']
    else:
        # Multi-leg BAG calculation path
        df_primary = leg_dataframes[symbols[0]][['date', 'close']].rename(columns={'close': symbols[0]})
        df_secondary = leg_dataframes[symbols[1]][['date', 'close']].rename(columns={'close': symbols[1]})
        
        # Merge on timestamp and forward-fill missing ticks/gaps
        df = pd.merge(df_primary, df_secondary, on='date', how='outer').sort_values('date')
        df[symbols[0]] = df[symbols[0]].ffill()
        df[symbols[1]] = df[symbols[1]].ffill()
        df = df.dropna()

        # Compute synthetic metric
        if calc_mode == 'RATIO':
            df['value'] = df[symbols[0]] / df[symbols[1]]
        elif calc_mode == 'SPREAD':
            df['value'] = df[symbols[0]] - df[symbols[1]]
        else:
            raise ValueError(f"Unsupported calculation mode: {calc_mode}")

    # Calculate Technical Indicators in Python
    df['sma'] = df['value'].rolling(window=sma_period).mean()
    df['std'] = df['value'].rolling(window=sma_period).std()
    df['upper_band'] = df['sma'] + (2 * df['std'])
    df['lower_band'] = df['sma'] - (2 * df['std'])

    # Format dates for Lightweight Charts (YYYY-MM-DD or Unix timestamp)
    df['time'] = pd.to_datetime(df['date']).dt.strftime('%Y-%m-%d')

    return {
        "value_series": df[['time', 'value']].rename(columns={'value': 'value'}).dropna().to_dict(orient='records'),
        "sma_series": df[['time', 'sma']].rename(columns={'sma': 'value'}).dropna().to_dict(orient='records'),
        "upper_band": df[['time', 'upper_band']].rename(columns={'upper_band': 'value'}).dropna().to_dict(orient='records'),
        "lower_band": df[['time', 'lower_band']].rename(columns={'lower_band': 'value'}).dropna().to_dict(orient='records'),
    }

def compute_live_tick(prices: Dict[str, float], calc_mode: str, leg_symbols: List[str]) -> float:
    """Computes a single real-time synthetic value from incoming leg ticks."""
    if len(leg_symbols) == 1:
        return prices.get(leg_symbols[0], 0.0)
    
    p1 = prices.get(leg_symbols[0], 0.0)
    p2 = prices.get(leg_symbols[1], 0.0)
    
    if p1 <= 0 or p2 <= 0:
        return 0.0

    if calc_mode == 'RATIO':
        return p1 / p2
    elif calc_mode == 'SPREAD':
        return p1 - p2
    return 0.0
