import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import pyodbc

base = r'C:\Users\kurt_\Musikprogramm'

def connect(db):
    conn_str = f'DRIVER={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={base}\\{db};'
    return pyodbc.connect(conn_str)

conn = connect('rw_Aehnlichkeiten.mdb')
cur = conn.cursor()

# Check what Scan_Nr values exist for Radio Würmchen KI
cur.execute("SELECT Scan_Nr, Sender, Startzeit FROM Tab_Scans WHERE Sender = 'Radio Würmchen KI'")
rw_scans = cur.fetchall()
print(f'Radio Würmchen KI entries in Tab_Scans: {len(rw_scans)}')
for row in rw_scans:
    print(f'  Scan_Nr={row[0]}, Sender={row[1]}, Startzeit={row[2]}')

# Check Tab_Scan entries for those Scan_Nr values
if rw_scans:
    scan_nrs = [str(row[0]) for row in rw_scans]
    placeholders = ','.join(scan_nrs)
    cur.execute(f"SELECT COUNT(*) FROM Tab_Scan WHERE Scan_Nr IN ({placeholders})")
    count = cur.fetchone()[0]
    print(f'\nTab_Scan entries for Radio Würmchen KI Scan_Nrs: {count}')
    
    # Show sample
    cur.execute(f"SELECT TOP 10 Scan_Nr, Titelnr, Zeit, Sender FROM Tab_Scan WHERE Scan_Nr IN ({placeholders})")
    rows = cur.fetchall()
    for row in rows:
        print(f'  Scan_Nr={row[0]}, Titelnr={row[1]}, Zeit={row[2]}, Sender={row[3]}')

# Also check: how many Tab_Scan entries have Sender = 95 (Kurt)?
cur.execute("SELECT COUNT(*) FROM Tab_Scan WHERE Sender = 95")
kurt_scans = cur.fetchone()[0]
print(f'\nTab_Scan entries with Sender=95 (Kurt): {kurt_scans}')

# And which Scan_Nr values does Kurt have?
cur.execute("SELECT DISTINCT Scan_Nr FROM Tab_Scan WHERE Sender = 95")
kurt_scan_nrs = [row[0] for row in cur.fetchall()]
print(f'Distinct Scan_Nrs for Kurt: {len(kurt_scan_nrs)}')

# Check which of those are Radio Würmchen KI
if rw_scans:
    rw_scan_nrs = set(scan_nrs)
    kurt_rw = [nr for nr in kurt_scan_nrs if str(nr) in rw_scan_nrs]
    print(f'Kurt Scan_Nrs that are Radio Würmchen KI: {len(kurt_rw)}')

conn.close()
