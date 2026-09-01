# JobHunter 🕵️‍♂️

> 個人化的 AI 求職助手 — 從 104 人力銀行自動爬取職缺，結合向量搜尋與 Gemini，幫你找機會、配對履歷、生成推薦信。

<video src="https://raw.githubusercontent.com/gabrielk1234/job_hunter/main/demo.mp4" controls width="100%"></video>
---

## 專案簡介

**JobHunter**（本 repo 名稱：`job_analysis`）是一套面向求職者的全端工具。它將職缺搜集、資料管理、語意搜尋與 AI 分析整合在同一個 Web 介面中，讓你不用在 104 與履歷之間來回切換，也能用自然語言問「適合我的職缺有哪些？」。

### 核心特色

| 功能 | 說明 |
|------|------|
| **104 職缺爬蟲** | 依地區、職類、關鍵字搜尋，WebSocket 即時顯示進度 |
| **雙層資料儲存** | SQLite 存完整職缺；ChromaDB 存向量 chunk，支援語意搜尋 |
| **資料儀表板** | 瀏覽、篩選已爬職缺（薪資、HR 回覆率等） |
| **AI 職涯顧問** | Gemini + RAG，用對話方式查職缺、取得職涯建議 |
| **履歷深度解析** | 上傳 PDF 或貼文字，AI 分析優勢、弱點與修改建議 |
| **智慧職缺配對** | 向量粗篩 + AI 精準打分（0–100），列出符合原因與風險 |
| **一鍵推薦信** | 依履歷與職缺內容，自動生成 104 投遞用自我推薦信 |

---

## 技術堆疊

### 後端
- **[FastAPI](https://fastapi.tiangolo.com/)** — Web API 與頁面路由
- **[SQLite](https://www.sqlite.org/)** — 職缺、履歷、配對結果
- **[ChromaDB](https://www.trychroma.com/)** — 向量資料庫，支援 RAG 語意搜尋
- **[Google Gemini](https://ai.google.dev/)** — 履歷解析、配對打分、對話、推薦信生成

### 前端
- **Jinja2 Templates** — 伺服器端渲染
- **Tailwind CSS** — UI 樣式
- **Font Awesome** — 圖示

### 資料來源
- **[104 人力銀行 API](https://www.104.com.tw/)** — 職缺列表與詳情

### 主要 Python 套件
```
fastapi · chromadb · google-genai · requests · pydantic
PyMuPDF · browser-cookie3 · uvicorn · jinja2
```

---

## 快速開始

### 環境需求

- **Python** 3.10 或以上
- **Google Chrome**（Web 爬蟲會讀取 104 登入 Cookie）
- **Gemini API Key**（[Google AI Studio](https://aistudio.google.com/apikey) 申請）

### 1. 克隆專案

```bash
git clone https://github.com/gabrielk1234/job_hunter.git
cd job_analysis
```

### 2. 建立虛擬環境並安裝依賴

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
pip install google-genai PyMuPDF browser-cookie3 uvicorn jinja2
```

> `requirements.txt` 目前僅列出部分核心套件，上述額外套件為執行時所需，請一併安裝。

### 3. 設定 API Key 與爬蟲

請參考下方「設定檔說明」，建立 `apikey.json` 與 `config.json`。

### 4. 啟動服務

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

瀏覽器開啟：**http://localhost:8000**

### 5. 建議使用流程

1. **爬蟲控制器** (`/scrapper`) — 選擇地區、職類與關鍵字，開始抓取職缺
2. **資料儀表板** (`/dashboard`) — 確認資料是否正確寫入
3. **Profile** (`/profile`) — 上傳履歷，取得 AI 解析結果
4. **職缺匹配** (`/matches`) — 觸發配對，查看推薦職缺與推薦信
5. **AI 職涯顧問** (`/assistant`) — 用自然語言搜尋與諮詢

---

## 專案目錄結構

```
job_analysis/
├── main.py                 # FastAPI 主程式（API、WebSocket 爬蟲、頁面路由）
├── scrap_data.py           # 獨立爬蟲腳本（命令列批次抓取）
├── config.json             # 104 爬蟲用的 cookies / headers（請勿提交真實資料）
├── apikey.json             # Gemini API Key（已加入 .gitignore）
├── requirements.txt        # Python 依賴清單
│
├── tools/
│   ├── llm_agent.py        # Gemini 對話、RAG 搜尋工具
│   ├── pharse.py           # 職缺 JSON 解析、chunk 切分、metadata 抽取
│   └── myown_tools.py      # 共用工具函式
│
├── templates/              # Jinja2 前端頁面
│   ├── home.html           # 系統首頁
│   ├── dashboard.html      # 資料儀表板
│   ├── scrapper.html       # 爬蟲控制器
│   ├── assistant.html      # AI 職涯顧問
│   ├── profile.html        # 履歷上傳與解析
│   └── matches.html        # 職缺配對結果
│
├── static/
│   ├── js/dashboard.js     # 儀表板前端邏輯
│   ├── job_area.json       # 104 地區代碼對照
│   └── job_cat.json        # 104 職類代碼對照
│
├── all_jobs.db             # SQLite 資料庫（執行後自動建立）
└── my_job_db/              # ChromaDB 向量資料庫（執行後自動建立）
```

---

## 設定檔說明

本專案**不使用 `.env`**，改以 JSON 設定檔管理機敏資訊。

### `apikey.json`（必填）

在專案根目錄建立此檔案（已在 `.gitignore` 中，不會被提交）：

```json
{
  "gemini_api_key": "YOUR_GEMINI_API_KEY"
}
```

### `config.json`（爬蟲必填）

供 104 API 請求使用的 cookies 與 headers。可從瀏覽器 DevTools → Network 複製已登入 104 的請求標頭。

```json
{
  "cookies": {
    "JBCLOGIN": "...",
    "cf_clearance": "..."
  },
  "headers": {
    "User-Agent": "Mozilla/5.0 ...",
    "Accept": "application/json, text/plain, */*",
    "Referer": "https://www.104.com.tw/jobs/search/"
  }
}
```

> **安全提醒**：`config.json` 含登入 Cookie，請勿將含真實資料的檔案 push 至公開 repo。建議加入 `.gitignore` 或使用私有 repo。

### Web 爬蟲 Cookie 來源

`/api/ws-scrape`（Web 介面爬蟲）預設透過 `browser_cookie3` 讀取本機 Chrome Cookie。若路徑與你的環境不同，請修改 `main.py` 中對應的 `cookie_file` 路徑，或改為使用 `config.json` 的 cookies（參考 `scrap_data.py`）。

---

## 資料庫說明

| 儲存位置 | 用途 |
|----------|------|
| `all_jobs.db` | `job_documents`（完整職缺）、`user_profiles`（履歷）、`user_matches`（配對結果） |
| `my_job_db/` | ChromaDB collection `job_chunks`，供向量搜尋與 RAG |

首次執行 `main.py` 時會自動建立 SQLite 資料表。

---

## API 端點概覽

| 方法 | 路徑 | 說明 |
|------|------|------|
| `GET` | `/api/sqlite-jobs` | 分頁取得 SQLite 職缺 |
| `GET` | `/api/chroma-jobs` | 分頁取得 ChromaDB 職缺（可篩薪資、HR 回覆率） |
| `WS` | `/api/ws-scrape` | WebSocket 即時爬蟲 |
| `POST` | `/api/parse-profile` | 解析履歷（PDF / 文字） |
| `POST` | `/api/trigger-match` | 觸發背景職缺配對 |
| `GET` | `/api/get-matches` | 取得配對結果 |
| `POST` | `/api/generate-cover-letter` | 生成自我推薦信 |
| `POST` | `/api/chat` | AI 職涯顧問對話 |

完整互動式文件：啟動後前往 **http://localhost:8000/docs**

---

## 注意事項

- 爬蟲請遵守 [104 人力銀行](https://www.104.com.tw/) 服務條款，並控制請求頻率（程式內建 2–5 秒隨機延遲）。
- Cookie 會過期，若爬蟲失敗請重新登入 104 並更新 `config.json`。
- AI 配對與推薦信僅供參考，投遞前請自行確認內容。

---

## 授權條款

本專案以 [MIT License](LICENSE) 釋出。

```
MIT License

Copyright (c) 2026 JobHunter Contributors

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

---

## 貢獻

歡迎提交 Issue 或 Pull Request。開發中的功能與待辦事項可參考 `things_for_review/things_to_do.txt`。
