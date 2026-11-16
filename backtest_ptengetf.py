"""Backtest pentru alertele PTENGETF, fara trimitere de notificari."""

import pandas as pd
import yfinance as yf

from bot import SIMBOLURI, verifica_simbol

SYMBOL = "PTENGETF.RO"


def load_close_prices():
    history = yf.download(SYMBOL, period="max", interval="1d", progress=False)
    close = history["Close"]
    if isinstance(close, pd.DataFrame):
        close = close.iloc[:, 0]
    return close.dropna().sort_index()


def run_backtest(close):
    start_date = close.index.max() - pd.Timedelta(days=365)
    alerts = []
    evaluated_days = 0
    config = SIMBOLURI[SYMBOL]

    for position in range(1, len(close)):
        current_date = close.index[position]
        if current_date < start_date:
            continue

        evaluated_days += 1
        known_prices = close.iloc[: position + 1]
        messages = verifica_simbol(SYMBOL, config, known_prices.to_frame("Close"))
        for message in messages:
            if "Condiție de cumpărare îndeplinită" in message:
                alerts.append((current_date, "drawdown", message))
            elif "scădere bruscă" in message:
                alerts.append((current_date, "scadere zilnica", message))

    return evaluated_days, alerts


if __name__ == "__main__":
    prices = load_close_prices()
    if len(prices) < 2:
        raise SystemExit("Nu exista suficiente date pentru backtest.")

    evaluated_days, alerts = run_backtest(prices)
    drawdown_alerts = [alert for alert in alerts if alert[1] == "drawdown"]
    daily_drop_alerts = [alert for alert in alerts if alert[1] == "scadere zilnica"]

    print(f"Simbol: {SYMBOL}")
    print(f"Perioada disponibila: {prices.index.min().date()} - {prices.index.max().date()}")
    print(f"Zile evaluate in ultimul an: {evaluated_days}")
    print(f"Alerte drawdown: {len(drawdown_alerts)}")
    print(f"Alerte scadere zilnica: {len(daily_drop_alerts)}")

    if alerts:
        print("\nAlerte detectate:")
        for alert in alerts:
            date, alert_type, message = alert
            print(f"{date.date()} | {alert_type} | {message}")
    else:
        print("Nu au fost detectate alerte.")
