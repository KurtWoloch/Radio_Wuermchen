import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import pyodbc

base = r'C:\Users\kurt_\Musikprogramm'
verkn = f'{base}\\rw_verknuepfung2000.mdb'

conn_str = f'DRIVER={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={verkn};'
conn = pyodbc.connect(conn_str)
cursor = conn.cursor()

# List all tables (including linked ones)
tables = []
for row in cursor.tables(tableType='TABLE'):
    tables.append(row.table_name)

print(f'Tables in rw_verknuepfung2000.mdb ({len(tables)}):')
for t in sorted(tables):
    print(f'  {t}')

# Try to get columns from key tables
key_tables = ['Tab_Files', 'Tab_Wertung_pro_Person', 'Tab_Person', 'Tab_Aehnlich', 'Tab_Titel', 'Tab_Interpreten']
for table in key_tables:
    if table in tables:
        try:
            cursor.execute(f'SELECT TOP 1 * FROM [{table}]')
            cols = [desc[0] for desc in cursor.description]
            print(f'\n[{table}] columns:')
            for col in cols:
                print(f'  {col}')
            row = cursor.fetchone()
            if row:
                print(f'  sample: {dict(zip(cols, row))}')
        except Exception as e:
            print(f'\n[{table}] ERROR: {e}')
    else:
        print(f'\n[{table}] NOT FOUND')

conn.close()
