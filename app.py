from flask import Flask, jsonify
from vnstock import stock_historical_data
import time
from datetime import datetime

app = Flask(__name__)

# =========================
# CACHE
# =========================
stock_cache = {
    "data": None,
    "time": 0
}

CACHE_TIME = 300  # 5 phút


# =========================
# FORMAT FUNCTIONS
# =========================
def format_price(x):
    return f"{x/1000:.2f}"   # 25750 -> 25.75

def format_volume(x):
    if x >= 1_000_000:
        return f"{x/1_000_000:.2f}M"
    elif x >= 1_000:
        return f"{x/1_000:.1f}K"
    return str(x)


# =========================
# GET DATA
# =========================
def fetch_stock_data():

    df = stock_historical_data(
        symbol="VCI",
        start_date="2025-01-01",
        end_date=datetime.today().strftime("%Y-%m-%d"),
        resolution="1D",
        type="stock",
        beautify=True
    )

    df = df.tail(10)

    # ép kiểu an toàn
    df["open"] = df["open"].astype(float)
    df["high"] = df["high"].astype(float)
    df["low"] = df["low"].astype(float)
    df["close"] = df["close"].astype(float)
    df["volume"] = df["volume"].astype(int)

    return df


# =========================
# CACHE FUNCTION
# =========================
def get_cached_data():

    now = time.time()

    if (
        stock_cache["data"] is None
        or now - stock_cache["time"] > CACHE_TIME
    ):
        stock_cache["data"] = fetch_stock_data()
        stock_cache["time"] = now

    return stock_cache["data"]


# =========================
# HOME PAGE (HTML)
# =========================
@app.route("/")
def home():

    df = get_cached_data()

    rows = ""

    for _, row in df.iterrows():
        rows += f"""
        <tr>
            <td>{row['time']}</td>
            <td>{format_price(row['open'])}</td>
            <td>{format_price(row['high'])}</td>
            <td>{format_price(row['low'])}</td>
            <td>{format_price(row['close'])}</td>
            <td>{format_volume(row['volume'])}</td>
        </tr>
        """

    return f"""
    <h1>📈 VCI Stock Dashboard</h1>

    <table border="1" cellpadding="8">
        <tr>
            <th>Date</th>
            <th>Open</th>
            <th>High</th>
            <th>Low</th>
            <th>Close</th>
            <th>Volume</th>
        </tr>
        {rows}
    </table>

    <br>
    <a href="/api/stock">JSON API</a>
    """


# =========================
# API JSON
# =========================
@app.route("/api/stock")
def api_stock():

    df = get_cached_data()

    # trả JSON đã format
    data = []

    for _, row in df.iterrows():
        data.append({
            "time": str(row["time"]),
            "open": format_price(row["open"]),
            "high": format_price(row["high"]),
            "low": format_price(row["low"]),
            "close": format_price(row["close"]),
            "volume": format_volume(row["volume"])
        })

    return jsonify(data)


# =========================
# RUN SERVER
# =========================
if __name__ == "__main__":
    app.run(debug=True)