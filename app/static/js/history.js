const t = (key) => (window.__t && window.__t[key]) || key;

const historyList = document.getElementById('history-list');
const historyEmpty = document.getElementById('history-empty');
const historyToolbar = document.getElementById('history-toolbar');
const clearBtn = document.getElementById('clear-history-btn');

async function loadHistory() {
    try {
        const resp = await fetch('/api/history');
        const items = await resp.json();
        render(items);
    } catch {
        historyList.innerHTML = `<p class="empty-state">${t('err_load')}</p>`;
    }
}

function showToast(message, type = '') {
    const existing = document.querySelector('.toast');
    if (existing) existing.remove();
    const toast = document.createElement('div');
    toast.className = 'toast' + (type ? ' ' + type : '');
    toast.textContent = message;
    document.body.appendChild(toast);
    setTimeout(() => toast.remove(), 3000);
}

function render(items) {
    if (!items || items.length === 0) {
        historyEmpty.classList.remove('hidden');
        historyToolbar.classList.add('hidden');
        historyList.innerHTML = '';
        return;
    }

    historyEmpty.classList.add('hidden');
    historyToolbar.classList.remove('hidden');

    historyList.innerHTML = items.map((item, idx) => {
        const date = formatDate(item.scanned_at);
        const ip = item.ip_address || '';
        return `
        <div class="history-item" data-index="${idx}">
            <div class="history-item-info">
                <div class="history-item-url">${escHtml(item.url)}</div>
                <div class="history-item-meta">
                    <span>${date}</span>
                    ${ip ? ` · IP: ${escHtml(ip)}` : ''}
                </div>
            </div>
            <div class="history-item-actions">
                <a href="/?url=${encodeURIComponent(item.url)}" class="btn-icon reanalyze" title="${t('title_reanalyze')}">
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M21 12a9 9 0 1 1-9-9"/><path d="M21 3v6h-6"/>
                    </svg>
                </a>
                <button class="btn-icon danger" title="${t('title_delete')}" onclick="deleteEntry(${idx})">
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>
                    </svg>
                </button>
            </div>
        </div>`;
    }).join('');
}

async function deleteEntry(index) {
    if (!confirm(t('confirm_delete_entry'))) return;
    try {
        const resp = await fetch(`/api/history/${index}`, { method: 'DELETE' });
        if (!resp.ok) throw new Error();
        showToast(t('toast_entry_deleted'), 'success');
        loadHistory();
    } catch {
        showToast(t('toast_entry_delete_err'), 'error');
    }
}

clearBtn?.addEventListener('click', async () => {
    if (!confirm(t('confirm_clear_history'))) return;
    try {
        const resp = await fetch('/api/history', { method: 'DELETE' });
        if (!resp.ok) throw new Error();
        showToast(t('toast_history_cleared'), 'success');
        loadHistory();
    } catch {
        showToast(t('toast_history_clear_err'), 'error');
    }
});

function formatDate(iso) {
    try {
        const d = new Date(iso);
        const locale = document.documentElement.lang === 'en' ? 'en-US' : 'ru-RU';
        return d.toLocaleDateString(locale, { day: 'numeric', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' });
    } catch {
        return iso;
    }
}

function escHtml(str) {
    if (str == null) return '';
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}

loadHistory();
