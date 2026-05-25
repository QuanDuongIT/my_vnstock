from flask import Blueprint, jsonify, render_template, current_app, request
from services.stock_service import (
    get_data,
    format_price,
    format_volume,
    sync_to_db,
    create_stock,
    get_stock_by_id,
    update_stock,
    delete_stock
)

from services.email_service import send_email
from services.stock_filter import VNStockScanner
import threading
from services.stock_worker import get_cached_df, refresh_data

stock_bp = Blueprint("stock", __name__)

@stock_bp.route("/")
def home():

    df_filtered = get_cached_df()

    # fallback nếu cache rỗng
    if df_filtered is None:
        refresh_data()
        df_filtered = get_cached_df()

    # vẫn rỗng thì báo loading
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

sync_lock = threading.Lock()

@stock_bp.route("/api/stock")
def api_stock():

    acquired = sync_lock.acquire(blocking=False)

    if not acquired:
        return jsonify({
            "status": "already syncing"
        }), 409

    try:
        with current_app.app_context():
            sync_to_db()

        return jsonify({
            "status": "success"
        })

    finally:
        sync_lock.release()

@stock_bp.route("/api/stock/sync", methods=["POST"])
def api_stock_sync():

    acquired = sync_lock.acquire(blocking=False)

    if not acquired:
        return jsonify({
            "status": "already syncing"
        }), 409

    app = current_app._get_current_object()

    def background_sync():
        try:
            with app.app_context():
                sync_to_db()
        finally:
            sync_lock.release()

    threading.Thread(
        target=background_sync,
        daemon=True
    ).start()

    return jsonify({
        "status": "started"
    }), 202