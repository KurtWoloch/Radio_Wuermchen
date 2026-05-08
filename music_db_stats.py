import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import pyodbc

base = r'C:\Users\kurt_\Musikprogramm'

def connect(db):
    conn_str = f'DRIVER={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={base}\\{db};'
    return pyodbc.connect(conn_str)

# 1. Count titles in Tab_Files
conn = connect('rw_Files2000.mdb')
cur = conn.cursor()
cur.execute('SELECT COUNT(*) FROM Tab_Files')
total_files = cur.fetchone()[0]
conn.close()

# 2. Get Kategorien stats from Tab_Aehnlich
conn = connect('rw_Aehnlichkeiten.mdb')
cur = conn.cursor()
cur.execute('SELECT COUNT(*) FROM Tab_Aehnlich')
total_aehnlich = cur.fetchone()[0]
cur.execute("SELECT COUNT(*) FROM Tab_Aehnlich WHERE Kategorien IS NOT NULL AND Kategorien <> ''")
with_kat = cur.fetchone()[0]
cur.execute("SELECT COUNT(*) FROM Tab_Aehnlich WHERE Kategorien IS NULL OR Kategorien = ''")
without_kat = cur.fetchone()[0]

# Sample Kategorien
cur.execute("SELECT TOP 30 Kategorien FROM Tab_Aehnlich WHERE Kategorien IS NOT NULL AND Kategorien <> ''")
samples = [row[0] for row in cur.fetchall()]

# 3. Count scans
cur.execute('SELECT COUNT(*) FROM Tab_Scan')
total_scans = cur.fetchone()[0]
cur.execute('SELECT Titelnr, COUNT(*) AS cnt FROM Tab_Scan GROUP BY Titelnr')
scanned_titles = len(cur.fetchall())

# Radio Würmchen KI scans
cur.execute("""
    SELECT COUNT(*) FROM Tab_Scan s
    INNER JOIN Tab_Scans sc ON s.Scan_Nr = sc.Scan_Nr
    WHERE sc.Sender = 'Radio Würmchen KI'
""")
rw_scans = cur.fetchone()[0]

cur.execute("""
    SELECT s.Titelnr, COUNT(*) AS cnt FROM Tab_Scan s
    INNER JOIN Tab_Scans sc ON s.Scan_Nr = sc.Scan_Nr
    WHERE sc.Sender = 'Radio Würmchen KI'
    GROUP BY s.Titelnr
""")
rw_titles = len(cur.fetchall())
conn.close()

# 4. Count ratings
conn = connect('rw_bewertung2000.mdb')
cur = conn.cursor()
cur.execute('SELECT COUNT(*) FROM Tab_Wertung_pro_Person')
total_ratings = cur.fetchone()[0]
cur.execute('SELECT COUNT(*) FROM Tab_Wertung_pro_Person WHERE Person_Nr = 95')
kurt_ratings = cur.fetchone()[0]
cur.execute('SELECT COUNT(*) FROM Tab_Wertung_pro_Person WHERE Person_Nr BETWEEN 1440 AND 1454')
show_ratings = cur.fetchone()[0]
conn.close()

print(f'Tab_Files: {total_files} Titel')
print(f'Tab_Aehnlich: {total_aehnlich} Einträge')
print(f'  mit Kategorien: {with_kat}')
print(f'  ohne Kategorien: {without_kat}')
print(f'Tab_Scan: {total_scans} Scans, {scanned_titles} verschiedene Titel')
print(f'  Radio Würmchen KI: {rw_scans} Scans, {rw_titles} verschiedene Titel')
print(f'Tab_Wertung_pro_Person: {total_ratings} Wertungen gesamt')
print(f'  Kurt (95): {kurt_ratings}')
print(f'  Shows (1440-1454): {show_ratings}')
print()
print('Sample Kategorien:')
for i, k in enumerate(samples[:20]):
    print(f'  {i+1}. {k}')
