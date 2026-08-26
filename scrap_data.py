import requests
import time
import random as rd
import json
import sqlite3
import os
from tools.pharse import get_document,get_metadata,create_chunks
import chromadb

config_file = './config.json'
sqlite_db = 'all_jobs.db'
table_name = 'job_details'
chroma_db = './my_job_db'
chroma_collection = 'jobs_collection'

with open(config_file, 'r', encoding='utf-8') as f:
        config_json = json.load(f)

cookies,headers = config_json['cookies'],config_json['headers']

# ----------------- 連結sqlite3資料庫開始 -----------------
print("開始連結 sqlite3 資料庫")
conn = sqlite3.connect(sqlite_db)
cursor = conn.cursor()
print("建立資料表...")
cursor.execute(f'''
    CREATE TABLE IF NOT EXISTS {table_name} (
        job_id TEXT PRIMARY KEY,
        job_data TEXT
    )
''')
conn.commit()
# ----------------- 連結sqlite3資料庫結束 -----------------
# ----------------- 連結ChromaDB資料庫開始 -----------------
client = chromadb.PersistentClient(path=chroma_db)
collection = client.get_or_create_collection(name=chroma_collection)
# ----------------- 連結ChromaDB資料庫結束 -----------------

params = {
    'area': '6001016000',
    'jobcat': '2007000000',
    'jobsource': 'joblist_search',
    'mode': 's',
    'orLabel': 'foreigners@overseasStudents^20,foreigners@chineseDiasporas^20,foreigners@foreignStudents^20,foreigners@foreigners^20,foreigners@foreigners_tick^20,foreigners@overseasStudents_tick^20,foreigners@full_fc_em_jbs^20,foreigners@pt_fc_em_jbs^20,c@2026career^5',
    'order': '16',
    'page': '1',
    'pagesize': '20',
}

response = requests.get('https://www.104.com.tw/jobs/search/api/jobs', params=params, cookies=cookies, headers=headers)

if response.status_code != 200:
    raise RuntimeError("Cannot scrap info from website, Please check your cookies or slow down searching speed")

job_json = response.json()['data']
print(f"找到{len(job_json)}個職缺")

# ----------------- 爬蟲抓資料的迴圈開始 -----------------
for job in job_json:
    job_id = job['jobNo']
    job_code = job['link']['job'].split('/')[-1]
    # 去request職缺的細節
    job_detail_response = requests.get(f'https://www.104.com.tw/api/jobs/{job_code}', cookies=cookies, headers=headers)
    
    if job_detail_response.status_code == 200:
        job_detail_json = job_detail_response.json().get('data')
    else: 
        print(f'{job_code}獲取資料失敗')
        continue
    
    # ----------- 儲存進sqlite3資料庫 -------------
    print(f"【sqlite】{job_code}-{job['custName']}-{job['jobName']} saving...")
    job_json_str = json.dumps(job_detail_json, ensure_ascii=False)
    cursor.execute(f'''
        INSERT OR REPLACE INTO {table_name} (job_id, job_data) 
        VALUES (?, ?)
    ''', (job_id, job_json_str))
    conn.commit()
    print(f"【sqlite】✅ 成功處理並存入職缺：{job_id}")
    
    # ----------- 儲存進chromaDB向量資料庫 -------------
    documents = get_document(job_detail_json) # 將json資料整理成document
    metadata = get_metadata(job_detail_json)
    
    # 將資料切分成6個chunk
    chunks = create_chunks(job_id=job_id,full_document=documents,base_metadata=metadata)

    chunk_documents = [c['text'] for c in chunks]
    chunk_metadatas = [c['metadata'] for c in chunks]
    chunk_ids = [c['ids'] for c in chunks]
    
    # 
    print(f"【ChromaDB】{job_code}-{job_detail_json['header']['custName']}-{job_detail_json['header']['jobName']} saving...")

    collection.add(
        documents=chunk_documents, 
        metadatas=chunk_metadatas, 
        ids=chunk_ids
    )
    print(f"【ChromaDB】✅ 成功處理並存入職缺：{job_id}")
        
    time.sleep(rd.randint(2,5))# 因為有request，要適當休息一下 隨機2到5秒
# ----------------- 爬蟲抓資料的迴圈結束 -----------------
