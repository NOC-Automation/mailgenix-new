import os
import sys
import subprocess
import tempfile
import requests
import pandas as pd
import mysql.connector
from urllib.parse import urlparse
import logging

# Konfigurasi MySQL
MYSQL_CONFIG = {
    'user': 'badia',
    'password': '0fejt)kGRimmi~NsH8UL',
    'host': 'localhost',
    'database': 'automation_db'
}

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

def download_file(github_url):
    logging.info(f"Mengunduh file dari {github_url}")
    response = requests.get(github_url)
    if response.status_code != 200:
        raise Exception(f"Gagal mengunduh file: {response.status_code}")
    filename = os.path.basename(urlparse(github_url).path)
    temp_dir = tempfile.gettempdir()
    file_path = os.path.join(temp_dir, filename)
    with open(file_path, 'wb') as f:
        f.write(response.content)
    logging.info(f"File disimpan di {file_path}")
    return file_path

def execute_sql_dump(file_path):
    logging.info(f"Menjalankan SQL dump: {file_path}")
    cmd = [
        'mysql',
        f"-u{MYSQL_CONFIG['user']}",
        f"-p{MYSQL_CONFIG['password']}",
        MYSQL_CONFIG['database']
    ]
    with open(file_path, 'r') as f:
        subprocess.run(cmd, stdin=f, check=True)
    logging.info("SQL dump berhasil dijalankan.")

def get_table_columns(table_name):
    conn = mysql.connector.connect(**MYSQL_CONFIG)
    cursor = conn.cursor()
    cursor.execute(f"DESCRIBE {table_name}")
    columns = [row[0] for row in cursor.fetchall()]
    cursor.close()
    conn.close()
    return columns

def insert_dataframe_to_mysql(df, table_name):
    table_columns = get_table_columns(table_name)
    matching_cols = [col for col in df.columns if col in table_columns]
    if not matching_cols:
        logging.warning(f"Tidak ada kolom yang cocok untuk tabel {table_name}. Lewati.")
        return
    df_filtered = df[matching_cols]
    conn = mysql.connector.connect(**MYSQL_CONFIG)
    cursor = conn.cursor()
    cols = ', '.join(matching_cols)
    placeholders = ', '.join(['%s'] * len(matching_cols))
    query = f"INSERT INTO {table_name} ({cols}) VALUES ({placeholders})"
    for _, row in df_filtered.iterrows():
        cursor.execute(query, tuple(row))
    conn.commit()
    cursor.close()
    conn.close()
    logging.info(f"{len(df_filtered)} baris berhasil diimport ke {table_name}")

def insert_csv_to_mysql(file_path, table_name):
    logging.info(f"Import CSV {file_path} ke tabel {table_name}")
    df = pd.read_csv(file_path)
    insert_dataframe_to_mysql(df, table_name)

def insert_json_to_mysql(file_path, table_name):
    logging.info(f"Import JSON {file_path} ke tabel {table_name}")
    df = pd.read_json(file_path)
    insert_dataframe_to_mysql(df, table_name)

def detect_file_type(file_path):
    ext = os.path.splitext(file_path)[1].lower()
    if ext == '.sql':
        return 'sql'
    elif ext == '.csv':
        return 'csv'
    elif ext == '.json':
        return 'json'
    else:
        raise Exception(f"Tipe file tidak didukung: {ext}")

def map_filename_to_table(filename):
    base_name = os.path.splitext(filename)[0].lower()
    if base_name.startswith('core_'):
        return base_name
    else:
        return f"core_{base_name}"

def process_file(github_url):
    try:
        file_path = download_file(github_url)
        file_type = detect_file_type(file_path)
        filename = os.path.basename(file_path)
        table_name = map_filename_to_table(filename)

        if file_type == 'sql':
            execute_sql_dump(file_path)
        elif file_type == 'csv':
            insert_csv_to_mysql(file_path, table_name)
        elif file_type == 'json':
            insert_json_to_mysql(file_path, table_name)
    except Exception as e:
        logging.error(f"Gagal memproses file {github_url}: {e}")

def main():
    if len(sys.argv) < 2:
        print("Usage: python import_github_to_mysql_batch.py <github_raw_file_url1> <github_raw_file_url2> ...")
        sys.exit(1)

    github_urls = sys.argv[1:]
    for url in github_urls:
        logging.info(f"Memproses file: {url}")
        process_file(url)

if __name__ == "__main__":
    main()
