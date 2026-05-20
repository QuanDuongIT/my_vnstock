from flask import Flask, jsonify
from flask_sqlalchemy import SQLAlchemy
from vnstock import Vnstock
from datetime import datetime
import time
from config import DATABASE_URL

app = Flask(__name__)

app.config["SQLALCHEMY_DATABASE_URI"] = (DATABASE_URL)

app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "connect_args": {"sslmode": "require"}
}
db = SQLAlchemy(app)

# ======================================
# MODEL
# ======================================

class StockData(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    time = db.Column(db.String(50), unique=True)
    open = db.Column(db.Float)
    high = db.Column(db.Float)
    low = db.Column(db.Float)
    close = db.Column(db.Float)
    volume = db.Column(db.BigInteger)

# ======================================
# VNSTOCK (VNSTOCK3)
# ======================================

stock = Vnstock().stock(
    symbol="VCI",
    source="VCI"
)

# ======================================
# CACHE
# ======================================

cache = {
    "data": None,
    "time": 0
}

CACHE_TIME = 300  # 5 phút

# ======================================
# FORMAT
# ======================================

def format_price(x):
    return f"{float(x):.2f}"

def format_volume(x):
    x = int(x)
    if x >= 1_000_000:
        return f"{x/1_000_000:.2f}M"
    elif x >= 1_000:
        return f"{x/1_000:.1f}K"
    return str(x)

# ======================================
# FETCH DATA FROM VNSTOCK3
# ======================================

def fetch_stock_data():
    try:
        df = stock.quote.history(
            start="2025-01-01",
            end=datetime.today().strftime("%Y-%m-%d"),
            interval="1D"
        )

        df = df.tail(10)
        return df

    except Exception as e:
        print("FETCH ERROR:", e)
        return None

# ======================================
# SYNC DATA TO DATABASE
# ======================================

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

    db.session.commit()

# ======================================
# CACHE FUNCTION
# ======================================

def get_data():

    now = time.time()

    if cache["data"] is None or now - cache["time"] > CACHE_TIME:

        sync_to_db()

        cache["data"] = StockData.query.order_by(
            StockData.id.desc()
        ).limit(10).all()

        cache["time"] = now

    return cache["data"]

# ======================================
# HOME PAGE
# ======================================

@app.route("/")
def home():

    data = get_data()

    rows = ""

    for r in data:

        rows += f"""
        <tr>
            <td>{r.time}</td>
            <td>{format_price(r.open)}</td>
            <td>{format_price(r.high)}</td>
            <td>{format_price(r.low)}</td>
            <td>{format_price(r.close)}</td>
            <td>{format_volume(r.volume)}</td>
        </tr>
        """

    return f"""
    <html>
    <head>
        <title>VCI Stock Dashboard</title>
        <style>
            body {{
                font-family: Arial;
                padding: 20px;
                background: #f4f4f4;
            }}
            table {{
                width: 100%;
                border-collapse: collapse;
                background: white;
            }}
            th {{
                background: black;
                color: white;
                padding: 10px;
            }}
            td {{
                padding: 10px;
                border: 1px solid #ddd;
                text-align: center;
            }}
            tr:nth-child(even) {{
                background: #f9f9f9;
            }}
        </style>
    </head>

    <body>
        <h1>📈 VCI Stock Dashboard</h1>

        <table>
            <tr>
                <th>Time</th>
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
    </body>
    </html>
    """

# ======================================
# API
# ======================================

@app.route("/api/stock")
def api():

    data = get_data()

    return jsonify([
        {
            "time": r.time,
            "open": r.open,
            "high": r.high,
            "low": r.low,
            "close": r.close,
            "volume": r.volume
        }
        for r in data
    ])

# ======================================
# INIT DB
# ======================================

with app.app_context():
    db.create_all()

# ======================================
# RUN
# ======================================

if __name__ == "__main__":
    app.run(debug=True, use_reloader=False)