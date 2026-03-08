const historyList = document.getElementById('history-list');
const historyEmpty = document.getElementById('history-empty');

async function loadHistory() {
    try {
        const resp = await fetch('/api/history');
        const items = await resp.json();
        render(items);
    } catch {
        historyList.innerHTML = '<p class="empty-state">Ошибка загрузки</p>';
    }
}

function render(items) {
    if (!items || items.length === 0) {
        historyEmpty.classList.remove('hidden');
        historyList.innerHTML = '';
        return;
    }

    historyEmpty.classList.add('hidden');
    historyList.innerHTML = items.map(item => {
        const date = formatDate(item.scanned_at);
        const ip = item.ip_address || '';
        return `
        <div class="saved-card history-card">
            <div class="saved-card-info">
                <div class="saved-card-url">${escHtml(item.url)}</div>
                <div class="saved-card-meta">
                    <span>${date}</span>
                    ${ip ? `<span>IP: ${escHtml(ip)}</span>` : ''}
                </div>
            </div>
            <div class="saved-card-actions">
                <a href="/?url=${encodeURIComponent(item.url)}" class="btn-icon view" title="Повторный анализ">
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M21 12a9 9 0 1 1-9-9"/><path d="M21 3v6h-6"/>
                    </svg>
                </a>
            </div>
        </div>`;
    }).join('');
}

function formatDate(iso) {
    try {
        const d = new Date(iso);
        return d.toLocaleDateString('ru-RU', { day: 'numeric', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' });
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
