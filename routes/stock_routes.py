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
import threading

stock_bp = Blueprint("stock", __name__)

@stock_bp.route("/")
def home():

    data = get_data()

    return render_template(
        "index.html",
        data=data,
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

    # acquire không block
    acquired = sync_lock.acquire(blocking=False)

    if not acquired:

        return jsonify({
            "status": "already syncing"
        })

    response = jsonify({
        "status": "success"
    })

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

    return response

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