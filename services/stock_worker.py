import time
from threading import Lock
from apscheduler.schedulers.background import BackgroundScheduler
from services.stock_filter import VNStockScanner

scanner = None

cached_df = None

# chống race condition
cache_lock = Lock()

# chống spam refresh
refresh_lock = Lock()
last_refresh_attempt = 0
MIN_REFRESH_INTERVAL = 60  # giây


def init_scanner(api_key):
    global scanner
    scanner = VNStockScanner(api_key=api_key)


def refresh_data():
    global cached_df, last_refresh_attempt

    now = time.time()

    # cooldown chống spam
    if now - last_refresh_attempt < MIN_REFRESH_INTERVAL:
        return

    # chỉ 1 thread được refresh
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

        # cập nhật cache
        with cache_lock:
            cached_df = df_filtered

        # ✅ ghi nhận SAU khi refresh thành công
        last_refresh_attempt = time.time()

    finally:
        refresh_lock.release()

def get_cached_df():
    with cache_lock:
        return cached_df

def start_worker():
    scheduler = BackgroundScheduler(daemon=True)

    # chạy định kỳ 10 phút
    scheduler.add_job(refresh_data, "interval", minutes=10, max_instances=1)

    scheduler.start()
    # warm up lần đầu
    refresh_data()