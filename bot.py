"""
ALERTĂ SCĂDERE BURSĂ — TLV (Banca Transilvania) și PTENGETF (ETF Energie Patria-Tradeville)

CE FACE SCRIPTUL
Rulează O SINGURĂ VERIFICARE pe rulare (nu stă în buclă). Îl programezi să ruleze
la fiecare 15-30 min în orele de tranzacționare BVB (10:00-18:00, luni-vineri)
folosind cron (Linux/Mac) sau Task Scheduler (Windows) — vezi instrucțiunile de
la finalul fișierului.

REGULA DE ALERTĂ (per simbol, praguri diferite):
  - TLV:      alertă "drawdown" dacă preț < -15% față de maximul din ultimele 12 luni
              ȘI preț sub media mobilă pe 200 zile (MA200)
              + alertă separată "mișcare bruscă" dacă scade > 5% într-o zi
  - PTENGETF: alertă "drawdown" dacă preț < -10% față de maximul din ultimele 12 luni
              ȘI preț sub media mobilă pe 200 zile (MA200)
              + alertă separată "mișcare bruscă" dacă scade > 3% într-o zi

INSTALARE (o singură dată):
  pip install yfinance requests --break-system-packages

CONFIGURARE OBLIGATORIE: variabila de mediu NTFY_TOPIC (nu se mai ține în cod,
fiindcă repo-ul e public și oricine ar putea citi/trimite pe topic).
Cum funcționează (fără cont, fără token):
  1. Instalează aplicația "ntfy" (iOS/Android) sau folosește https://ntfy.sh/app în browser.
  2. Alege un nume de topic UNIC și greu de ghicit (topicurile ntfy.sh sunt publice —
     oricine știe exact numele poate citi/trimite pe el), ex: "alerta-bursa-ax7k2m9".
  3. În aplicație, apasă "+" și abonează-te la topicul ales.
  4. Setează variabila de mediu NTFY_TOPIC cu același nume — scriptul trimite notificarea acolo.
     Linux/Mac:  export NTFY_TOPIC="numele-tau-secret"
     Windows:    setx NTFY_TOPIC "numele-tau-secret"
     GitHub Actions: secretul NTFY_TOPIC (vezi .github/workflows/alerts.yml).

VERIFICĂ TICKERELE: acest script folosește "TLV.RO" pentru Yahoo Finance. Dacă la
rulare apare eroare sau date lipsă, verifică manual pe finance.yahoo.com dacă
simbolul corect e TLV.RO, TLV.BSE sau altul — sufixele Yahoo pentru BVB nu sunt
mereu consistente. Pentru PTNEGETF, dacă Yahoo Finance nu are date, va trebui
o sursă alternativă (ex. export manual din platforma brokerului tău).
"""

import os

import yfinance as yf
import requests
import pandas as pd
from datetime import datetime

# ── CONFIGURARE ──────────────────────────────────────────────────────────
NTFY_TOPIC = os.environ.get("NTFY_TOPIC", "").strip()

SIMBOLURI = {
    "TLV.RO": {
        "nume": "Banca Transilvania (TLV)",
        "prag_drawdown_procent": 15,   # alertă dacă scade >15% de la maximul pe 12 luni
        "prag_zilnic_procent": 5,      # alertă dacă scade >5% într-o singură zi
    },
    "PTENGETF.RO": {
        "nume": "ETF Energie Patria-Tradeville (PTNEGETF)",
        "prag_drawdown_procent": 10,   # alertă dacă scade >10% de la maximul pe 12 luni
        "prag_zilnic_procent": 3,      # alertă dacă scade >3% într-o singură zi
    },
}
# ─────────────────────────────────────────────────────────────────────────

def verifica_simbol(simbol, cfg, istoric=None):
    if istoric is None:
        istoric = yf.download(simbol, period="2y", interval="1d", progress=False)

    try:
        close = istoric["Close"]
        if isinstance(close, pd.DataFrame):
            close = close.iloc[:, 0]
        close = close.dropna()

        if len(close) < 2:
            return [
                f"⚠️ Nu am putut obține suficiente date pentru {cfg['nume']} ({simbol}). "
                f"Verifică manual simbolul pe Yahoo Finance."
            ]

        pret_curent = float(close.iloc[-1])
        pret_anterior = float(close.iloc[-2])
        close_12luni = close[close.index >= close.index.max() - pd.Timedelta(days=365)]
        maxim_12luni = float(close_12luni.max())
        zile_media = min(200, len(close))
        media_mobila = float(close.tail(zile_media).mean())

        drawdown_procent = (maxim_12luni - pret_curent) / maxim_12luni * 100
        variatie_zilnica_procent = (pret_curent - pret_anterior) / pret_anterior * 100

        sub_media_mobila = pret_curent < media_mobila
        drawdown_depasit = drawdown_procent >= cfg["prag_drawdown_procent"]
        scadere_brusca = variatie_zilnica_procent <= -cfg["prag_zilnic_procent"]
        mesaje_alerta = []

        if drawdown_depasit and sub_media_mobila:
            mesaje_alerta.append(
                f"🔴 {cfg['nume']}: preț {pret_curent:.2f} RON, "
                f"-{drawdown_procent:.1f}% față de maximul pe 12 luni ({maxim_12luni:.2f} RON) "
                f"și sub media pe {zile_media} zile ({media_mobila:.2f} RON). "
                "Condiție de cumpărare îndeplinită."
            )

        if scadere_brusca:
            mesaje_alerta.append(
                f"⚡ {cfg['nume']}: scădere bruscă de {variatie_zilnica_procent:.1f}% "
                f"într-o zi (preț curent {pret_curent:.2f} RON)."
            )

        return mesaje_alerta
    except Exception as eroare:
        return [f"⚠️ Eroare la verificarea {cfg['nume']} ({simbol}): {eroare}"]


def trimite_notificare(mesaje_alerta):
    if not mesaje_alerta:
        print(f"[{datetime.now().strftime('%d.%m.%Y %H:%M')}] Nicio condiție de alertă îndeplinită.")
        return

    text_final = "\n\n".join(mesaje_alerta)
    if not NTFY_TOPIC:
        print("NTFY_TOPIC nu este setat — afișez alerta fără să trimit notificare:\n" + text_final)
        return

    raspuns = requests.post(
        f"https://ntfy.sh/{NTFY_TOPIC}",
        data=text_final.encode("utf-8"),
        headers={
            "Title": "Alertă bursă TLV / PTNEGETF".encode("utf-8"),
            "Priority": "high",
            "Tags": "chart_with_downwards_trend",
        },
        timeout=10,
    )
    if raspuns.status_code != 200:
        print(f"Eroare la trimiterea notificării ntfy: {raspuns.text}")
    else:
        print("Notificare push trimisă.")


def main():
    mesaje_alerta = []
    for simbol, cfg in SIMBOLURI.items():
        mesaje_alerta.extend(verifica_simbol(simbol, cfg))
    trimite_notificare(mesaje_alerta)


if __name__ == "__main__":
    main()


# ─────────────────────────────────────────────────────────────────────────
# CUM PROGRAMEZI RULAREA AUTOMATĂ LA 15-30 MIN, ÎN ORELE DE TRANZACȚIONARE:
#
# LINUX / MAC (cron) — rulează în fiecare 15 min, luni-vineri, 10:00-18:00:
#   1. Deschide terminalul de cron:  crontab -e
#   2. Adaugă linia (ajustează calea către fișier și către python3):
#      */15 10-18 * * 1-5 /usr/bin/python3 /calea/catre/alerta_bursa.py
#
# WINDOWS (Task Scheduler):
#   1. Deschide "Task Scheduler" -> "Create Task"
#   2. Trigger: "Daily", repeat every 15 minutes, între orele 10:00-18:00
#   3. Action: "Start a program" -> python.exe, argument: calea către alerta_bursa.py
#
# ALTERNATIVĂ FĂRĂ SERVER PROPRIU: AWS Lambda + EventBridge (schedule rate),
# util dacă nu vrei să ții un PC pornit permanent.
# ─────────────────────────────────────────────────────────────────────────