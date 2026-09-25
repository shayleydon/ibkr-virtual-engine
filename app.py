from datetime import datetime
from flask import Flask, jsonify, request
from flask_socketio import SocketIO, emit
from instrument_registry import registry, InstrumentDefinition, SingleContractConfig, BAGLegConfig
from calculation_engine import compute_instrument_series, compute_live_tick
from ib_service import IBKRService

app = Flask(__name__)
app.config['SECRET_KEY'] = 'quant_secret'
socketio = SocketIO(app, cors_allowed_origins="*")

# Initialize IBKR Service
ib_service = IBKRService(host='127.0.0.1', port=4002, client_id=1)
ib_service.start()

active_stream_instrument_id = None

def handle_ib_tick(symbol: str, price: float):
    """Callback fired whenever IBKR receives a price tick."""
    global active_stream_instrument_id
    if not active_stream_instrument_id:
        return

    inst = registry.get(active_stream_instrument_id)
    if not inst:
        return

    leg_symbols = [leg.symbol for leg in inst.bag_legs] if inst.is_bag else [inst.single_config.symbol]
    live_value = compute_live_tick(ib_service.live_prices, inst.calc_mode, leg_symbols)

    if live_value > 0:
        socketio.emit('live_tick', {
            'instrument_id': inst.id,
            'time': datetime.now().strftime('%Y-%m-%d'),
            'value': live_value,
            'prices': ib_service.live_prices
        })

ib_service.tick_callback = handle_ib_tick

# ---------------- REST ENDPOINTS ----------------

@app.route('/api/instruments', methods=['GET'])
def get_instruments():
    """List all registered single and BAG instruments."""
    return jsonify(registry.list_all())

@app.route('/api/instruments/register', methods=['POST'])
def register_instrument():
    """
    Dynamically add a new single or BAG instrument to the registry.
    Example Payload (BAG):
    {
      "id": "GLD_SLV_RATIO",
      "name": "Gold / Silver Ratio",
      "is_bag": true,
      "calc_mode": "RATIO",
      "bag_legs": [
        {"symbol": "GLD", "ratio": 1, "action": "BUY"},
        {"symbol": "SLV", "ratio": 1, "action": "BUY"}
      ]
    }
    """
    data = request.json
    is_bag = data.get('is_bag', False)

    if is_bag:
        legs = [BAGLegConfig(**leg) for leg in data.get('bag_legs', [])]
        inst = InstrumentDefinition(
            id=data['id'],
            name=data['name'],
            is_bag=True,
            calc_mode=data.get('calc_mode', 'RATIO'),
            bag_legs=legs
        )
    else:
        config = SingleContractConfig(**data.get('single_config', {'symbol': data['id']}))
        inst = InstrumentDefinition(
            id=data['id'],
            name=data['name'],
            is_bag=False,
            single_config=config
        )

    registry.register(inst)
    return jsonify({"status": "success", "registered": inst.id})

@app.route('/api/historical/<instrument_id>', methods=['GET'])
def get_historical(instrument_id):
    """Fetch historical data and compute ratio/indicators for a registered instrument."""
    inst = registry.get(instrument_id)
    if not inst:
        return jsonify({"error": "Instrument not found"}), 404

    # Determine required leg symbols
    leg_symbols = [leg.symbol for leg in inst.bag_legs] if inst.is_bag else [inst.single_config.symbol]
    
    # Fetch historical data for all required legs via IBKR
    leg_dfs = {}
    for sym in leg_symbols:
        leg_dfs[sym] = ib_service.fetch_historical_bars(sym, duration='1 Y', bar_size='1 day')

    # Compute spread/ratio and indicators in Python
    result = compute_instrument_series(leg_dfs, calc_mode=inst.calc_mode, sma_period=20)
    return jsonify(result)

# ---------------- WEBSOCKET EVENTS ----------------

@socketio.on('toggle_stream')
def handle_toggle_stream(data):
    global active_stream_instrument_id
    active = data.get('active', False)
    instrument_id = data.get('instrument_id')

    if active and instrument_id:
        inst = registry.get(instrument_id)
        if inst:
            active_stream_instrument_id = instrument_id
            leg_symbols = [leg.symbol for leg in inst.bag_legs] if inst.is_bag else [inst.single_config.symbol]
            ib_service.subscribe_live_ticks(leg_symbols)
            emit('stream_state', {'active': True, 'instrument_id': instrument_id})
    else:
        active_stream_instrument_id = None
        ib_service.unsubscribe_all()
        emit('stream_state', {'active': False, 'instrument_id': None})

if __name__ == '__main__':
    socketio.run(app, debug=True, port=5000)
