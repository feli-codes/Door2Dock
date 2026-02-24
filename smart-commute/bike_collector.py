#!/usr/bin/env python3
"""
Smart-Commute Predictor – Bike Data Collector
Sammelt die Verfügbarkeit der Santander Cycles Stationen
rund um Imperial College South Kensington.

Usage:
    python bike_collector.py              # Dauerbetrieb jede Minute (lokal)
    python bike_collector.py --once       # Einmal sammeln, dann exit
    python bike_collector.py --burst      # 5x sammeln (jede Min), dann exit (GitHub Actions)
    python bike_collector.py --discover   # Stationen im Umkreis anzeigen
    python bike_collector.py --stats      # Daten-Statistiken anzeigen
"""

import requests
import sqlite3
import time
import sys
import os
import math
from datetime import datetime, timezone

# ============================================================
# KONFIGURATION
# ============================================================

IMPERIAL_LAT = 51.4988
IMPERIAL_LON = -0.1749
SEARCH_RADIUS_M = 800
POLL_INTERVAL = 60  # 1 Minute

# DB-Pfad: data/commute.db (relativ zum Skript-Ordner)
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(SCRIPT_DIR, "data")
DB_PATH = os.path.join(DATA_DIR, "commute.db")

TFL_BIKEPOINT_URL = "https://api.tfl.gov.uk/BikePoint"

# ============================================================
# ZEITZONE
# ============================================================

def get_london_now():
    """Gibt die aktuelle London-Zeit zurück."""
    try:
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo("Europe/London"))
    except ImportError:
        return datetime.now(timezone.utc)

# ============================================================
# DATENBANK
# ============================================================

def init_db():
    """Erstellt data-Ordner, Datenbank und Tabellen."""
    os.makedirs(DATA_DIR, exist_ok=True)

    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS bike_availability (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp       TEXT NOT NULL,
            station_id      TEXT NOT NULL,
            station_name    TEXT,
            available_bikes INTEGER,
            standard_bikes  INTEGER,
            ebikes          INTEGER,
            empty_docks     INTEGER,
            total_docks     INTEGER,
            latitude        REAL,
            longitude       REAL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS monitored_stations (
            station_id      TEXT PRIMARY KEY,
            station_name    TEXT,
            latitude        REAL,
            longitude       REAL,
            distance_m      REAL
        )
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_bike_timestamp 
        ON bike_availability(timestamp)
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_bike_station 
        ON bike_availability(station_id)
    """)
    conn.commit()
    conn.close()
    print(f"[init] DB ready: {DB_PATH}")
    print(f"[init] DB exists: {os.path.exists(DB_PATH)}")
    print(f"[init] DB size: {os.path.getsize(DB_PATH)} bytes")

# ============================================================
# HILFSFUNKTIONEN
# ============================================================

def haversine(lat1, lon1, lat2, lon2):
    """Berechnet Distanz zwischen zwei Koordinaten in Metern."""
    R = 6371000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = (math.sin(dphi / 2) ** 2
         + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2)
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

def parse_properties(additional_properties):
    """Extrahiert relevante Felder aus additionalProperties."""
    props = {}
    for p in additional_properties:
        key = p.get("key", "")
        val = p.get("value", "")
        if key in ("NbBikes", "NbEBikes", "NbEmptyDocks", "NbDocks",
                    "NbStandardBikes", "Installed", "Locked"):
            props[key] = val
    return props

def fetch_all_stations():
    """Holt alle BikePoints von der TfL API (1 Request)."""
    print("[fetch] Calling TfL API...")
    resp = requests.get(TFL_BIKEPOINT_URL, timeout=30)
    resp.raise_for_status()
    stations = resp.json()
    print(f"[fetch] Got {len(stations)} stations from API")
    return stations

# ============================================================
# STATION DISCOVERY
# ============================================================

def discover_stations():
    """Findet alle Stationen im Umkreis von Imperial College."""
    print(f"\n🔍 Suche Stationen im Umkreis von {SEARCH_RADIUS_M}m "
          f"um Imperial College...")

    try:
        all_stations = fetch_all_stations()
    except requests.RequestException as e:
        print(f"❌ API-Fehler: {e}")
        return []

    nearby = []
    for station in all_stations:
        lat = station.get("lat", 0)
        lon = station.get("lon", 0)
        dist = haversine(IMPERIAL_LAT, IMPERIAL_LON, lat, lon)

        if dist <= SEARCH_RADIUS_M:
            props = parse_properties(
                station.get("additionalProperties", []))
            nearby.append({
                "station_id": station["id"],
                "station_name": station["commonName"],
                "latitude": lat,
                "longitude": lon,
                "distance_m": round(dist),
                "total_docks": props.get("NbDocks", "?"),
                "available_bikes": props.get("NbBikes", "?"),
                "ebikes": props.get("NbEBikes", "?"),
            })

    nearby.sort(key=lambda x: x["distance_m"])

    conn = sqlite3.connect(DB_PATH)
    for s in nearby:
        conn.execute("""
            INSERT OR REPLACE INTO monitored_stations 
            (station_id, station_name, latitude, longitude, distance_m)
            VALUES (?, ?, ?, ?, ?)
        """, (s["station_id"], s["station_name"], s["latitude"],
              s["longitude"], s["distance_m"]))
    conn.commit()
    conn.close()

    print(f"\n📍 {len(nearby)} Stationen gefunden:\n")
    for i, s in enumerate(nearby, 1):
        print(f"  {i}. {s['station_name']} ({s['distance_m']}m) "
              f"– {s['total_docks']} docks, "
              f"{s['available_bikes']} bikes, "
              f"{s['ebikes']} e-bikes")
    print()
    return nearby

# ============================================================
# DATENSAMMLUNG
# ============================================================

def get_monitored_station_ids():
    """Lädt die Station-IDs aus der DB."""
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute(
        "SELECT station_id FROM monitored_stations").fetchall()
    conn.close()
    return [r[0] for r in rows]

def collect_once():
    """Führt eine einzelne Datensammlung durch."""
    station_ids = get_monitored_station_ids()

    if not station_ids:
        print("[collect] Keine Stationen – starte Discovery...")
        discover_stations()
        station_ids = get_monitored_station_ids()
        if not station_ids:
            print("[collect] ❌ Konnte keine Stationen finden!")
            return "error"

    now_utc = datetime.now(timezone.utc).isoformat()
    now_london = get_london_now()
    collected = 0

    try:
        all_stations = fetch_all_stations()
    except requests.RequestException as e:
        print(f"[collect] ❌ API-Fehler: {e}")
        return "error"

    station_map = {s["id"]: s for s in all_stations}

    conn = sqlite3.connect(DB_PATH)
    for sid in station_ids:
        station = station_map.get(sid)
        if not station:
            continue

        props = parse_properties(
            station.get("additionalProperties", []))

        if (props.get("Installed") == "false"
                or props.get("Locked") == "true"):
            continue

        conn.execute("""
            INSERT INTO bike_availability 
            (timestamp, station_id, station_name, available_bikes,
             standard_bikes, ebikes, empty_docks, total_docks, 
             latitude, longitude)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            now_utc,
            station["id"],
            station["commonName"],
            int(props.get("NbBikes", 0)),
            int(props.get("NbStandardBikes", 0)),
            int(props.get("NbEBikes", 0)),
            int(props.get("NbEmptyDocks", 0)),
            int(props.get("NbDocks", 0)),
            station["lat"],
            station["lon"],
        ))
        collected += 1

    conn.commit()
    conn.close()

    total = sqlite3.connect(DB_PATH).execute(
        "SELECT COUNT(*) FROM bike_availability").fetchone()[0]

    print(f"[collect] ✅ {now_london.strftime('%H:%M:%S')} London – "
          f"{collected} Stationen gespeichert "
          f"(total: {total} Einträge in DB)")
    return "ok"

# ============================================================
# LAUFMODI
# ============================================================

def run_continuous():
    """Dauerläufer – für lokalen Betrieb."""
    print("\n" + "=" * 60)
    print("🚲 Smart-Commute Bike Collector")
    print(f"   Intervall:   {POLL_INTERVAL} Sekunden")
    print(f"   Modus:       Dauerbetrieb (24/7)")
    print(f"   Datenbank:   {DB_PATH}")
    print(f"   Stoppen:     Ctrl+C")
    print("=" * 60 + "\n")

    collect_once()

    try:
        while True:
            time.sleep(POLL_INTERVAL)
            collect_once()
    except KeyboardInterrupt:
        print("\n\n👋 Collector gestoppt.")
        show_stats()

def run_burst(cycles=5):
    """Burst-Modus: sammelt mehrfach im Minutentakt, dann exit.
    Für GitHub Actions (Cron min = 5 Min, intern jede Minute)."""
    print(f"[burst] Starte {cycles} Sammelzyklen im Minutentakt...")

    for i in range(cycles):
        print(f"\n[burst] === Zyklus {i + 1}/{cycles} ===")
        collect_once()
        if i < cycles - 1:
            print(f"[burst] Warte 60 Sekunden...")
            time.sleep(60)

    print(f"\n[burst] ✅ Fertig – {cycles} Zyklen abgeschlossen")

# ============================================================
# STATISTIKEN
# ============================================================

def show_stats():
    """Zeigt eine Übersicht der gesammelten Daten."""
    if not os.path.exists(DB_PATH):
        print("\n📊 Keine Datenbank gefunden.")
        return

    conn = sqlite3.connect(DB_PATH)

    total = conn.execute(
        "SELECT COUNT(*) FROM bike_availability").fetchone()[0]
    if total == 0:
        print("\n📊 Noch keine Daten gesammelt.")
        conn.close()
        return

    stations = conn.execute(
        "SELECT COUNT(DISTINCT station_id) FROM bike_availability"
    ).fetchone()[0]
    first = conn.execute(
        "SELECT MIN(timestamp) FROM bike_availability").fetchone()[0]
    last = conn.execute(
        "SELECT MAX(timestamp) FROM bike_availability").fetchone()[0]

    try:
        t1 = datetime.fromisoformat(first.replace("Z", "+00:00"))
        t2 = datetime.fromisoformat(last.replace("Z", "+00:00"))
        days = (t2 - t1).days + 1
    except Exception:
        days = "?"

    print(f"\n📊 Daten-Statistiken:")
    print(f"   Datenpunkte:    {total:,}")
    print(f"   Stationen:      {stations}")
    print(f"   Sammeldauer:    {days} Tag(e)")
    print(f"   Erster Eintrag: {first[:19] if first else '-'} UTC")
    print(f"   Letzter Eintrag:{last[:19] if last else '-'} UTC")
    print(f"   DB-Größe:       {os.path.getsize(DB_PATH):,} bytes")

    print(f"\n   {'Station':<42} {'Einträge':>8}  "
          f"{'Ø Bikes':>7}  {'Ø E-Bikes':>9}")
    print("   " + "-" * 72)
    rows = conn.execute("""
        SELECT station_name, COUNT(*), 
               ROUND(AVG(available_bikes), 1),
               ROUND(AVG(ebikes), 1)
        FROM bike_availability
        GROUP BY station_id ORDER BY station_name
    """).fetchall()
    for name, count, avg_bikes, avg_ebikes in rows:
        print(f"   {name:<42} {count:>8}  "
              f"{avg_bikes:>7}  {avg_ebikes:>9}")

    conn.close()
    print()

# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":
    print(f"[main] Python {sys.version}")
    print(f"[main] Working dir: {os.getcwd()}")
    print(f"[main] Script dir:  {SCRIPT_DIR}")
    print(f"[main] DB path:     {DB_PATH}")
    print(f"[main] Args:        {sys.argv[1:]}")

    init_db()

    if "--discover" in sys.argv:
        discover_stations()
    elif "--stats" in sys.argv:
        show_stats()
    elif "--once" in sys.argv:
        collect_once()
    elif "--burst" in sys.argv:
        run_burst(cycles=5)
    else:
        run_continuous()
