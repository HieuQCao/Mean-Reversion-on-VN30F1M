# Database connection parameters
import psycopg2
import pandas as pd
import matplotlib.pyplot as plt
import json
import numpy as np

db_params = {
    "host": "api.algotrade.vn",
    "port": 5432,
    "database": "algotradeDB",
    "user": "intern_read_only",
    "password": "ZmDaLzFf8pg5",
}

connection = psycopg2.connect(**db_params)


def execute_query(query, from_date, to_date):
    cursor = connection.cursor()
    try:
        cursor.execute(query, (from_date, to_date))
        result = cursor.fetchall()

        cursor.close()
        return result

    except Exception as e:
        print(f"Error: {e}")


matched_query = """
    WITH filtered_matched AS (
    SELECT m.datetime, m.tickersymbol, m.price
    FROM quote.matched m
    JOIN quote.futurecontractcode fc
        ON m.tickersymbol = fc.tickersymbol AND DATE(m.datetime) = fc.datetime
    WHERE fc.futurecode = 'VN30F1M'
        AND m.datetime BETWEEN %s AND %s
        AND (
        (EXTRACT(HOUR FROM m.datetime) >= 9 AND EXTRACT(HOUR FROM m.datetime) < 14)
        OR (EXTRACT(HOUR FROM m.datetime) = 14 AND EXTRACT(MINUTE FROM m.datetime) < 30)
        )
    )
    SELECT fm.datetime, fm.tickersymbol, fm.price, mv.quantity AS volume
    FROM filtered_matched fm
    JOIN quote.matchedvolume mv
    ON fm.datetime = mv.datetime AND fm.tickersymbol = mv.tickersymbol
    ORDER BY fm.datetime;
"""


def get_matched(from_date, to_date, save_path=None):
    matched = pd.DataFrame(
        execute_query(matched_query, from_date, to_date),
        columns=["datetime", "tickersymbol", "price", "volume"],
    )
    matched = matched.astype({"price": float})
    matched.to_csv(save_path, index=False)


def group_to_ohlc(df, freq="1H"):
    df = (
        df.resample(freq)
        .apply(
            lambda g: pd.Series(
                {
                    "Open": g["price"].iloc[0] if not g.empty else None,
                    "High": g["price"].max() if not g.empty else None,
                    "Low": g["price"].min() if not g.empty else None,
                    "Close": g["price"].iloc[-1] if not g.empty else None,
                    "Volume": g["volume"].sum() if not g.empty else None,
                    "VWAP": (
                        (g["price"] * g["volume"]).sum() / g["volume"].sum()
                        if g["volume"].sum() > 0
                        else None
                    ),
                }
            )
        )
        .dropna()
    )
    # df.columns = df.columns.droplevel()
    return df


def plot_assets(assets):
    # Convert 'datetime' column to pandas datetime
    assets["datetime"] = pd.to_datetime(assets["datetime"])

    # Create a plot
    plt.figure(figsize=(10, 6))
    plt.plot(assets["datetime"], assets["balance"], label="Balance", color="blue")

    # Add labels and title
    plt.xlabel("Datetime")
    plt.ylabel("Balance")
    plt.title("Asset Balance Over Time")

    # Format the datetime on the x-axis for better readability
    plt.xticks(rotation=45)

    # Show a grid for easier reading of values
    plt.grid(True)

    # Show the plot
    plt.tight_layout()
    plt.show()


def plot_max_dd(assets):

    # Create a plot
    plt.figure(figsize=(10, 6))
    plt.plot(assets["datetime"], assets["MDD"], label="Drawdown", color="red")

    # Add labels and title
    plt.xlabel("Datetime")
    plt.ylabel("Drawdown")
    plt.title(f"Max Drawdown Over Time")

    # Format the datetime on the x-axis for better readability
    plt.xticks(rotation=45)

    # Show a grid for easier reading of values
    plt.grid(True)

    # Show the plot
    plt.tight_layout()
    plt.show()


def save_best_parameters(best_trials, output_file="best_params_1D.json"):
    for trial in best_trials:
        print(trial.values)
        print(trial.params)

    # Save best parameters to a JSON file
    with open(output_file, "w") as f:
        json.dump([trial.params for trial in best_trials], f)


def calcualte_sharpe_ratio(assets):
    risk_free_rate = 0.05 / 252
    assets["return"] = assets["balance"].pct_change()
    df = assets.dropna()
    expected_return = df["return"].mean()
    volatility = df["return"].std()
    if volatility == 0:
        if expected_return > risk_free_rate:
            return float(
                "inf"
            )  # Sharpe Ratio vô hạn nếu lợi nhuận vượt qua tỷ suất phi rủi ro
        else:
            return 0
    sharpe_ratio = (expected_return - risk_free_rate) / volatility * np.sqrt(252)

    # print(f"Expected return: {expected_return} - Volatility: {volatility}")
    return sharpe_ratio


def run_strategy_and_plot(strategy_class, json_file, data, output_prefix):
    with open(json_file, "r") as file:
        strategies_params = json.load(file)

    best_sharpe_ratio = -float("inf")
    best_MDD = float("inf")
    best_assets = None
    best_history = None
    best_param = None

    for params in strategies_params:

        strategy = strategy_class(**params)
        assets = strategy.run(data)

        # Tính toán Sharpe Ratio và MDD
        sharpe_ratio = calcualte_sharpe_ratio(assets)

        # So sánh để tìm chiến lược có Sharpe Ratio cao nhất
        if sharpe_ratio > best_sharpe_ratio:
            best_sharpe_ratio = sharpe_ratio
            best_MDD = strategy.get_MDD()
            best_assets = assets
            best_history = strategy.export_history()
            best_param = params

    # In chiến lược tốt nhất và Sharpe Ratio
    print(f"Best Sharpe Ratio: {best_sharpe_ratio} - Best MDD: {best_MDD}")
    print(f"Profit: {best_assets['balance'].iloc[-1] / 1000000}")
    print(f"Best parameters: {best_param}")

    # Lưu kết quả vào CSV
    best_assets.to_csv(f"records\\{output_prefix}_best_assets.csv")
    best_history.to_csv(f"records\\{output_prefix}_best_history.csv")

    # Vẽ đồ thị của chiến lược tốt nhất
    plot_assets(best_assets)
    plot_max_dd(best_assets)
