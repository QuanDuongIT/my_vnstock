import time
from threading import Lock
from apscheduler.schedulers.background import BackgroundScheduler
from services.stock_filter import VNStockScanner

scanner = None

cached_df = None
cache_lock = Lock()

refresh_lock = Lock()
last_refresh_attempt = 0
MIN_REFRESH_INTERVAL = 60


def init_scanner(api_key):
    global scanner
    scanner = VNStockScanner(api_key=api_key)


def refresh_data():
    global cached_df, last_refresh_attempt

    now = time.time()

    if now - last_refresh_attempt < MIN_REFRESH_INTERVAL:
        return

    if not refresh_lock.acquire(blocking=False):
        return

    try:
        if scanner is None:
            return

        stats = scanner.scan(days=120)

        df_kept, df_removed = scanner.filter_top_n_per_time(
            stats,
            "group_name"
        )

        df_filtered = scanner.edge_filtered(df_kept, 3)
        df_filtered = df_filtered.sort_values(by="time", ascending=False)

        with cache_lock:
            cached_df = df_filtered

        last_refresh_attempt = time.time()

    finally:
        refresh_lock.release()


def get_cached_df():
    with cache_lock:
        return cached_df


def start_worker():
    scheduler = BackgroundScheduler(daemon=True)

    scheduler.add_job(
        refresh_data,
        "interval",
        minutes=10,
        max_instances=1,
        coalesce=True
    )

    scheduler.start()

    # warm up
    refresh_data()