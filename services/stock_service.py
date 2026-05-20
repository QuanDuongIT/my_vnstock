from vnstock import Vnstock
from datetime import datetime
from models.stock_model import StockData, db
import time

stock = Vnstock().stock(
    symbol="VCI",
    source="VCI"
)

cache = {
    "data": None,
    "time": 0
}

CACHE_TIME = 300


def format_price(x):
    return f"{float(x):.2f}"


def format_volume(x):

    x = int(x)

    if x >= 1_000_000:
        return f"{x/1_000_000:.2f}M"

    elif x >= 1_000:
        return f"{x/1_000:.1f}K"

    return str(x)


def fetch_stock_data():

    try:

        df = stock.quote.history(
            start="2025-01-01",
            end=datetime.today().strftime("%Y-%m-%d"),
            interval="1D"
        )

        return df.tail(10)

    except Exception as e:

        print("FETCH ERROR:", e)

        return None


def sync_to_db():

    df = fetch_stock_data()

    if df is None:
        return

    for _, row in df.iterrows():

        t = str(row["time"])

        exists = StockData.query.filter_by(time=t).first()

        if not exists:

            item = StockData(
                time=t,
                open=float(row["open"]),
                high=float(row["high"]),
                low=float(row["low"]),
                close=float(row["close"]),
                volume=int(row["volume"])
            )

            db.session.add(item)

        else:

            exists.open = float(row["open"])
            exists.high = float(row["high"])
            exists.low = float(row["low"])
            exists.close = float(row["close"])
            exists.volume = int(row["volume"])

    db.session.commit()

# ======================================
# CRUD
# ======================================

def create_stock(data):

    item = StockData(
        time=data["time"],
        open=data["open"],
        high=data["high"],
        low=data["low"],
        close=data["close"],
        volume=data["volume"]
    )

    db.session.add(item)

    db.session.commit()

    return item


def get_stock_by_id(stock_id):

    return StockData.query.get(stock_id)


def update_stock(stock_id, data):

    item = StockData.query.get(stock_id)

    if not item:
        return None

    item.time = data.get("time", item.time)

    item.open = data.get("open", item.open)
    item.high = data.get("high", item.high)
    item.low = data.get("low", item.low)
    item.close = data.get("close", item.close)

    item.volume = data.get("volume", item.volume)

    db.session.commit()

    return item


def delete_stock(stock_id):

    item = StockData.query.get(stock_id)

    if not item:
        return False

    db.session.delete(item)

    db.session.commit()

    return True

def get_data():

    now = time.time()

    if cache["data"] is None or now - cache["time"] > CACHE_TIME:

        sync_to_db()

        cache["data"] = StockData.query.order_by(
            StockData.id.desc()
        ).limit(10).all()

        cache["time"] = now

    return cache["data"]