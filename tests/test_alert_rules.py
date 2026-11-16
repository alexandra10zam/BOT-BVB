"""Unit tests for the alert rules in bot.verifica_simbol, using synthetic price series (no network)."""

import pandas as pd

from bot import SIMBOLURI, verifica_simbol

CFG = SIMBOLURI["TLV.RO"]  # drawdown threshold 15%, daily drop threshold 5%


def history(prices):
    index = pd.bdate_range(end="2026-11-13", periods=len(prices))
    return pd.DataFrame({"Close": prices}, index=index)


def test_no_alert_in_a_steady_uptrend():
    prices = [100 + i * 0.1 for i in range(300)]
    assert verifica_simbol("TLV.RO", CFG, history(prices)) == []


def test_drawdown_below_moving_average_triggers_buy_alert():
    # long plateau at 100, then a slow slide to 80: -20% from the 12-month high and below MA200
    prices = [100.0] * 250 + [100 - i for i in range(1, 21)]
    alerts = verifica_simbol("TLV.RO", CFG, history(prices))
    assert any("Condiție de cumpărare îndeplinită" in a for a in alerts)


def test_small_drawdown_does_not_trigger():
    prices = [100.0] * 250 + [100 - i * 0.5 for i in range(1, 21)]  # -10% only
    alerts = verifica_simbol("TLV.RO", CFG, history(prices))
    assert not any("Condiție de cumpărare îndeplinită" in a for a in alerts)


def test_sudden_daily_drop_triggers_alert():
    prices = [100.0] * 250 + [93.0]  # -7% in one day
    alerts = verifica_simbol("TLV.RO", CFG, history(prices))
    assert any("scădere bruscă" in a for a in alerts)


def test_not_enough_data_returns_warning():
    alerts = verifica_simbol("TLV.RO", CFG, history([100.0]))
    assert len(alerts) == 1 and alerts[0].startswith("⚠️")
