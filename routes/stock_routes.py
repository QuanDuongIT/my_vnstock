from flask import Blueprint, jsonify, render_template, current_app
from services.stock_service import (
    get_data,
    format_price,
    format_volume,
    sync_to_db
)

from services.email_service import send_email
from services.stock_worker import get_cached_df, refresh_data

stock_bp = Blueprint("stock", __name__)


@stock_bp.route("/")
def home():
    df_filtered = get_cached_df()

    if df_filtered is None:
        refresh_data()
        df_filtered = get_cached_df()

    if df_filtered is None:
        return "Loading data...", 503

    return render_template(
        "index.html",
        data=get_data(),
        df_filtered=df_filtered,
        format_price=format_price,
        format_volume=format_volume
    )


@stock_bp.route("/test-mail")
def test_mail():
    send_email(
        subject="Test",
        body="Hello Flask",
        to_email="tieuduong.25.1.98@gmail.com"
    )
    return "Mail sent"


@stock_bp.route("/api/stock/data")
def api_data():
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


# =========================
# FIX: NO THREADING HERE
# =========================
@stock_bp.route("/api/stock/sync", methods=["POST"])
def api_stock_sync():
    try:
        with current_app.app_context():
            sync_to_db()

        return jsonify({"status": "success"}), 200

    except Exception as e:
        return jsonify({"status": "error", "msg": str(e)}), 500