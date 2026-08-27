
const API_BASE_URL = 'http://127.0.0.1:8000/api';

async function fetchSQLiteData() {
    const tbody = document.getElementById('sqlite-table-body');
    tbody.innerHTML = `<tr><td colspan="5" class="px-6 py-8 text-center text-gray-500"><i class="fa-solid fa-spinner fa-spin mr-2"></i> 正在連線至 SQLite 撈取資料...</td></tr>`;

    try {
        const response = await fetch(`${API_BASE_URL}/sqlite-jobs`);
        const result = await response.json();

        if (result.status === 'success' && result.data.length > 0) {
            renderSQLiteTable(result.data);
        } else {
            tbody.innerHTML = `<tr><td colspan="5" class="px-6 py-8 text-center text-red-500"><i class="fa-solid fa-circle-exclamation mr-2"></i> 找不到資料，或是後端回報錯誤：${result.message || '資料庫為空'}</td></tr>`;
        }
    } catch (error) {
        tbody.innerHTML = `<tr><td colspan="5" class="px-6 py-8 text-center text-red-500"><i class="fa-solid fa-plug-circle-xmark mr-2"></i> 無法連線至後端。請確認 FastAPI (Uvicorn) 已在 Port 8000 啟動。</td></tr>`;
    }
}

async function fetchChromaData() {
    const tbody = document.getElementById('chroma-table-body');
    tbody.innerHTML = `<tr><td colspan="5" class="px-6 py-8 text-center text-gray-500"><i class="fa-solid fa-spinner fa-spin mr-2"></i> 正在連線至 ChromaDB 撈取向量資料...</td></tr>`;

    try {
        const response = await fetch(`${API_BASE_URL}/chroma-jobs`);
        const result = await response.json();

        if (result.status === 'success' && result.data.length > 0) {
            renderChromaTable(result.data);
        } else {
            tbody.innerHTML = `<tr><td colspan="5" class="px-6 py-8 text-center text-red-500"><i class="fa-solid fa-circle-exclamation mr-2"></i> 找不到資料，或是 ChromaDB 尚未建立：${result.message || '無資料'}</td></tr>`;
        }
    } catch (error) {
        tbody.innerHTML = `<tr><td colspan="5" class="px-6 py-8 text-center text-red-500"><i class="fa-solid fa-plug-circle-xmark mr-2"></i> 無法連線至後端。請確認 FastAPI (Uvicorn) 已啟動。</td></tr>`;
    }
}

function renderSQLiteTable(data) {
    const sqliteBody = document.getElementById('sqlite-table-body');

    // 更新總計數量標籤
    const titleRow = document.getElementById('sqlite-total-count');
    if (titleRow) titleRow.innerText = `總計: ${data.length} 筆`;
    console.log(data.length);
    sqliteBody.innerHTML = data.map(row => `
        <tr class="hover:bg-indigo-50 transition-colors group">
            <td class="px-6 py-4 font-mono text-xs text-gray-500">${row.job_id}</td>
            <td class="px-6 py-4 font-medium text-gray-800">${row.custName}</td>
            <td class="px-6 py-4 text-gray-600 truncate max-w-xs">${row.jobName}</td>
            <td class="px-6 py-4"><span class="bg-green-100 text-green-700 text-xs px-2 py-1 rounded-full"><i class="fa-solid fa-check mr-1"></i>已儲存</span></td> 
            <td class="px-6 py-4 text-right">
                <button onclick='openModal(${JSON.stringify(row.raw_json).replace(/'/g, "&#39;")}, "${row.job_id}")' class="text-primary hover:text-indigo-800 bg-indigo-50 hover:bg-indigo-100 px-3 py-1.5 rounded-lg text-sm font-medium transition-colors">
                    檢視 JSON
                </button>
            </td>
        </tr>
    `).join('');
}

function renderChromaTable(data) {
    const chromaBody = document.getElementById('chroma-table-body');

    // 更新統計數字
    const countDisplay = document.getElementById('chroma-doc-count');
    if (countDisplay) countDisplay.innerHTML = `${data.length} <span class="text-sm font-normal text-green-500 ml-2"><i class="fa-solid fa-arrow-up"></i> 即時連線</span>`;

    chromaBody.innerHTML = data.map(row => {
        // 防呆處理，避免 metadata 為空導致程式崩潰
        const meta = row.metadata || {};
        let salary = '未知';
        if (meta.salaryMin === 0 || !['月薪', '時薪', '年薪'].includes(meta.salaryType)) {
            salary = '面議';
        } else if (meta.salaryMin) {
            salary = `$${meta.salaryMin.toLocaleString()} (${meta.salaryType})`;
        }
        const jobType = meta.jobType;
        const jobName = meta.jobName || '未知職缺';
        const custName = meta.custName || '未知公司';
        const hrBehaviorPR = meta.hrBehaviorPR || 0;

        return `
        <tr class="hover:bg-emerald-50 transition-colors">
            <td class="px-6 py-4 font-mono text-xs text-gray-500">${row.id}</td>
            <td class="px-6 py-4 font-medium text-gray-800">${custName}</td>
            <td class="px-6 py-4 font-medium text-gray-800 truncate max-w-[200px]">${jobName}</td>
            <td class="px-6 py-4">
                <span class="bg-gray-100 border border-gray-200 text-gray-600 text-xs px-2 py-1 rounded-md shadow-sm">${jobType}</span>
            </td>
            <td class="px-6 py-4 text-gray-600 font-semibold">${salary}</td>
            <td class="px-6 py-4 text-gray-600 font-semibold">${hrBehaviorPR.toFixed(2)}</td>
            <td class="px-6 py-4 text-right">
                <button onclick='openModal(${JSON.stringify(row).replace(/'/g, "&#39;")}, "Chroma ID: ${row.id}")' class="text-secondary hover:text-emerald-700 bg-emerald-50 hover:bg-emerald-100 px-3 py-1.5 rounded-lg text-sm font-medium transition-colors">
                    查看 Metadata
                </button>
            </td>
        </tr>
        `
    }).join('');
}

function switchTab(tabId) {
    // 1. 切換頁籤前，先清空搜尋框並恢復所有隱藏的表格資料
    const searchInput = document.getElementById('global-search');
    if (searchInput) {
        searchInput.value = '';
        handleSearch('');
    }

    // 2. 隱藏所有的 tab 內容
    document.querySelectorAll('.tab-content').forEach(el => el.classList.remove('active'));

    // 3. 把所有的側邊欄按鈕恢復成「灰暗狀態」 (加上防呆檢查，即使按鈕被刪除也不會報錯)
    const btnSqlite = document.getElementById('btn-sqlite');
    const btnChroma = document.getElementById('btn-chroma');

    const inactiveClass = "w-full flex items-center px-4 py-3 rounded-xl text-gray-400 hover:bg-gray-800 hover:text-white transition-all duration-200";

    if (btnSqlite) btnSqlite.className = inactiveClass;
    if (btnChroma) btnChroma.className = inactiveClass;

    // 4. 顯示指定的 tab 內容
    const activeTab = document.getElementById(`tab-${tabId}`);
    if (activeTab) activeTab.classList.add('active');

    // 5. 更改上方的標題文字
    const titles = {
        'sqlite': 'SQLite 原始資料庫',
        'chroma': 'ChromaDB 向量資料庫'
    };
    const pageTitle = document.getElementById('page-title');
    if (pageTitle && titles[tabId]) {
        pageTitle.innerText = titles[tabId];
    }

    // 6. 將被選中的側邊欄按鈕變成「發亮的靛藍色」
    const activeBtn = document.getElementById(`btn-${tabId}`);
    if (activeBtn) {
        activeBtn.className = "w-full flex items-center px-4 py-3 rounded-xl bg-indigo-600 text-white shadow-lg shadow-indigo-500/30 transition-all duration-200";
    }
}

function openModal(data, idText) {
    const modal = document.getElementById('json-modal');
    const modalContent = document.getElementById('modal-content');

    document.getElementById('modal-job-id').innerText = idText;

    // 判斷傳進來的是物件還是字串
    console.log('Data type:', typeof data);
    let displayContent = '';
    if (typeof data === 'object' && data !== null) {
        // 如果是 JSON 物件，維持原本的縮排排版
        displayContent = JSON.stringify(data, null, 4);
    } else {
        // 如果是純字串，就直接原樣貼上
        displayContent = data;
    }

    document.getElementById('json-code-block').innerText = displayContent;

    modal.classList.remove('hidden');
    setTimeout(() => {
        modal.classList.remove('opacity-0');
        modalContent.classList.remove('scale-95');
    }, 10);
}

function closeModal() {
    const modal = document.getElementById('json-modal');
    const modalContent = document.getElementById('modal-content');

    modal.classList.add('opacity-0');
    modalContent.classList.add('scale-95');

    setTimeout(() => {
        modal.classList.add('hidden');
    }, 300);
}

document.getElementById('json-modal').addEventListener('click', function (e) {
    if (e.target === this) closeModal();
});

function fillInput(text) {
    document.getElementById('chat-input').value = text;
    document.getElementById('chat-input').focus();
}

function handleSearch(keyword) {
    // 為了實現大小寫不敏感的搜尋，統一轉成小寫，並清除頭尾空白
    keyword = keyword.toLowerCase().trim();

    // 知道現在使用者正在看哪個頁籤
    const activeTab = document.querySelector('.tab-content.active').id;

    let tbodyId = '';
    if (activeTab === 'tab-sqlite') {
        tbodyId = 'sqlite-table-body';
    } else if (activeTab === 'tab-chroma') {
        tbodyId = 'chroma-table-body';
    } else {
        return; // 如果在 LLM 頁籤就不做事
    }

    const tbody = document.getElementById(tbodyId);
    if (!tbody) return;

    // 抓出表格所有的資料列 <tr>
    const rows = tbody.querySelectorAll('tr');

    rows.forEach(row => {
        // 防呆：如果只有一個 <td>，通常是 "正在載入..." 或 "錯誤訊息" 的提示列，跳過不處理
        if (row.cells.length === 1) return;

        // 只搜索id，公司名稱以及職缺名稱
        const jobId = row.cells[0].innerText.toLowerCase();
        const custName = row.cells[1].innerText.toLowerCase();
        const jobName = row.cells[2].innerText.toLowerCase();

        const searchTarget = `${jobId} ${custName} ${jobName}`;

        // 判斷是否「包含」關鍵字
        if (searchTarget.includes(keyword)) {
            row.style.display = ''; // 包含的話，取消隱藏，正常顯示
        } else {
            row.style.display = 'none'; // 不包含的話，把這一列隱藏起來
        }
    });
}

function handleChatSubmit(e) {
    e.preventDefault();
    const input = document.getElementById('chat-input');
    const text = input.value.trim();
    if (!text) return;

    const chatContainer = document.getElementById('chat-messages');

    const userMsg = document.createElement('div');
    userMsg.className = "flex space-x-3 justify-end";
    userMsg.innerHTML = `
        <div class="bg-primary text-white p-4 rounded-2xl rounded-tr-none shadow-sm max-w-[80%]">
            <p>${text}</p>
        </div>
        <div class="flex-shrink-0 w-8 h-8 rounded-full bg-gray-300 flex items-center justify-center text-gray-700 text-xs shadow-sm overflow-hidden">
            <img src="https://placehold.co/100x100/4F46E5/FFFFFF?text=JH" alt="User">
        </div>
    `;
    chatContainer.appendChild(userMsg);

    input.value = '';
    chatContainer.scrollTop = chatContainer.scrollHeight;

    setTimeout(() => {
        const aiMsg = document.createElement('div');
        aiMsg.className = "flex space-x-3";

        let responseText = "我目前只是一個靜態的 HTML 介面喔！等你把 Python 後端的 FastAPI 或 Flask 寫好，串接 OpenAI API 並且透過 `collection.query()` 搜尋 ChromaDB 後，就能把真正的回答傳送回這裡了！🚀";

        aiMsg.innerHTML = `
            <div class="flex-shrink-0 w-8 h-8 rounded-full bg-primary flex items-center justify-center text-white text-xs shadow-sm">
                AI
            </div>
            <div class="bg-white border border-gray-200 text-gray-800 p-4 rounded-2xl rounded-tl-none shadow-sm max-w-[80%]">
                <p>${responseText}</p>
            </div>
        `;
        chatContainer.appendChild(aiMsg);
        chatContainer.scrollTop = chatContainer.scrollHeight;
    }, 1000);
}

// 初始化：一打開網頁就去後端撈資料
window.onload = () => {
    fetchSQLiteData();
    fetchChromaData();

    // 綁定 ChromaDB 頁籤的「重新載入」按鈕
    const reloadBtn = document.querySelector('#tab-chroma button');
    if (reloadBtn) {
        reloadBtn.onclick = fetchChromaData;
    }
};