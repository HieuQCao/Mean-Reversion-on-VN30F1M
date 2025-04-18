import pandas as pd


class Strategy:  # Define the Strategy class
    def __init__(
        self,
        name="Strategy",
        initial_balance=1000000,
        fee=23.0,
        margin=0.25,
        **kwargs,  # Initialize the strategy with the given parameters
    ):
        self.name = name
        self.initial_balance = initial_balance
        self.fee = fee
        self.margin = margin
        self.kwargs = kwargs
        self.value_each_point = 100

        self.reset()

    def reset(self):  # Reset the strategy to its initial state
        self.balance = self.initial_balance
        self.position = 0
        self.entry_price = 0
        self.shares = 0
        self.history = {
            "datetime": [],
            "balance": [],
            "position": [],
            "price": [],
            "shares": [],
            "reason": [],
        }
        self.assets = {
            "datetime": [],
            "balance": [],
            "MDD": [],
        }
        self.MDD = 0
        self.max_balance = self.initial_balance

    def export_history(self):  # Export the history of the strategy
        # to data frame
        return pd.DataFrame(self.history)

    def export_assets(self):  # Export the assets of the strategy
        # to data frame
        return pd.DataFrame(self.assets)

    def max_share_purchase(self, price) -> int:
        return int(self.balance / (price * self.margin * self.value_each_point))

    def get_profit(self, price) -> float:
        return (
            (price - self.entry_price)
            * self.value_each_point
            * self.shares
            * self.position
        )

    def open_position(self, datetime, price, position, reason):
        self.shares = self.max_share_purchase(price)
        self.position = position
        self.entry_price = price
        self.balance -= self.fee * self.shares

        self.history["datetime"].append(datetime)
        self.history["balance"].append(self.balance)
        self.history["position"].append(self.position)
        self.history["price"].append(price)
        self.history["shares"].append(self.shares)
        self.history["reason"].append(reason)

    def close_position(self, datetime, price, reason):
        self.balance += self.get_profit(price) - self.fee * self.shares
        self.position = 0
        self.shares = 0

        self.history["datetime"].append(datetime)
        self.history["balance"].append(self.balance)
        self.history["position"].append(self.position)
        self.history["price"].append(price)
        self.history["shares"].append(self.shares)
        self.history["reason"].append(reason)

        self.max_balance = max(self.max_balance, self.balance)
        self.MDD = max(self.MDD, (self.max_balance - self.balance) / self.max_balance)

    def get_MDD(self):
        return self.MDD


class Strategy_1(Strategy):
    def __init__(
        self,
        name="Strategy_1",
        cut_loss_thres=0.008,
        sma_window=132,
        bb_window=133,
        bb_std=1.41,
        **kwargs,
    ):
        super().__init__(name=name, **kwargs)
        self.cut_loss_thres = cut_loss_thres
        self.sma_window = sma_window
        self.bb_window = bb_window
        self.bb_std = bb_std

    def get_sma(self, data, window):
        data["sma"] = data["Close"].rolling(window=window, min_periods=1).mean()

    def get_bollinger_bands(self, data, window, std):
        data["bb_middle"] = data["Close"].rolling(window=window, min_periods=1).mean()
        data["bb_upper"] = (
            data["bb_middle"]
            + std * data["Close"].rolling(window=window, min_periods=1).std()
        )
        data["bb_lower"] = (
            data["bb_middle"]
            - std * data["Close"].rolling(window=window, min_periods=1).std()
        )

        data["bb_upper"] = data["bb_upper"]
        data["bb_lower"] = data["bb_lower"]

    def run(self, data):
        self.get_sma(data, self.sma_window)
        self.get_bollinger_bands(data, self.bb_window, self.bb_std)

        signal = 0
        below_lower_flag = False
        above_upper_flag = False
        min_max_price = 0
        stop_loss_price = 0

        self.assets["datetime"].append(
            (data["datetime"].iloc[0] - pd.Timedelta(days=1)).date()
        )
        self.assets["balance"].append(self.balance)
        self.assets["MDD"].append(0)

        for index, row in data.iterrows():
            cur_date = row["datetime"].date()
            cur_price = row["Close"]

            if cur_date != self.assets["datetime"][-1]:
                self.assets["datetime"].append(cur_date)
                self.assets["balance"].append(self.balance + self.get_profit(cur_price))
                self.assets["MDD"].append(self.get_MDD())

            if (self.position == 1 and signal == -1) or (
                self.position == -1 and signal == 1
            ):
                self.close_position(row["datetime"], cur_price, "Signal Change")

            if signal != 0 and self.position == 0:
                self.open_position(
                    row["datetime"],
                    cur_price,
                    signal,
                    "buy" if signal == 1 else "sell",
                )
                signal = 0
                min_max_price = cur_price

            if self.position != 0:
                stop_loss_price = (
                    min_max_price * (1 - self.cut_loss_thres)
                    if self.position == 1
                    else min_max_price * (1 + self.cut_loss_thres)
                )
                if (self.position == 1 and cur_price <= stop_loss_price) or (
                    self.position == -1 and cur_price >= stop_loss_price
                ):
                    self.close_position(row["datetime"], cur_price, "Cut Loss")

                min_max_price = (
                    max(min_max_price, cur_price)
                    if self.position == 1
                    else min(min_max_price, cur_price)
                )

            if cur_price <= row["bb_lower"]:
                below_lower_flag = True
            elif cur_price >= row["bb_upper"]:
                above_upper_flag = True

            if below_lower_flag and cur_price >= row["sma"]:
                signal = 1  # buy
                below_lower_flag = False
            elif above_upper_flag and cur_price <= row["sma"]:
                signal = -1  # sell
                above_upper_flag = False

            self.assets["balance"][-1] = self.balance + self.get_profit(cur_price)
            self.assets["MDD"][-1] = self.get_MDD()

        return self.export_assets()


class Strategy_2(Strategy):
    def __init__(
        self,
        name="Strategy_2",
        cut_loss_thres=0.009,
        lookback_period=136,
        upbound=0.00264,
        downbound=0,
        sma_window=6,
        **kwargs,
    ):
        super().__init__(name=name, **kwargs)
        self.cut_loss_thres = cut_loss_thres
        self.sma_window = sma_window
        self.lookback_period = lookback_period
        self.upbound = upbound
        self.downbound = downbound

    def get_sma(self, data, window):
        data["sma"] = data["Close"].rolling(window=window, min_periods=1).mean()

    def get_rolling_return(self, data, window):
        data["rolling_return"] = data["Close"].pct_change(window)

    def run(self, data):
        self.get_sma(data, self.sma_window)
        self.get_rolling_return(data, self.lookback_period)

        signal = 0
        min_max_price = 0
        stop_loss_price = 0

        self.assets["datetime"].append(
            (data["datetime"].iloc[0] - pd.Timedelta(days=1)).date()
        )
        self.assets["balance"].append(self.balance)
        self.assets["MDD"].append(0)

        for index, row in data.iterrows():
            cur_date = row["datetime"].date()
            cur_price = row["Close"]

            if cur_date != self.assets["datetime"][-1]:
                self.assets["datetime"].append(cur_date)
                self.assets["balance"].append(self.balance + self.get_profit(cur_price))
                self.assets["MDD"].append(self.get_MDD())

            rolling_return = row["rolling_return"]

            if (self.position == 1 and signal == -1) or (
                self.position == -1 and signal == 1
            ):
                self.close_position(row["datetime"], cur_price, "Signal Change")

            if signal != 0 and self.position == 0:
                self.open_position(
                    row["datetime"],
                    row["Close"],
                    signal,
                    "buy" if signal == 1 else "sell",
                )
                signal = 0
                min_max_price = cur_price

            if self.position != 0:
                stop_loss_price = (
                    min_max_price * (1 - self.cut_loss_thres)
                    if self.position == 1
                    else min_max_price * (1 + self.cut_loss_thres)
                )
                if (self.position == 1 and cur_price <= stop_loss_price) or (
                    self.position == -1 and cur_price >= stop_loss_price
                ):
                    self.close_position(row["datetime"], cur_price, "Cut Loss")

                min_max_price = (
                    max(min_max_price, cur_price)
                    if self.position == 1
                    else min(min_max_price, cur_price)
                )
            # check is rolling return is not nan
            if pd.isnull(rolling_return):
                continue
            if rolling_return > self.upbound and cur_price > row["sma"]:
                signal = -1
            elif rolling_return < self.downbound and cur_price < row["sma"]:
                signal = 1

            self.assets["balance"][-1] = self.balance + self.get_profit(cur_price)
            self.assets["MDD"][-1] = self.get_MDD()

        return self.export_assets()
