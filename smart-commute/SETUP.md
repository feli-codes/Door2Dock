# 🚲 Smart-Commute – GitHub Actions Setup

## So funktioniert es

GitHub Actions führt alle **5 Minuten** einen Workflow aus.  
Jeder Workflow sammelt intern **5× im Minutentakt** Daten → effektiv **jede Minute** ein Datenpunkt.  
Die SQLite-Datenbank wird nach jedem Lauf zurück ins Repo committed.

```
Cron (alle 5 Min) → python --burst → Min 0, 1, 2, 3, 4 → git commit DB → fertig
```

---

## Einrichtung (10 Minuten)

### Schritt 1: Neues GitHub Repo erstellen

1. [github.com/new](https://github.com/new)
2. **Repository name**: `smart-commute`
3. **⚠️ Public** auswählen → unbegrenzte Actions-Minuten!
4. **Haken setzen** bei "Add a README file"
5. **Create repository**

### Schritt 2: Dateien hochladen

1. Im Repo auf **Add file → Upload files**
2. Lade hoch:
   - `bike_collector.py`
   - `requirements.txt`
   - `.gitignore` (Finder: `Cmd+Shift+.` um versteckte Dateien zu sehen)
3. **Commit changes**

### Schritt 3: Workflow-Datei erstellen

1. Im Repo auf **Add file → Create new file**
2. Als Dateinamen **genau** eingeben: `.github/workflows/collect.yml`
   (GitHub erstellt die Ordner automatisch)
3. Inhalt der `collect.yml` Datei reinkopieren
4. **Commit changes**

### Schritt 4: Workflow-Berechtigung setzen

**⚠️ Das ist der wichtigste Schritt – ohne das kann der Bot nicht committen!**

1. **Settings** → **Actions** → **General**
2. Runterscrollen zu **"Workflow permissions"**
3. **"Read and write permissions"** auswählen
4. **Save**

### Schritt 5: Testen

1. **Actions** Tab → **"Collect Bike Data"** links auswählen
2. **"Run workflow"** → **"Run workflow"** (grüner Button)
3. Warte ~5 Minuten (5 Zyklen à 1 Minute)
4. Der Job sollte **grün** ✅ werden
5. Zurück zu **Code** → `data/commute.db` sollte erscheinen!

### Schritt 6: Fertig! 🎉

Ab jetzt läuft alles automatisch. Laptop aus, schlafen, egal.

---

## Daten herunterladen

### Option A: Direkt von GitHub
Im Repo → `data/` → `commute.db` → **Download raw file**

### Option B: Per Terminal
```bash
git clone https://github.com/DEIN-USERNAME/smart-commute.git
cd smart-commute
python bike_collector.py --stats
```

### Option C: DB direkt abfragen
```bash
sqlite3 data/commute.db "SELECT COUNT(*) FROM bike_availability;"
sqlite3 data/commute.db "SELECT * FROM bike_availability ORDER BY timestamp DESC LIMIT 20;"
```

---

## Lokaler Betrieb (Alternative zu GitHub Actions)

Falls du das Skript auch lokal laufen lassen willst:

```bash
pip install requests

# Dauerbetrieb (jede Minute, Ctrl+C zum Stoppen)
python bike_collector.py

# Auf Mac: verhindert Sleep
caffeinate -i python bike_collector.py
```

---

## Troubleshooting

**Job läuft, aber keine DB im Repo?**
→ Schritt 4 prüfen: Workflow permissions auf "Read and write" gesetzt?

**Job ist rot / Fehler?**
→ Actions Tab → auf den Lauf klicken → "collect" → Logs lesen.  
  Häufigste Ursache: TfL API kurz offline → nächster Lauf klappt meist.

**Cron triggert nicht pünktlich?**
→ Normal. GitHub Actions hat bis zu 5-15 Min Verzögerung bei Cron-Jobs.  
  Die Daten kommen trotzdem – nur nicht sekundengenau.

**Wie stoppe ich die Sammlung?**
→ Actions Tab → "Collect Bike Data" → "⋯" oben rechts → **Disable workflow**

---

## Datenmengen

| Zeitraum  | Datenpunkte (ca.)       | DB-Größe     |
|-----------|------------------------:|-------------:|
| 1 Tag     | ~12 Stationen × 1440   | ~2 MB        |
| 1 Woche   | ~120.000                | ~15 MB       |
| 3 Wochen  | ~360.000                | ~45 MB       |

GitHub erlaubt Repos bis 1 GB – kein Problem.
