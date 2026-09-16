# controlling_mcp_server
FastMCP-Server mit PostgreSQL-Backend für Controlling-Anwendungsfälle – Soll/Ist-Abweichungsanalyse mit automatischer Ursachenzuordnung, Forecast und Drill-Down auf Einzelbuchungen.

Dieses Repository zeigt anhand einer stark vereinfachten, an SAP-CO angelehnten Datenstruktur (Kostenstelle, Kostenart, Plan- und Istwerte), wie sich klassische Controlling-Prozesse per MCP-Tools für KI-Clients wie Claude Desktop oder Claude Code zugänglich machen lassen. Der Server stellt reine Werkzeuge bereit (kein eigenständiger Agent) – die Entscheidungslogik übernimmt der jeweils verbundene KI-Client.

## 1. PostgreSQL-Datenbank anlegen

```sql
CREATE DATABASE controlling_demo;
```

Danach das Schema samt Beispieldaten einspielen:

```bash
psql -U postgres -d controlling_demo -f schema.sql
```

**Windows-Hinweis (bekannter Stolperstein):** Falls `psycopg2.connect()`
mit einem Encoding-Fehler abbricht, in `postgresql.conf` (unter
`C:\Program Files\PostgreSQL\<version>\data\`) folgende Zeile setzen und
den PostgreSQL-Dienst neu starten:

```
lc_messages = 'en_US.UTF-8'
```

## 2. Python-Umgebung einrichten

```bash
python -m venv .venv
.venv\Scripts\activate        # Windows
pip install -r requirements.txt
```

## 3. Verbindungsdaten setzen

Der Server liest die Verbindungsdaten aus Umgebungsvariablen (alle als
String, siehe unten):

| Variable      | Default             |
|---------------|---------------------|
| `DB_HOST`     | `localhost`         |
| `DB_PORT`     | `5432`              |
| `DB_NAME`     | `controlling_demo`  |
| `DB_USER`     | `postgres`          |
| `DB_PASSWORD` | *(leer)*            |

## 4. Server lokal testen (ohne Claude)

```bash
python server.py
```

Der Server läuft dann über stdio und wartet auf einen MCP-Client. Zum
schnellen Debuggen eignet sich auch der MCP Inspector:

```bash
npx @modelcontextprotocol/inspector python server.py
```

## 5. Mit Claude Code verbinden

```bash
claude mcp add --transport stdio controlling-mcp-server ^
  --env DB_PASSWORD=dein-passwort ^
  -- python C:\pfad\zu\controlling_mcp_server\server.py
```

Status prüfen:

```bash
claude mcp list
```

## 6. Alternativ: mit Claude Desktop verbinden

In `claude_desktop_config.json` ergänzen (alle Werte als String!):

```json
{
  "mcpServers": {
    "controlling-mcp-server": {
      "command": "python",
      "args": ["C:\\pfad\\zu\\controlling_mcp_server\\server.py"],
      "env": {
        "DB_HOST": "localhost",
        "DB_PORT": "5432",
        "DB_NAME": "controlling_demo",
        "DB_USER": "postgres",
        "DB_PASSWORD": "dein-passwort"
      }
    }
  }
}
```

## 7. Agentisches Verhalten ausprobieren

Sobald der Server verbunden ist, im Chat z. B. eintippen:

> "Prüfe die Kostenstellen für August 2026 auf Abweichungen und erkläre
> mir die größte Abweichung samt Ursache."

Ein KI-Client verkettet dafür typischerweise selbstständig:

1. `list_kostenstellen` – Übersicht verschaffen
2. `abweichungsanalyse(periode="2026-08")` – alle Abweichungen ermitteln
3. `abweichung_erklaeren(kostenstelle=..., periode="2026-08")` – für die
   größte Abweichung die Treiber benennen
4. optional `buchungsdetails(...)` – die auffälligen Einzelbuchungen zeigen
5. optional `rollierender_forecast(...)` – Ausblick auf die Folgeperiode

Die eingebaute Beispiel-Auffälligkeit: Kostenstelle **4200 (Produktion
Werk 1)** liegt bei Kostenart **610000 (Materialkosten)** im August 2026
wegen eines simulierten Rohstoffpreisanstiegs deutlich über Plan – daran
lässt sich die automatische Ursachenzuordnung gut demonstrieren.

## Enthaltene Tools

| Tool | Zweck |
|---|---|
| `list_kostenstellen` | Stammdaten der Kostenstellen |
| `abweichungsanalyse(periode, kostenstelle=None)` | Soll/Ist je Kostenstelle & Kostenart |
| `abweichung_erklaeren(kostenstelle, periode)` | Haupttreiber + Erklärtext |
| `rollierender_forecast(kostenstelle, kostenart)` | einfache Trend-Prognose |
| `buchungsdetails(kostenstelle, kostenart, periode)` | Einzelpostenanzeige |

## Nächste Ausbaustufen (Ideen)

- Weitere Perioden/Kostenstellen ergänzen, um Trends über mehr Monate zu zeigen.
- Schwellenwert-Parameter einbauen (z. B. nur Abweichungen > 10 % zurückgeben).
- Zweiten Server für Rechnungsprüfung/Anomalieerkennung ergänzen und beide
  Server im selben Client kombinieren.
- Eigenständigen Agenten (z. B. mit dem Claude Agent SDK) obendrauf bauen,
  der diese Tools automatisiert und zeitgesteuert (Task Scheduler/Cron)
  nutzt, statt nur im Chat aufgerufen zu werden.
