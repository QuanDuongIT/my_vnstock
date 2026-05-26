import time
from threading import Lock
from apscheduler.schedulers.background import BackgroundScheduler
from services.stock_filter import VNStockScanner
from services.email_service import send_email, send_email_html

scanner = None

cached_df = None
cache_lock = Lock()

refresh_lock = Lock()
last_refresh_attempt = 0
MIN_REFRESH_INTERVAL = 60


def init_scanner(api_key):
    global scanner
    scanner = VNStockScanner(api_key=api_key)

def dataframe_to_html(df):
    return df.to_html(
        index=False,
        border=1,
        justify="center"
    )

def refresh_data():
    global cached_df, last_refresh_attempt

    import time
    from datetime import datetime

    now = time.time()

    if now - last_refresh_attempt < MIN_REFRESH_INTERVAL:
        return

    if not refresh_lock.acquire(blocking=False):
        return

    try:

        if scanner is None:
            return

        # =========================
        # SCAN DATA
        # =========================

        stats = scanner.scan(days=120)

        df_kept, df_removed = scanner.filter_top_n_per_time(
            stats,
            "group_name"
        )

        df_filtered = scanner.edge_filtered(df_kept, 3)

        df_filtered = df_filtered.sort_values(
            by="time",
            ascending=False
        )

        # =========================
        # CACHE
        # =========================

        with cache_lock:
            cached_df = df_filtered

        # =========================
        # SEND EMAIL
        # =========================

        if not df_filtered.empty:

            today = datetime.now().strftime("%Y-%m-%d")

            rows_html = ""

            for _, row in df_filtered.iterrows():

                # =========================
                # BORDER COLOR
                # =========================

                border_color = "#e0e0e0"

                # RED
                if (
                    row["end_life_cycle"] is True
                    and row["exit_time"].strftime("%Y-%m-%d") == today
                ):
                    border_color = "#ef4444"

                # ORANGE
                elif (row["life_cycle"] - row["num_candel"]) == 1:
                    border_color = "#f97316"

                # GREEN
                elif row["num_candel"] == 0:
                    border_color = "#22c55e"

                # YELLOW
                elif row["num_candel"] <= 3:
                    border_color = "#eab308"

                # =========================
                # FORMAT VALUES
                # =========================

                end_life = (
                    "❌ Close"
                    if row["end_life_cycle"]
                    else "✅ Open"
                )

                exit_return_color = (
                    "#16a34a"
                    if row["exit_return"] > 0
                    else "#dc2626"
                )

                rows_html += f"""
                <tr>

                    <td style="
                        border-left: 8px solid {border_color};
                        border-top: 1px solid #e0e0e0;
                        border-bottom: 1px solid #e0e0e0;
                        padding: 10px;
                        text-align: center;
                        font-weight: bold;
                    ">
                        {row["symbol"]}
                    </td>

                    <td style="
                        border-top: 1px solid #e0e0e0;
                        border-bottom: 1px solid #e0e0e0;
                        padding: 10px;
                        text-align: center;
                    ">
                        {row["time"].strftime("%Y-%m-%d")}
                    </td>

                    <td style="
                        border-top: 1px solid #e0e0e0;
                        border-bottom: 1px solid #e0e0e0;
                        padding: 10px;
                        text-align: center;
                    ">
                        {row["exit_time"].strftime("%Y-%m-%d")}
                    </td>

                    <td style="
                        border-top: 1px solid #e0e0e0;
                        border-bottom: 1px solid #e0e0e0;
                        padding: 10px;
                        text-align: center;
                        color: {exit_return_color};
                        font-weight: bold;
                    ">
                        {row["exit_return"] * 100:.2f}%
                    </td>

                    <td style="
                        border-top: 1px solid #e0e0e0;
                        border-bottom: 1px solid #e0e0e0;
                        padding: 10px;
                        text-align: center;
                        font-weight: bold;
                    ">
                        {end_life}
                    </td>

                    <td style="
                        border-top: 1px solid #e0e0e0;
                        border-bottom: 1px solid #e0e0e0;
                        padding: 10px;
                        text-align: center;
                    ">
                        {row["num_candel"]}/{row["life_cycle"]}
                    </td>

                    <td style="
                        border-right: 1px solid #e0e0e0;
                        border-top: 1px solid #e0e0e0;
                        border-bottom: 1px solid #e0e0e0;
                        padding: 10px;
                        text-align: center;
                    ">
                        {row["valid_pct"]:.4f}
                    </td>

                </tr>
                """

            # =========================
            # TABLE
            # =========================

            html_table = f"""
            <table
                style="
                    border-collapse: collapse;
                    width: 100%;
                    font-size: 14px;
                    background: white;
                "
            >

                <thead>

                    <tr>

                        <th style="
                            background: #1976d2;
                            color: white;
                            padding: 12px;
                        ">
                            Symbol
                        </th>

                        <th style="
                            background: #1976d2;
                            color: white;
                            padding: 12px;
                        ">
                            Time
                        </th>

                        <th style="
                            background: #1976d2;
                            color: white;
                            padding: 12px;
                        ">
                            Exit Time
                        </th>

                        <th style="
                            background: #1976d2;
                            color: white;
                            padding: 12px;
                        ">
                            Exit Return
                        </th>

                        <th style="
                            background: #1976d2;
                            color: white;
                            padding: 12px;
                        ">
                            End Life
                        </th>

                        <th style="
                            background: #1976d2;
                            color: white;
                            padding: 12px;
                        ">
                            Life
                        </th>

                        <th style="
                            background: #1976d2;
                            color: white;
                            padding: 12px;
                        ">
                            Valid %
                        </th>

                    </tr>

                </thead>

                <tbody>
                    {rows_html}
                </tbody>

            </table>
            """

            # =========================
            # EMAIL HTML
            # =========================

            html = f"""
            <html>

                <body style="
                    font-family: Arial, sans-serif;
                    background-color: #f5f7fb;
                    padding: 20px;
                    color: #333;
                ">

                    <div style="
                        background: white;
                        border-radius: 12px;
                        padding: 24px;
                        box-shadow: 0 2px 8px rgba(0,0,0,0.08);
                    ">

                        <h2 style="
                            color: #1976d2;
                            margin-bottom: 20px;
                        ">
                            📈 VNStock Filter Updated
                        </h2>

                        <p style="
                            margin-bottom: 20px;
                            color: #555;
                        ">
                            Danh sách cổ phiếu mới nhất
                        </p>

                        {html_table}

                    </div>

                </body>

            </html>
            """

            send_email_html(
                subject="VNStock Filter Updated",
                html_body=html,
                to_email="tieuduong.25.1.98@gmail.com"
            )

        # =========================
        # UPDATE REFRESH TIME
        # =========================

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