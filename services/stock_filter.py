# @title run exit before2
import time
import heapq
import numpy as np
import pandas as pd

from collections import deque
from datetime import datetime, timedelta

from vnstock import register_user
from vnstock.api.listing import Listing
from vnstock.api.quote import Quote

class VNStockScanner:

    _initialized = False

    def __init__(
        self,
        api_key,
        max_req=55,
        window=60,
        exit_candle=1
    ):

        self.api_key = api_key

        self.MAX_REQ = max_req
        self.WINDOW = window
        self.EXIT_CANDLE = exit_candle

        self.REQUEST_TIMES = deque()

        self.init()

    # =========================
    # INIT
    # =========================
    def init(self):

        if not VNStockScanner._initialized:
            register_user(api_key=self.api_key)

            VNStockScanner._initialized = True

            print("✅ vnstock registered")

    # =========================
    # RATE LIMIT
    # =========================
    def rate_limit(self):

        while True:

            now = time.time()

            while (
                self.REQUEST_TIMES
                and now - self.REQUEST_TIMES[0] >= self.WINDOW
            ):
                self.REQUEST_TIMES.popleft()

            if len(self.REQUEST_TIMES) < self.MAX_REQ:
                self.REQUEST_TIMES.append(now)
                return

            wait_time = (
                self.WINDOW
                - (now - self.REQUEST_TIMES[0])
                + 0.1
            )

            print(f"⏳ sleep {wait_time:.1f}s")

            time.sleep(wait_time)

    # =========================
    # SYMBOLS
    # =========================
    def get_symbols(self):

        ls = Listing()

        vn30 = ls.symbols_by_group("VN30")
        hnx30 = ls.symbols_by_group("HNX30")

        symbols = pd.concat(
            [vn30, hnx30],
            ignore_index=True
        )

        return symbols

    # =========================
    # DOWNLOAD DATA
    # =========================
    def fetch_history(
        self,
        symbol,
        start_str,
        end_str
    ):

        self.rate_limit()

        q = Quote(
            symbol=symbol,
            source="KBS"
        )

        # data = q.history(
        #     start="2021-03-05",
        #     end="2026-03-04"
        # )
        
        data = q.history(
            start=start_str,
            end=end_str
        )


        if (
            data is None
            or data.empty
            or (data["volume"] <= 0).any()
            or data["volume"].isna().any()
        ):
            return None

        return data

    def window_time(
        self,
        days=120
    ):
        end_date = datetime.today()

        start_date = end_date - timedelta(days=days)

        start_str = start_date.strftime("%Y-%m-%d")
        end_str = end_date.strftime("%Y-%m-%d")

        return start_str, end_str
    
    # =========================
    # MAIN SCAN
    # =========================
    def scan(
        self,
        symbols=None,
        days=120
    ):

        if symbols is None:
            symbols = self.get_symbols()

        start_str, end_str = self.window_time(days=120)

        entrys = []

        for symbol in symbols:

            try:

                data = self.fetch_history(
                    symbol,
                    start_str,
                    end_str
                )

                # if data is None or len(data) < 1246:
                #     continue

                if data is None:
                    continue

                entries_symbol = self.process_entries(
                    data,
                    symbol,
                    "group_name",
                    self.EXIT_CANDLE
                )

                entrys.extend(entries_symbol)

                # print("OK:", symbol)

            except Exception as e:

                print("FAIL:", symbol, e)

                time.sleep(2)

        stats = pd.DataFrame(entrys)

        return stats
    
    def get_data_group(
        self,
        group="VN30",
        start_day="2021-03-05",
        end_day="2026-03-04",
        n_day=3
    ):
        q = Quote(symbol=group, source="KBS")

        data = q.history(
            start=start_day,
            end=end_day
        )

        data["time"] = pd.to_datetime(data["time"]).dt.normalize()

        n = len(data)

        # đủ n_day phía sau hay không
        data["end_life"] = (np.arange(n) + n_day < n)

        # index đích
        target_idx = np.minimum(np.arange(n) + n_day, n - 1)

        # giá đóng cửa tại thời điểm thoát lệnh
        data["exit_close"] = data["close"].iloc[target_idx].to_numpy()

        # lợi nhuận
        data["exit_return"] = (
            data["exit_close"] / data["close"] - 1
        )
        data["symbol"] = group
        data["num_candel"] = n_day


        return data
    # =========================
    # YOUR OLD FUNCTIONS
    # =========================

    def compute_rsi(self, df, length=14, price_col="close"):
        df = df.copy()

        delta = df[price_col].diff()

        gain = delta.clip(lower=0)
        loss = -delta.clip(upper=0)

        # Wilder's smoothing (RMA)
        avg_gain = gain.ewm(alpha=1/length, adjust=False).mean()
        avg_loss = loss.ewm(alpha=1/length, adjust=False).mean()

        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))

        df["RSI"] = rsi

        return df

    def resample_to_weekly(self, df):
        df = df.copy()

        df["time"] = pd.to_datetime(df["time"]).dt.tz_localize(None)
        df = df.sort_values("time").reset_index(drop=True)

        # giữ lại time
        df["time_copy"] = df["time"].to_numpy(dtype="datetime64[D]")

        df_week = (
            df.set_index("time")
            .resample("W-FRI")
            .agg({
                "open": "first",
                "high": "max",
                "low": "min",
                "close": "last",
                "volume": "sum",
                "time_copy": ["first", "last"]
            })
        )

        df_week.columns = ["open", "high", "low", "close", "volume", "time", "close_time"]

        df_week = df_week.dropna().reset_index(drop=True)

        return df_week

    def find_lower_line(self, x, y):
        def cost(k):
            z = y - k * x
            b = np.min(z)
            return np.sum(y - (k * x + b)), b

        left, right = -1.0, 1.0

        for _ in range(40):
            m1 = left + (right - left) / 3
            m2 = right - (right - left) / 3

            c1, _ = cost(m1)
            c2, _ = cost(m2)

            if c1 < c2:
                right = m2
            else:
                left = m1

        k = (left + right) / 2
        _, b = cost(k)
        return k, b

    def find_upper_line(self, x, y):
        def cost(k):
            z = y - k * x
            b = np.max(z)
            return np.sum((k * x + b) - y), b

        left, right = -1.0, 1.0

        for _ in range(40):
            m1 = left + (right - left) / 3
            m2 = right - (right - left) / 3

            c1, _ = cost(m1)
            c2, _ = cost(m2)

            if c1 < c2:
                right = m2
            else:
                left = m1

        k = (left + right) / 2
        _, b = cost(k)
        return k, b

    def find_line(self, x, y):
        x = np.asarray(x)
        y = np.asarray(y)

        x_mean = np.mean(x)
        y_mean = np.mean(y)

        # hệ số góc k
        k = np.sum((x - x_mean) * (y - y_mean)) / np.sum((x - x_mean) ** 2)

        # hệ số chặn b
        b = y_mean - k * x_mean

        return k, b

    def filter_top_n_per_time(self, stats, group_name):
        df = stats.copy()
        df["time"] = pd.to_datetime(df["time"])
        edge_head = 3
        start_str, end_str = self.window_time(days=120)
        vn30_data = self.get_data_group(group="VN30", start_day=start_str, end_day=end_str)

        def process_group(input_x):

            def edge_2():
                x = input_x[input_x["group_name"] == group_name].copy()


                # ===== CASE 1: điều kiện fail =====
                edge2 = None
                dow = x[
                    (x["candles_to_intersect"] < 0)
                    & (x["ma_type"] == True)
                    & (x["breakdown"] > 0)
                ]

                check = dow
                # for i in range(0, len(check)):
                #   df_day = pd.read_csv(f"/content/stock/{check["symbol"].iloc[i]}_5years.csv")
                # return check.sort_values("fibo", ascending=True).head(10 * len(check) // 10)

                top_n = check.loc[(check["k_range"]).abs().sort_values(ascending=True).index].head(3 * len(check) // 5)
                top_n = top_n.loc[(top_n["valid_pct"]-top_n["valid_pct"].mean()).abs().sort_values(ascending=True).index].head(3 * len(top_n) // 5)
                top_n["k_mean"] = top_n[["k_low", "k_high"]].mean(axis=1)
                top_n = top_n.loc[(top_n["k_mean"]).abs().sort_values(ascending=True).index].head(4 * len(top_n) // 5)
                # top_n = top_n.sort_values("valid_pct", ascending=False).head(3 * len(top_n) // 5)


                top_n = top_n.sort_values("valid_pct", ascending=False).head(3 * len(top_n) // 5)

                top_n = top_n[
                        (top_n["day_breakdown"] > 0)
                        & (top_n["k_low_pre"] > 0)
                        & (top_n["fibo"] > 0)
                    ]

                edge2 = top_n.sort_values("k_high", ascending=False)

                if edge2 is not None and len(edge2) > 0: return edge2.head(edge_head)

            def edge_1():
                x = input_x[input_x["group_name"] == group_name].copy()

                # ===== CHECK =====
                pct_positive = (x["diff"] > 0).mean()
                # pct_trend_low = (x["k_low"] > 0).mean()

                # ===== CASE 1: điều kiện fail =====
                edge1 = None
                up = x[
                    (x["candles_to_intersect"] >= 0)
                    & (x["breakdown"] > 0)
                    & (x["ma_type"] == True)
                ]

                check = up
                top_n = check.loc[(check["k_range"]).sort_values(ascending=False).index].head(3 * len(check) // 5)
                top_n = top_n.loc[(top_n["valid_pct"]-top_n["valid_pct"].mean()).abs().sort_values(ascending=True).index].head(3 * len(top_n) // 5)
                top_n["k_mean"] = top_n[["k_low", "k_high"]].mean(axis=1)
                top_n = top_n.loc[(top_n["k_mean"]).abs().sort_values(ascending=True).index].head(3 * len(top_n) // 5)

                if not top_n.empty and (top_n["day_of_week"] != 5).all():
                    top_n = top_n.sort_values("valid_pct", ascending=True).head(3 * len(top_n) // 5)

                    top_n = top_n[
                            (top_n["day_breakdown"] < 0)
                            # & (top_n["k_low_pre"] > 0)
                            & (top_n["fibo"] > 0)
                        ]
                else:
                    top_n = top_n.sort_values("valid_pct", ascending=False).head(3 * len(top_n) // 5)

                    top_n = top_n[
                            (top_n["day_breakdown"] > 0)
                            # & (top_n["k_low_pre"] > 0)
                            & (top_n["fibo"] > 0)
                        ]

                edge1 = top_n.sort_values("k_high", ascending=False)
                # edge1 = top_n.sort_values("k_mean", ascending=False).head(edge_head)
                # edge1 = top_n.head(edge_head)

                if edge1 is not None and len(edge1) > 0: return edge1.head(edge_head)


            def edge_short_2():
                x = input_x[
                    input_x["group_name"] == group_name
                ].copy()

                edge2 = None

                dow = x[
                    (x["candles_to_intersect"] < 0)
                    & (x["ma_type"] == False)
                    & (x["breakdown"] < 0)
                ]

                check = dow

                if len(check) == 0:
                    return None

                # =========================
                # FILTER
                # =========================

                top_n = check.loc[
                    (check["k_range"]).abs()
                    .sort_values(ascending=False).index
                ].head(3 * len(check) // 5)

                if len(top_n) == 0:
                    return None

                top_n = top_n.loc[
                    (top_n["valid_pct"] - top_n["valid_pct"].mean())
                    .abs()
                    .sort_values(ascending=True).index
                ].head(3 * len(top_n) // 5)

                if len(top_n) == 0:
                    return None

                top_n["k_mean"] = top_n[
                    ["k_low", "k_high"]
                ].mean(axis=1)

                top_n = top_n.loc[
                    (top_n["k_mean"])
                    .abs()
                    .sort_values(ascending=True).index
                ].head(4 * len(top_n) // 5)

                if len(top_n) == 0:
                    return None

                top_n = top_n.sort_values(
                    "valid_pct",
                    ascending=False
                ).head(3 * len(top_n) // 5)

                # =========================
                # FINAL CONDITION
                # =========================

                top_n = top_n[
                    # (top_n["day_breakdown"] < 0)
                    # # & (top_n["k_low_pre"] > 0)
                    # &
                        (top_n["fibo"] > 0)
                ]

                if len(top_n) == 0:
                    return None

                edge2 = top_n.sort_values(
                    "k_high",
                    ascending=False
                )
                if edge2 is not None and len(edge2) > 0:

                    row1 = edge2.head(1).copy()

                    match = vn30_data.loc[
                        vn30_data["time"].eq(row1["time"].iloc[0])
                    ]

                    if not match.empty:
                        row2 = match.iloc[0]

                        common_cols = row1.columns.intersection(row2.index)

                        row1.loc[row1.index[0], common_cols] = row2.loc[common_cols]

                    return row1

                return None

            def edge_short_1():

                x = input_x[
                    input_x["group_name"] == group_name
                ].copy()

                edge1 = None

                up = x[
                    (x["candles_to_intersect"] >= 0)
                    & (x["breakdown"] < 0)
                    & (x["ma_type"] == False)
                ]

                check = up

                if len(check) == 0:
                    return None

                # =========================
                # FILTER
                # =========================

                top_n = check.loc[
                    (check["k_range"])
                    .sort_values(ascending=False).index
                ].head(3 * len(check) // 5)

                if len(top_n) == 0:
                    return None

                top_n = top_n.loc[
                    (top_n["valid_pct"] - top_n["valid_pct"].mean())
                    .abs()
                    .sort_values(ascending=False).index
                ].head(3 * len(top_n) // 5)

                if len(top_n) == 0:
                    return None

                top_n["k_mean"] = top_n[
                    ["k_low", "k_high"]
                ].mean(axis=1)

                top_n = top_n.loc[
                    (top_n["k_mean"])
                    .abs()
                    .sort_values(ascending=True).index
                ].head(3 * len(top_n) // 5)

                if len(top_n) == 0:
                    return None

                # =========================
                # CONDITION
                # =========================

                if not top_n.empty and (top_n["day_of_week"] != 5).all():

                    top_n = top_n.sort_values(
                        "valid_pct",
                        ascending=False
                    ).head(3 * len(top_n) // 5)

                    top_n = top_n[
                        (top_n["day_breakdown"] < 0)
                        & (top_n["fibo"] > 0)
                    ]

                else:

                    top_n = top_n.sort_values(
                        "valid_pct",
                        ascending=True
                    ).head(3 * len(top_n) // 5)

                    # top_n = top_n[
                    #     (top_n["day_breakdown"] > 0)
                    #     & (top_n["fibo"] > 0)
                    # ]

                if len(top_n) == 0:
                    return None

                edge1 = top_n.sort_values(
                    "k_high",
                    ascending=False
                )

                if edge1 is not None and len(edge1) > 0:

                    row1 = edge1.head(1).copy()

                    match = vn30_data.loc[
                        vn30_data["time"].eq(row1["time"].iloc[0])
                    ]

                    if not match.empty:
                        row2 = match.iloc[0]

                        common_cols = row1.columns.intersection(row2.index)

                        row1.loc[row1.index[0], common_cols] = row2.loc[common_cols]

                    return row1

                return None


            result = []

            e2 = edge_2()
            if e2 is not None:
                result.append(e2)

            e1 = edge_1()
            if e1 is not None and len(result)==0:
                result.append(e1)


            if len(result) == 0:
                return pd.DataFrame()

            return pd.concat(result, ignore_index=True)

        df_kept = (
            df.groupby("time", group_keys=False)
              .apply(process_group)
              .reset_index(drop=True)
        )

        df_removed = df.merge(df_kept, how="left", indicator=True)
        df_removed = df_removed[df_removed["_merge"] == "left_only"].drop(columns=["_merge"])
        return df_kept, df_removed

    def edge_filtered(self, df_kept, max_overlap):
      # sort theo thời gian bắt đầu
      df_sorted = (
          df_kept
          .sort_values("time")
          .reset_index(drop=True)
      )

      selected_idx = []

      # min-heap lưu các edge đang active
      # mỗi phần tử: (exit_time, row_idx)
      active = []

      for idx, row in df_sorted.iterrows():

          start = row["time"]
          end = row["exit_time"]

          # remove các edge đã kết thúc
          while active and active[0][0] <= start:
              heapq.heappop(active)

          # nếu chưa vượt quá overlap
          if len(active) < max_overlap:
              selected_idx.append(idx)

              # thêm edge hiện tại vào active
              heapq.heappush(active, (end, idx))

      # dataframe sau lọc
      return df_sorted.iloc[selected_idx].reset_index(drop=True)


    def process_entries(self, df_day, symbol, group_name, EXIT_CANDLE):
        entrys = []

        df_day["time"] = pd.to_datetime(df_day["time"], errors="coerce").dt.tz_localize(None)
        df_day["time"] = df_day["time"].dt.normalize()

        df_day = df_day.dropna(subset=["time"]).sort_values("time").reset_index(drop=True)

        df = self.resample_to_weekly(df_day)

        window_zite = 9

        df["MA"] = df["close"].rolling(window_zite).mean()

        for i in range(window_zite, len(df)):
            signal_idx = i - 1
            trade_idx = i
            life_cycle = 15

            root_index = i - window_zite

            y = df["close"].iloc[max(0, root_index - 2):signal_idx].values
            x = np.arange(len(y))

            k_low, b_low = self.find_lower_line(x, y)
            k_high, b_high = self.find_upper_line(x, y)

            x_i = x[-1]
            close_i = y[-1]

            if abs(k_low - k_high) < 1e-9:
                x_intersect = 0
            else:
                x_intersect = (b_high - b_low) / (k_low - k_high)

            candles_to_intersect = x_intersect - x_i

            if candles_to_intersect >= 0:
                life_cycle = 5

            poit_low = k_low * x_i + b_low
            poit_high = k_high * x_i + b_high

            width = poit_high - poit_low

            if width > 1e-9:
                valid_pct = (poit_high - close_i) / width
                valid_pct = np.clip(valid_pct, -0.1, 1.1)
            else:
                valid_pct = 0.5

            ma_type = df["close"].iloc[signal_idx - 1] + df["close"].iloc[signal_idx - 3] >= 2 * df["close"].iloc[signal_idx - 2]

            y_pre = df["close"].iloc[max(0, root_index - 3):signal_idx - 1].values
            x_pre = np.arange(len(y_pre))

            k_low_pre, b_low_pre = self.find_lower_line(x_pre, y_pre)
            k_high_pre, b_high_pre = self.find_upper_line(x_pre, y_pre)

            price_day = df_day[
                (df_day["time"] >= df["time"].iloc[trade_idx]) &
                (df_day["time"] <= df["close_time"].iloc[trade_idx])
            ].copy()

            price_day = price_day.reset_index()

            for idx in range(len(price_day)):
                diff = price_day["close"].iloc[idx] - price_day["open"].iloc[idx]

                breakup = price_day["high"].iloc[0:idx + 1].min() / df["high"].iloc[min(signal_idx, len(df) - 1)] - 1

                weeek_low = df["low"].iloc[min(signal_idx, len(df) - 1)]

                breakdown = price_day["low"].iloc[0:idx + 1].min() / weeek_low - 1

                entry_time = price_day["time"].iloc[idx]

                entry_global_idx = df_day.index[df_day["time"] == entry_time][0]

                exit_global_idx = min(entry_global_idx + life_cycle + 5, len(df_day) - 1)

                day_breakdown = df_day["low"].iloc[entry_global_idx] / df_day["low"].iloc[entry_global_idx - 1] - 1

                day_breakdown_pre = df_day["low"].iloc[entry_global_idx] / df_day["low"].iloc[entry_global_idx - 2:entry_global_idx].min() - 1


                with_cl_h = price_day["close"].iloc[idx] - df["low"].iloc[min(signal_idx, len(df) - 1)]

                with_fibo = df["high"].iloc[min(signal_idx, len(df) - 1)] - df["low"].iloc[min(signal_idx, len(df) - 1)]

                if with_fibo == 0:
                    fibo = 0.5 - k_low
                else:
                    fibo = with_cl_h / with_fibo - k_low

                exit_row = df_day.iloc[exit_global_idx]

                exit_return = exit_row["close"] / price_day["close"].iloc[idx] - 1
                end_life_cycle = False

                exit_time = exit_row["time"]

                start = min(entry_global_idx + 3, len(df_day) - 1)

                start_midle = min(entry_global_idx + life_cycle // 2 + 3, len(df_day) - 1)

                end = min(entry_global_idx + life_cycle + 5, len(df_day) - 1)

                is_midle = False

                midl_weeek_low = weeek_low * 2 - df_day["close"].iloc[entry_global_idx]

                if candles_to_intersect < 0:
                    exit_weekday_num = df_day["time"].iloc[start].weekday() + 1

                    num_candel = exit_global_idx - entry_global_idx

                    for _e in range(start, start_midle + 1):
                        exit_row = df_day.iloc[_e]

                        exit_breakdown = df_day["low"].iloc[entry_global_idx + 3:_e].min() / weeek_low - 1

                        exit_breakdown_midl = df_day["low"].iloc[_e].min() / midl_weeek_low - 1

                        if exit_breakdown_midl < 0:
                            exit_return = exit_row["close"] / price_day["close"].iloc[idx] - 1

                            exit_weekday_num = exit_row["time"].weekday() + 1

                            num_candel = _e - entry_global_idx

                            exit_time = exit_row["time"]

                            is_midle = True
                            end_life_cycle = True
                            break

                if is_midle is False:
                    exit_global_idx = min(entry_global_idx + life_cycle + 5, len(df_day) - 1)

                    exit_row = df_day.iloc[exit_global_idx]

                    exit_return = exit_row["close"] / price_day["close"].iloc[idx] - 1

                    exit_time = exit_row["time"]

                    exit_weekday_num = df_day["time"].iloc[start].weekday() + 1

                    num_candel = exit_global_idx - entry_global_idx

                    for _e in range(start_midle, end + 1):
                        exit_row = df_day.iloc[_e]

                        exit_breakdown = df_day["low"].iloc[entry_global_idx + 3:_e].min() / weeek_low - 1

                        exit_breakdown_pre = (
                            df_day["low"].iloc[entry_global_idx + 2:min(_e - 1, start_midle)].min()
                            / weeek_low
                            - 1
                        )

                        exit_breakdown_midl = df_day["low"].iloc[_e].min() / midl_weeek_low - 1

                        if exit_breakdown_midl < 0:
                            exit_return = exit_row["close"] / price_day["close"].iloc[idx] - 1

                            exit_weekday_num = exit_row["time"].weekday() + 1

                            num_candel = _e - entry_global_idx

                            exit_time = exit_row["time"]
                            end_life_cycle = True

                            break

                        if (((   exit_row["close"] > df["high"].iloc[min(signal_idx, len(df) - 1)]
                                or exit_row["close"] < df["low"].iloc[min(signal_idx, len(df) - 1)])
                                and (exit_row["high"] - exit_row["close"]
                                    < exit_row["close"] - exit_row["low"]))
                                or (exit_breakdown < 0 and exit_breakdown < exit_breakdown_pre)):

                            if (
                                exit_row["close"] > df["high"].iloc[min(signal_idx, len(df) - 1)]
                                and (exit_row["high"] - exit_row["close"]) < (exit_row["close"] - exit_row["low"])):
                                exit_row = df_day.iloc[min(_e + 1, end)]

                            exit_return = exit_row["close"] / price_day["close"].iloc[idx] - 1

                            exit_weekday_num = exit_row["time"].weekday() + 1

                            num_candel = _e - entry_global_idx

                            exit_time = exit_row["time"]
                            end_life_cycle = True

                            break

                weekday_num = price_day["time"].iloc[idx].weekday() + 1
                if num_candel == life_cycle + 5:
                  end_life_cycle = True

                entrys.append({
                    "week_time": df["time"].iloc[trade_idx],
                    "time": price_day["time"].iloc[idx],
                    "fibo": fibo,
                    "exit_time": exit_time,
                    "day_of_week": weekday_num,
                    "exit_weekday_num": exit_weekday_num,
                    "life_cycle": life_cycle + 5,
                    "end_life_cycle": end_life_cycle,
                    "num_candel": num_candel,
                    "symbol": symbol,
                    "group_name": group_name,
                    "valid_pct": valid_pct,
                    "k_range": k_high - k_low,
                    "k_high": k_high,
                    "k_low": k_low,
                    "k_high_pre": k_high_pre,
                    "k_low_pre": k_low_pre,
                    "candles_to_intersect": candles_to_intersect,
                    "ma_type": ma_type,
                    "diff": diff,
                    "breakdown": breakdown,
                    "day_breakdown": day_breakdown,
                    "exit_return": exit_return
                })

        return entrys
