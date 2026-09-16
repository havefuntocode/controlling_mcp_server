"""
Controlling-Agent Demo -- FastMCP-Server auf PostgreSQL-Basis.

Zeigt anhand einer stark vereinfachten, an SAP-CO angelehnten Datenstruktur
(Kostenstelle / Kostenart / Planwerte / Istbuchungen), wie ein KI-Agent im
Controlling nicht nur einzelne Werte abfragt (klassisches MCP-CRUD-Tool),
sondern eine mehrstufige Analyseaufgabe eigenstaendig durchfuehrt:

    1. list_kostenstellen        -- Stammdaten abrufen
    2. abweichungsanalyse        -- Soll/Ist je Kostenstelle & Kostenart
    3. abweichung_erklaeren      -- Haupttreiber der Abweichung benennen
    4. rollierender_forecast     -- einfache Prognose auf Basis Ist-Trend
    5. buchungsdetails           -- Einzelpostenanzeige (Drill-Down)

Ein KI-Agent (z. B. in Claude Desktop oder Claude Code) kann diese Tools
selbststaendig verketten: z. B. erst abweichungsanalyse() aufrufen, dann
fuer die groesste Abweichung automatisch abweichung_erklaeren() nachziehen
und das Ergebnis in eigenen Worten zusammenfassen -- genau das entspricht
"Beispiel 1: Abweichungsanalyse mit automatischer Ursachenzuordnung" aus
dem begleitenden Evaluierungs-Dokument.

WICHTIG (Windows-Setup, siehe eigene Erfahrungswerte):
  - PostgreSQL: lc_messages = 'en_US.UTF-8' in postgresql.conf setzen und
    den Dienst neu starten, sonst schlaegt psycopg2.connect() bei
    deutscher Locale mit einem Encoding-Fehler fehl.
  - Alle Werte in claude_desktop_config.json (env-Block) muessen Strings
    sein, z. B. "DB_PORT": "5432" -- Konvertierung erfolgt unten in Python.
  - Docstrings der @mcp.tool()-Funktionen bewusst ohne Umlaute geschrieben,
    um UnicodeDecodeError bei der Tool-Registrierung zu vermeiden.
"""

import os
from datetime import date

import psycopg2
import psycopg2.extras
from fastmcp import FastMCP

# ------------------------------------------------------------------
# Datenbankverbindung
# ------------------------------------------------------------------
DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": int(os.getenv("DB_PORT", "5432")),
    "dbname": os.getenv("DB_NAME", "controlling_demo"),
    "user": os.getenv("DB_USER", "postgres"),
    "password": os.getenv("DB_PASSWORD", ""),
    "options": "-c client_encoding=UTF8",
}


def get_connection():
    return psycopg2.connect(**DB_CONFIG)


mcp = FastMCP("controlling-agent-demo")


# ------------------------------------------------------------------
# Tool 1: Stammdaten
# ------------------------------------------------------------------
@mcp.tool()
def list_kostenstellen() -> list[dict]:
    """
    Liefert alle Kostenstellen mit Bezeichnung und Verantwortlichem zurueck.
    Nuetzlich als erster Schritt, um zu sehen, welche Kostenstellen fuer
    eine Abweichungsanalyse zur Verfuegung stehen.
    """
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT kostenstelle, bezeichnung, verantwortlicher "
                "FROM kostenstelle ORDER BY kostenstelle"
            )
            return [dict(row) for row in cur.fetchall()]


# ------------------------------------------------------------------
# Tool 2: Abweichungsanalyse (Soll/Ist)
# ------------------------------------------------------------------
@mcp.tool()
def abweichungsanalyse(periode: str, kostenstelle: str | None = None) -> list[dict]:
    """
    Vergleicht Plan- und Istwerte fuer eine Periode (Format 'YYYY-MM') je
    Kostenstelle und Kostenart und liefert die Abweichung in absoluten
    Werten und in Prozent zurueck, absteigend nach absoluter Abweichung
    sortiert. Optional kann auf eine einzelne kostenstelle gefiltert
    werden. Dies ist der erste Schritt einer klassischen Soll-Ist-
    Abweichungsanalyse im Controlling.
    """
    query = """
        SELECT
            p.kostenstelle,
            k.bezeichnung AS kostenstelle_bezeichnung,
            p.kostenart,
            ka.bezeichnung AS kostenart_bezeichnung,
            p.periode,
            p.planbetrag,
            COALESCE(SUM(i.betrag), 0) AS istbetrag
        FROM planwerte p
        JOIN kostenstelle k ON k.kostenstelle = p.kostenstelle
        JOIN kostenart ka ON ka.kostenart = p.kostenart
        LEFT JOIN istbuchungen i
            ON i.kostenstelle = p.kostenstelle
           AND i.kostenart = p.kostenart
           AND i.periode = p.periode
        WHERE p.periode = %(periode)s
          AND (%(kostenstelle)s IS NULL OR p.kostenstelle = %(kostenstelle)s)
        GROUP BY p.kostenstelle, k.bezeichnung, p.kostenart, ka.bezeichnung,
                 p.periode, p.planbetrag
    """
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(query, {"periode": periode, "kostenstelle": kostenstelle})
            rows = [dict(row) for row in cur.fetchall()]

    ergebnis = []
    for row in rows:
        plan = float(row["planbetrag"])
        ist = float(row["istbetrag"])
        abweichung = ist - plan
        abweichung_prozent = (abweichung / plan * 100) if plan else 0.0
        ergebnis.append(
            {
                "kostenstelle": row["kostenstelle"],
                "kostenstelle_bezeichnung": row["kostenstelle_bezeichnung"],
                "kostenart": row["kostenart"],
                "kostenart_bezeichnung": row["kostenart_bezeichnung"],
                "periode": row["periode"],
                "plan": round(plan, 2),
                "ist": round(ist, 2),
                "abweichung": round(abweichung, 2),
                "abweichung_prozent": round(abweichung_prozent, 1),
            }
        )

    ergebnis.sort(key=lambda r: abs(r["abweichung"]), reverse=True)
    return ergebnis


# ------------------------------------------------------------------
# Tool 3: Abweichung erklaeren (Treiberanalyse)
# ------------------------------------------------------------------
@mcp.tool()
def abweichung_erklaeren(kostenstelle: str, periode: str) -> dict:
    """
    Analysiert die Abweichung einer Kostenstelle in einer Periode und
    benennt die Kostenart(en), die den groessten Beitrag zur Abweichung
    leisten. Liefert zusaetzlich einen kurzen Erklaerungstext in
    natuerlicher Sprache zurueck -- vergleichbar mit der automatischen
    Ursachenzuordnung, die ein KI-Agent im Controlling uebernehmen kann.
    """
    positionen = abweichungsanalyse(periode=periode, kostenstelle=kostenstelle)
    if not positionen:
        return {
            "kostenstelle": kostenstelle,
            "periode": periode,
            "treiber": [],
            "erklaerung": f"Keine Daten fuer Kostenstelle {kostenstelle} in {periode} gefunden.",
        }

    gesamt_abweichung = sum(p["abweichung"] for p in positionen)
    top_treiber = positionen[:2]  # die zwei staerksten Einzeltreiber

    saetze = []
    richtung = "ueber" if gesamt_abweichung > 0 else "unter"
    saetze.append(
        f"Kostenstelle {kostenstelle} liegt in {periode} insgesamt um "
        f"{abs(gesamt_abweichung):,.2f} EUR {richtung} Plan."
    )
    for t in top_treiber:
        if t["abweichung"] == 0:
            continue
        richtung_t = "ueberschreitet" if t["abweichung"] > 0 else "unterschreitet"
        saetze.append(
            f"Hauptreiber: {t['kostenart_bezeichnung']} ({t['kostenart']}) "
            f"{richtung_t} den Plan um {abs(t['abweichung']):,.2f} EUR "
            f"({t['abweichung_prozent']:+.1f} %)."
        )

    return {
        "kostenstelle": kostenstelle,
        "periode": periode,
        "gesamtabweichung": round(gesamt_abweichung, 2),
        "treiber": top_treiber,
        "erklaerung": " ".join(saetze),
    }


# ------------------------------------------------------------------
# Tool 4: Rollierender Forecast
# ------------------------------------------------------------------
@mcp.tool()
def rollierender_forecast(kostenstelle: str, kostenart: str) -> dict:
    """
    Berechnet auf Basis der letzten verfuegbaren Istwerte einen einfachen
    rollierenden Forecast (gleitender Durchschnitt plus linearer Trend)
    fuer die naechste Periode. Dient als vereinfachtes Beispiel fuer eine
    kontinuierlich aktualisierte Prognose, wie sie ein KI-Agent im
    Controlling automatisiert erstellen koennte. Ersetzt keine
    vollstaendige Planungsrechnung.
    """
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                SELECT periode, SUM(betrag) AS istbetrag
                FROM istbuchungen
                WHERE kostenstelle = %(kostenstelle)s AND kostenart = %(kostenart)s
                GROUP BY periode
                ORDER BY periode
                """,
                {"kostenstelle": kostenstelle, "kostenart": kostenart},
            )
            rows = [dict(row) for row in cur.fetchall()]

    if len(rows) < 2:
        return {
            "kostenstelle": kostenstelle,
            "kostenart": kostenart,
            "forecast": None,
            "hinweis": "Nicht genuegend Historie fuer einen Trend-Forecast (mind. 2 Perioden noetig).",
        }

    werte = [float(r["istbetrag"]) for r in rows]
    durchschnitt = sum(werte) / len(werte)
    trend_je_periode = (werte[-1] - werte[0]) / (len(werte) - 1)
    forecast_naechste_periode = werte[-1] + trend_je_periode

    return {
        "kostenstelle": kostenstelle,
        "kostenart": kostenart,
        "historie": rows,
        "durchschnitt": round(durchschnitt, 2),
        "trend_je_periode": round(trend_je_periode, 2),
        "forecast_naechste_periode": round(forecast_naechste_periode, 2),
    }


# ------------------------------------------------------------------
# Tool 5: Buchungsdetails (Drill-Down)
# ------------------------------------------------------------------
@mcp.tool()
def buchungsdetails(kostenstelle: str, kostenart: str, periode: str) -> list[dict]:
    """
    Liefert die einzelnen Istbuchungen fuer eine Kombination aus
    Kostenstelle, Kostenart und Periode zurueck. Wird typischerweise als
    Drill-Down genutzt, nachdem abweichung_erklaeren() einen Treiber
    identifiziert hat, um die konkreten Buchungen dahinter zu pruefen.
    """
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                SELECT buchungsdatum, betrag, buchungstext
                FROM istbuchungen
                WHERE kostenstelle = %(kostenstelle)s
                  AND kostenart = %(kostenart)s
                  AND periode = %(periode)s
                ORDER BY buchungsdatum
                """,
                {"kostenstelle": kostenstelle, "kostenart": kostenart, "periode": periode},
            )
            return [
                {
                    "buchungsdatum": row["buchungsdatum"].isoformat()
                    if isinstance(row["buchungsdatum"], date)
                    else row["buchungsdatum"],
                    "betrag": float(row["betrag"]),
                    "buchungstext": row["buchungstext"],
                }
                for row in cur.fetchall()
            ]


if __name__ == "__main__":
    mcp.run()
