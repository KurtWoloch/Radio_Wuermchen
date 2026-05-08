import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import pyodbc

base = r'C:\Users\kurt_\Musikprogramm'

dbs = [
    ('rw_Files2000.mdb', ['Tab_Files']),
    ('Tontraeger.mdb', ['Tab_Titel', 'Tab_Interpreten']),
    ('rw_Aehnlichkeiten.mdb', ['Tab_Aehnlich', 'Tab_Scan', 'Tab_Scans']),
    ('rw_bewertung2000.mdb', ['Tab_Person', 'Tab_Wertung_pro_Person']),
]

for db_name, tables in dbs:
    db_path = f'{base}\\{db_name}'
    conn_str = f'DRIVER={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={db_path};'
    try:
        conn = pyodbc.connect(conn_str)
        cursor = conn.cursor()
        print(f'\n=== {db_name} ===')
        for table in tables:
            print(f'\n  [{table}]')
            cursor.execute(f'SELECT TOP 1 * FROM [{table}]')
            cols = [desc[0] for desc in cursor.description]
            for col in cols:
                print(f'    {col}')
            row = cursor.fetchone()
            if row:
                print(f'  --- sample: {dict(zip(cols, row))}')
        conn.close()
    except Exception as e:
        print(f'\n=== {db_name} === ERROR: {e}')
