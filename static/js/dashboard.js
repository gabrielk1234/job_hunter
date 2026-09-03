
const API_BASE_URL = 'http://127.0.0.1:8000/api';

// 設定目前頁碼跟一頁要抓幾筆
let currentSqlitePage = 1;
let currentChromaPage = 1;
let currentSqliteSubTab = 'all'; // 'all' (總資料庫) 或 'latest' (剛爬取的資料)
let currentChromaSubTab = 'all'; // 'all' 或 'latest'
let globalKeyword = ''; // 新增全域搜尋變數
let searchTimeout;      // 用來處理打字防抖 (Debounce)
const ITEMS_PER_PAGE = 20; // 改成一頁 20 筆畫面比較好看

// ChromaDB 篩選條件變數
let filterSalary = 0;
let filterHrPr = 0;

function switchSubTab(dbType, subTab) {
    if (dbType === 'sqlite') {
        currentSqliteSubTab = subTab;
        currentSqlitePage = 1;

        const btnAll = document.getElementById('subtab-sqlite-all');
        const btnLatest = document.getElementById('subtab-sqlite-latest');
        const viewTitle = document.getElementById('sqlite-view-title');
        const indicator = document.getElementById('sqlite-subtab-indicator');

        if (subTab === 'all') {
            btnAll.className = "flex items-center px-5 py-2.5 rounded-xl text-sm font-bold bg-white text-indigo-600 shadow-sm transition-all duration-200";
            btnLatest.className = "flex items-center px-5 py-2.5 rounded-xl text-sm font-medium text-gray-600 hover:text-indigo-600 hover:bg-white/60 transition-all duration-200";
            if (viewTitle) viewTitle.innerText = "總資料庫紀錄";
            if (indicator) indicator.classList.add('hidden');
        } else {
            btnLatest.className = "flex items-center px-5 py-2.5 rounded-xl text-sm font-bold bg-white text-indigo-600 shadow-sm transition-all duration-200";
            btnAll.className = "flex items-center px-5 py-2.5 rounded-xl text-sm font-medium text-gray-600 hover:text-indigo-600 hover:bg-white/60 transition-all duration-200";
            if (viewTitle) viewTitle.innerText = "剛爬取的職缺紀錄";
            if (indicator) indicator.classList.remove('hidden');
        }

        fetchSQLiteData();
    } else if (dbType === 'chroma') {
        currentChromaSubTab = subTab;
        currentChromaPage = 1;

        const btnAll = document.getElementById('subtab-chroma-all');
        const btnLatest = document.getElementById('subtab-chroma-latest');
        const viewTitle = document.getElementById('chroma-view-title');
        const indicator = document.getElementById('chroma-subtab-indicator');

        if (subTab === 'all') {
            btnAll.className = "flex items-center px-5 py-2.5 rounded-xl text-sm font-bold bg-white text-emerald-600 shadow-sm transition-all duration-200";
            btnLatest.className = "flex items-center px-5 py-2.5 rounded-xl text-sm font-medium text-gray-600 hover:text-emerald-600 hover:bg-white/60 transition-all duration-200";
            if (viewTitle) viewTitle.innerText = "已映射 Metadata 與 Documents";
            if (indicator) indicator.classList.add('hidden');
        } else {
            btnLatest.className = "flex items-center px-5 py-2.5 rounded-xl text-sm font-bold bg-white text-emerald-600 shadow-sm transition-all duration-200";
            btnAll.className = "flex items-center px-5 py-2.5 rounded-xl text-sm font-medium text-gray-600 hover:text-emerald-600 hover:bg-white/60 transition-all duration-200";
            if (viewTitle) viewTitle.innerText = "剛爬取之 Metadata 與 Documents";
            if (indicator) indicator.classList.remove('hidden');
        }

        fetchChromaData();
    }
}

async function fetchSQLiteData() {
    const tbody = document.getElementById('sqlite-table-body');
    tbody.innerHTML = `<tr><td colspan="5" class="px-6 py-8 text-center text-gray-500"><i class="fa-solid fa-spinner fa-spin mr-2"></i> 正在連線至 SQLite 撈取資料...</td></tr>`;

    try {
        const isLatest = currentSqliteSubTab === 'latest';
        const response = await fetch(`${API_BASE_URL}/sqlite-jobs?page=${currentSqlitePage}&limit=${ITEMS_PER_PAGE}&keyword=${encodeURIComponent(globalKeyword)}&latest_only=${isLatest}`);
        const result = await response.json();

        // 更新最新爬取數量徽章
        const latestBadge = document.getElementById('sqlite-latest-badge');
        if (latestBadge && result.latest_count !== undefined) {
            latestBadge.innerText = result.latest_count;
        }

        if (result.status === 'success' && result.data.length > 0) {
            renderSQLiteTable(result.data, result.total, result.total_pages);
        } else if (result.status === 'success' && result.data.length === 0) {
            const titleRow = document.getElementById('sqlite-total-count');
            if (titleRow) titleRow.innerText = `總計: 0 筆`;
            
            if (isLatest) {
                tbody.innerHTML = `
                    <tr>
                        <td colspan="5" class="px-6 py-12 text-center text-gray-500">
                            <div class="flex flex-col items-center justify-center space-y-3">
                                <div class="w-12 h-12 rounded-full bg-amber-50 flex items-center justify-center text-amber-500 text-xl shadow-inner">
                                    <i class="fa-solid fa-bolt"></i>
                                </div>
                                <p class="font-bold text-gray-700">目前尚無剛爬取的資料</p>
                                <p class="text-xs text-gray-400 max-w-sm">當您在「任務控制中心」啟動並完成爬蟲後，最新抓取到的職缺會立即分類顯示在此分頁！</p>
                                <a href="/scrapper" class="mt-2 text-indigo-600 hover:text-indigo-700 bg-indigo-50 hover:bg-indigo-100 text-xs font-semibold px-4 py-2 rounded-xl transition-all shadow-sm">
                                    <i class="fa-solid fa-spider mr-1.5"></i> 前往爬蟲控制器
                                </a>
                            </div>
                        </td>
                    </tr>
                `;
            } else {
                tbody.innerHTML = `<tr><td colspan="5" class="px-6 py-8 text-center text-gray-500"><i class="fa-solid fa-folder-open mr-2"></i> 資料庫目前為空。</td></tr>`;
            }
            renderPagination('sqlite', 1, 1);
        } else {
            tbody.innerHTML = `<tr><td colspan="5" class="px-6 py-8 text-center text-red-500"><i class="fa-solid fa-circle-exclamation mr-2"></i> 找不到資料，或是後端回報錯誤：${result.message || '資料庫為空'}</td></tr>`;
        }
    } catch (error) {
        tbody.innerHTML = `<tr><td colspan="5" class="px-6 py-8 text-center text-red-500"><i class="fa-solid fa-plug-circle-xmark mr-2"></i> 無法連線至後端。請確認 FastAPI (Uvicorn) 已在 Port 8000 啟動。</td></tr>`;
    }
}

async function fetchChromaData() {
    const tbody = document.getElementById('chroma-table-body');
    tbody.innerHTML = `<tr><td colspan="7" class="px-6 py-8 text-center text-gray-500"><i class="fa-solid fa-spinner fa-spin mr-2"></i> 正在連線至 ChromaDB 撈取向量資料...</td></tr>`;

    try {
        const isLatest = currentChromaSubTab === 'latest';
        const url = `${API_BASE_URL}/chroma-jobs?page=${currentChromaPage}&limit=${ITEMS_PER_PAGE}&min_salary=${filterSalary}&min_hr_pr=${filterHrPr}&keyword=${encodeURIComponent(globalKeyword)}&latest_only=${isLatest}`;
        const response = await fetch(url);
        const result = await response.json();

        // 更新最新爬取數量徽章
        const latestBadge = document.getElementById('chroma-latest-badge');
        if (latestBadge && result.latest_count !== undefined) {
            latestBadge.innerText = result.latest_count;
        }

        if (result.status === 'success' && result.data.length > 0) {
            renderChromaTable(result.data, result.total_in_db);
            renderPagination('chroma', currentChromaPage, result.total_pages || 1);
        } else if (result.status === 'success' && result.data.length === 0) {
            const countDisplay = document.getElementById('chroma-doc-count');
            if (countDisplay) countDisplay.innerHTML = `0 <span class="text-sm font-normal text-gray-400 ml-2">無資料</span>`;
            
            if (isLatest) {
                tbody.innerHTML = `
                    <tr>
                        <td colspan="7" class="px-6 py-12 text-center text-gray-500">
                            <div class="flex flex-col items-center justify-center space-y-3">
                                <div class="w-12 h-12 rounded-full bg-emerald-50 flex items-center justify-center text-emerald-500 text-xl shadow-inner">
                                    <i class="fa-solid fa-bolt"></i>
                                </div>
                                <p class="font-bold text-gray-700">目前尚無剛向量化的新資料</p>
                                <p class="text-xs text-gray-400 max-w-sm">請前往爬蟲控制器啟動任務，切割後的向量資料將自動分類顯示於此！</p>
                                <a href="/scrapper" class="mt-2 text-emerald-600 hover:text-emerald-700 bg-emerald-50 hover:bg-emerald-100 text-xs font-semibold px-4 py-2 rounded-xl transition-all shadow-sm">
                                    <i class="fa-solid fa-spider mr-1.5"></i> 前往爬蟲控制器
                                </a>
                            </div>
                        </td>
                    </tr>
                `;
            } else {
                tbody.innerHTML = `<tr><td colspan="7" class="px-6 py-8 text-center text-gray-500"><i class="fa-solid fa-folder-open mr-2"></i> ChromaDB 目前無符合資料。</td></tr>`;
            }
            renderPagination('chroma', 1, 1);
        } else {
            tbody.innerHTML = `<tr><td colspan="7" class="px-6 py-8 text-center text-red-500"><i class="fa-solid fa-circle-exclamation mr-2"></i> 找不到資料，或是 ChromaDB 尚未建立：${result.message || '無資料'}</td></tr>`;
        }
    } catch (error) {
        tbody.innerHTML = `<tr><td colspan="7" class="px-6 py-8 text-center text-red-500"><i class="fa-solid fa-plug-circle-xmark mr-2"></i> 無法連線至後端。請確認 FastAPI (Uvicorn) 已啟動。</td></tr>`;
    }
}

function renderSQLiteTable(data, totalCount, totalPages) {
    const sqliteBody = document.getElementById('sqlite-table-body');

    // 更新總計數量標籤
    const titleRow = document.getElementById('sqlite-total-count');
    if (titleRow) titleRow.innerText = `總計: ${totalCount !== undefined ? totalCount : data.length} 筆`;

    sqliteBody.innerHTML = data.map(row => `
        <tr class="hover:bg-indigo-50/70 transition-colors group">
            <td class="px-6 py-4 font-mono text-xs text-gray-500 whitespace-nowrap">
                <div class="flex items-center space-x-1.5">
                    <span>${row.job_id}</span>
                    ${row.is_latest ? `<span class="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-bold bg-amber-100 text-amber-800 border border-amber-200 shadow-xs"><i class="fa-solid fa-bolt text-amber-500 mr-1 text-[8px]"></i>新</span>` : ''}
                </div>
            </td>
            <td class="px-6 py-4 font-medium text-gray-800">${row.custName}</td>
            <td class="px-6 py-4 text-gray-600 truncate max-w-xs font-medium">${row.jobName}</td>
            <td class="px-6 py-4 text-left whitespace-nowrap">
                <a href="${row.job_link}" target="_blank" class="text-indigo-600 hover:text-indigo-800 bg-indigo-50 hover:bg-indigo-100 px-3 py-1.5 rounded-lg text-sm font-medium transition-colors inline-flex items-center">
                    查看職缺 <i class="fa-solid fa-arrow-up-right-from-square ml-1 text-xs"></i>
                </a>
            </td>
            <td class="px-6 py-4 text-right flex items-center justify-end space-x-2 whitespace-nowrap">
                <a href="/analysis?job_id=${row.job_id}" class="text-white bg-indigo-600 hover:bg-indigo-700 px-3 py-1.5 rounded-lg text-sm font-medium transition-colors shadow-sm">
                    <i class="fa-solid fa-wand-magic-sparkles mr-1"></i> AI 解析
                </a>
                <button onclick='openModal(${JSON.stringify(row.raw_json).replace(/'/g, "&#39;")}, "${row.job_id}")' class="text-indigo-600 bg-indigo-50 hover:bg-indigo-100 px-3 py-1.5 rounded-lg text-sm font-medium transition-colors">
                    JSON
                </button>
            </td>
        </tr>
    `).join('');

    renderPagination('sqlite', currentSqlitePage, totalPages);
}

function renderChromaTable(data, totalCount) {
    const chromaBody = document.getElementById('chroma-table-body');
    const countDisplay = document.getElementById('chroma-doc-count');
    if (countDisplay) countDisplay.innerHTML = `${totalCount !== undefined ? totalCount : data.length} <span class="text-sm font-normal text-emerald-500 ml-2"><i class="fa-solid fa-arrow-up"></i> 即時連線</span>`;

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
        <tr class="hover:bg-emerald-50/70 transition-colors">
            <td class="px-6 py-4 font-mono text-xs text-gray-500 whitespace-nowrap">
                <div class="flex items-center space-x-1.5">
                    <span>${row.id}</span>
                    ${row.is_latest ? `<span class="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-bold bg-amber-100 text-amber-800 border border-amber-200 shadow-xs"><i class="fa-solid fa-bolt text-amber-500 mr-1 text-[8px]"></i>新</span>` : ''}
                </div>
            </td>
            <td class="px-6 py-4 font-medium text-gray-800">${custName}</td>
            <td class="px-6 py-4 font-medium text-gray-800 truncate max-w-[200px]">${jobName}</td>
            <td class="px-6 py-4 whitespace-nowrap">
                <span class="bg-gray-100 border border-gray-200 text-gray-600 text-xs px-2 py-1 rounded-md shadow-sm">${jobType}</span>
            </td>
            <td class="px-6 py-4 text-gray-600 font-semibold whitespace-nowrap">${salary}</td>
            <td class="px-6 py-4 text-gray-600 font-semibold whitespace-nowrap">${hrBehaviorPR.toFixed(2)}</td>
            <td class="px-6 py-4 text-right flex items-center justify-end space-x-2 whitespace-nowrap">
                <a href="/analysis?job_id=${meta.job_id || row.id}" class="text-white bg-emerald-500 hover:bg-emerald-600 px-3 py-1.5 rounded-lg text-sm font-medium transition-colors shadow-sm">
                    <i class="fa-solid fa-wand-magic-sparkles mr-1"></i> AI 解析
                </a>
                <button onclick='openModal(${JSON.stringify(row).replace(/'/g, "&#39;")}, "Chroma ID: ${row.id}")' class="text-emerald-700 bg-emerald-50 hover:bg-emerald-100 px-3 py-1.5 rounded-lg text-sm font-medium transition-colors">
                    Meta
                </button>
            </td>
        </tr>
        `
    }).join('');
}

function renderPagination(type, currentPage, totalPages) {
    const container = document.getElementById(`${type}-pagination-container`);
    if (!container) return;
    if (totalPages < 1) totalPages = 1;

    let html = `<div class="flex items-center justify-between w-full">`;
    html += `<span class="text-sm text-gray-600">目前第 ${currentPage} 頁 / 共 ${totalPages} 頁</span>`;
    html += `<div class="flex items-center space-x-2">`;
    
    // 上一頁按鈕
    html += `<button onclick="goToPage('${type}', ${currentPage - 1})" ${currentPage <= 1 ? 'disabled' : ''} class="px-3 py-1 border border-gray-300 rounded hover:bg-gray-100 disabled:opacity-50 text-sm font-medium text-gray-700">上一頁</button>`;

    // 頁碼區塊 (顯示第一頁、最後一頁、當前頁的前後兩頁)
    html += `<div class="hidden md:flex items-center space-x-1">`;
    if (currentPage > 3) {
        html += `<button onclick="goToPage('${type}', 1)" class="px-3 py-1 border border-transparent rounded hover:bg-indigo-50 text-sm">1</button>`;
        if (currentPage > 4) html += `<span class="px-1 text-gray-400">...</span>`;
    }

    for (let i = Math.max(1, currentPage - 2); i <= Math.min(totalPages, currentPage + 2); i++) {
        if (i === currentPage) {
            html += `<button class="px-3 py-1 border border-indigo-600 bg-indigo-600 text-white rounded font-bold text-sm shadow-sm">${i}</button>`;
        } else {
            html += `<button onclick="goToPage('${type}', ${i})" class="px-3 py-1 border border-transparent rounded hover:bg-indigo-50 text-sm text-gray-700">${i}</button>`;
        }
    }

    if (currentPage < totalPages - 2) {
        if (currentPage < totalPages - 3) html += `<span class="px-1 text-gray-400">...</span>`;
        html += `<button onclick="goToPage('${type}', ${totalPages})" class="px-3 py-1 border border-transparent rounded hover:bg-indigo-50 text-sm text-gray-700">${totalPages}</button>`;
    }
    html += `</div>`;

    // 下一頁按鈕
    html += `<button onclick="goToPage('${type}', ${currentPage + 1})" ${currentPage >= totalPages ? 'disabled' : ''} class="px-3 py-1 border border-gray-300 rounded hover:bg-gray-100 disabled:opacity-50 text-sm font-medium text-gray-700">下一頁</button>`;
    
    // 跳轉輸入框
    html += `<div class="ml-4 flex items-center space-x-2 border-l pl-4 border-gray-300">
                <span class="text-sm text-gray-600">跳至</span>
                <input type="number" id="jump-${type}" min="1" max="${totalPages}" class="w-16 px-2 py-1 border border-gray-300 rounded text-sm focus:ring-2 focus:ring-indigo-500 focus:outline-none">
                <button onclick="jumpToInput('${type}', ${totalPages})" class="px-3 py-1 bg-gray-200 hover:bg-gray-300 text-gray-700 text-sm font-medium rounded transition-colors">Go</button>
             </div>`;
             
    html += `</div></div>`;
    container.innerHTML = html;
}

function goToPage(type, pageNo) {
    if (type === 'sqlite') {
        currentSqlitePage = pageNo;
        fetchSQLiteData();
    } else {
        currentChromaPage = pageNo;
        fetchChromaData();
    }
}

function jumpToInput(type, totalPages) {
    const inputVal = parseInt(document.getElementById(`jump-${type}`).value);
    if (!inputVal || inputVal < 1 || inputVal > totalPages) {
        alert(`請輸入 1 到 ${totalPages} 之間的有效頁碼！`);
        return;
    }
    goToPage(type, inputVal);
}

function handleSearch(keyword) {
    // 防抖機制：等你打完字停下來 500 毫秒後，才去 call 後端 API
    clearTimeout(searchTimeout);
    searchTimeout = setTimeout(() => {
        globalKeyword = keyword.trim().toLowerCase();
        
        const activeTab = document.querySelector('.tab-content.active').id;
        if (activeTab === 'tab-sqlite') {
            currentSqlitePage = 1; // 搜尋新東西時把頁碼重置回第 1 頁
            fetchSQLiteData();
        } else if (activeTab === 'tab-chroma') {
            currentChromaPage = 1;
            fetchChromaData();
        }
    }, 500); 
}

// ================= Chroma 過濾器等 =================
function applyChromaFilters() {
    const salInput = document.getElementById('filter-salary').value;
    const hrInput = document.getElementById('filter-hr-pr').value;
    
    filterSalary = salInput ? parseInt(salInput) : 0;
    filterHrPr = hrInput ? parseFloat(hrInput) : 0;
    
    // 【一定要加這段】不然輸入 50，後端還是找不到 0.32 的資料
    if (filterHrPr > 1) {
        filterHrPr = filterHrPr / 100;
    }
    
    currentChromaPage = 1; 
    fetchChromaData();
}
function clearChromaFilters() {
    document.getElementById('filter-salary').value = '';
    document.getElementById('filter-hr-pr').value = '';
    filterSalary = 0;
    filterHrPr = 0;
    currentChromaPage = 1;
    fetchChromaData();
}
// -------------------------------------------------------------

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

// 初始化：一打開網頁就去後端撈資料，並根據 URL 參數切換分頁
window.onload = () => {
    const urlParams = new URLSearchParams(window.location.search);
    const viewParam = urlParams.get('view') || urlParams.get('subtab');
    const dbParam = urlParams.get('db') || urlParams.get('tab');

    if (dbParam === 'chroma') {
        switchTab('chroma');
    }

    if (viewParam === 'latest') {
        switchSubTab('sqlite', 'latest');
        switchSubTab('chroma', 'latest');
    } else {
        fetchSQLiteData();
        fetchChromaData();
    }
};