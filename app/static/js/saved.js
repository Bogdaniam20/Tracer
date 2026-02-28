const savedList = document.getElementById('saved-list');
const savedEmpty = document.getElementById('saved-empty');
const modalOverlay = document.getElementById('modal-overlay');
const modalTitle = document.getElementById('modal-title');
const modalBody = document.getElementById('modal-body');
const modalClose = document.getElementById('modal-close');

let sites = [];

async function loadSaved() {
    try {
        const resp = await fetch('/api/saved');
        sites = await resp.json();
        render();
    } catch {
        savedList.innerHTML = '<p class="empty-state">Ошибка загрузки</p>';
    }
}

function render() {
    if (sites.length === 0) {
        savedEmpty.classList.remove('hidden');
        savedList.innerHTML = '';
        return;
    }

    savedEmpty.classList.add('hidden');
    savedList.innerHTML = sites.map(s => {
        const grade = s.analysis?.security?.grade || '?';
        const score = s.analysis?.security?.score ?? '—';
        const ip = s.analysis?.ip_address || '';
        const date = formatDate(s.saved_at);

        return `
        <div class="saved-card" data-id="${s.id}">
            <div class="saved-card-grade ${gradeClass(grade)}">${escHtml(grade)}</div>
            <div class="saved-card-info">
                <div class="saved-card-url">${escHtml(s.url)}</div>
                <div class="saved-card-meta">
                    <span>${date}</span>
                    ${ip ? `<span>IP: ${escHtml(ip)}</span>` : ''}
                    <span>Score: ${score}/100</span>
                </div>
                ${s.note ? `<div class="saved-card-note">${escHtml(s.note)}</div>` : ''}
            </div>
            <div class="saved-card-actions">
                <button class="btn-icon view" title="Просмотр" onclick="viewSite('${s.id}')">
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/>
                        <circle cx="12" cy="12" r="3"/>
                    </svg>
                </button>
                <button class="btn-icon reanalyze" title="Повторный анализ" onclick="reanalyze('${escAttr(s.url)}')">
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M21 12a9 9 0 1 1-9-9"/><path d="M21 3v6h-6"/>
                    </svg>
                </button>
                <button class="btn-icon danger" title="Удалить" onclick="deleteSite('${s.id}')">
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <polyline points="3 6 5 6 21 6"/>
                        <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>
                    </svg>
                </button>
            </div>
        </div>`;
    }).join('');
}

function viewSite(id) {
    const site = sites.find(s => s.id === id);
    if (!site) return;

    const a = site.analysis;
    modalTitle.textContent = site.url;

    let html = '';

    if (a.security) {
        const pct = Math.min((a.security.score / a.security.max_score) * 100, 100);
        html += `
        <div class="card">
            <h2>Безопасность</h2>
            <div class="security-overview">
                <div class="grade-circle ${gradeClass(a.security.grade)}">${a.security.grade}</div>
                <div class="score-bar-container">
                    <div class="score-bar">
                        <div class="score-fill" style="width:${pct}%;background:${scoreColor(pct)}"></div>
                    </div>
                    <span class="score-text">${a.security.score} / ${a.security.max_score}</span>
                </div>
            </div>
            <ul class="details-list">
                ${a.security.details.map(d => {
                    let cls = 'negative';
                    if (d.startsWith('[+')) cls = 'positive';
                    else if (d.startsWith('[!')) cls = 'warning';
                    return `<li class="${cls}">${escHtml(d)}</li>`;
                }).join('')}
            </ul>
        </div>`;
    }

    html += `
    <div class="card">
        <h2>Общая информация</h2>
        <div class="info-grid">
            ${infoItem('URL', a.url)}
            ${infoItem('IP-адрес', a.ip_address)}
        </div>
    </div>`;

    if (a.ssl && a.ssl.issuer) {
        html += `
        <div class="card">
            <h2>SSL / TLS</h2>
            <div class="info-grid">
                ${infoItem('Издатель', a.ssl.issuer)}
                ${infoItem('Протокол', a.ssl.protocol_version)}
                ${infoItem('Шифр', a.ssl.cipher_suite)}
                ${infoItem('Действителен до', a.ssl.not_after)}
                ${infoItem('Дней до истечения', a.ssl.days_until_expiry)}
            </div>
        </div>`;
    }

    if (a.performance) {
        html += `
        <div class="card">
            <h2>Производительность</h2>
            <div class="info-grid">
                ${infoItem('Общее время', a.performance.total_ms ? a.performance.total_ms + ' мс' : null)}
                ${infoItem('TTFB', a.performance.ttfb_ms ? a.performance.ttfb_ms + ' мс' : null)}
                ${infoItem('Размер контента', a.performance.content_size_bytes ? formatBytes(a.performance.content_size_bytes) : null)}
            </div>
        </div>`;
    }

    if (a.whois && a.whois.domain_name) {
        html += `
        <div class="card">
            <h2>WHOIS</h2>
            <div class="info-grid">
                ${infoItem('Домен', a.whois.domain_name)}
                ${infoItem('Регистратор', a.whois.registrar)}
                ${infoItem('Дата создания', a.whois.creation_date)}
                ${infoItem('Дата истечения', a.whois.expiration_date)}
            </div>
        </div>`;
    }

    if (a.ports && a.ports.length > 0) {
        html += `
        <div class="card">
            <h2>Открытые порты</h2>
            <div class="ports-grid">
                ${a.ports.map(p => `
                    <div class="port-item">
                        <span class="port-dot"></span>
                        <span class="port-number">${p.port}</span>
                        <span class="port-service">${escHtml(p.service)}</span>
                    </div>
                `).join('')}
            </div>
        </div>`;
    }

    modalBody.innerHTML = html;
    modalOverlay.classList.remove('hidden');
    document.body.style.overflow = 'hidden';
}

async function deleteSite(id) {
    if (!confirm('Удалить сохранённый сайт?')) return;

    try {
        const resp = await fetch(`/api/saved/${id}`, { method: 'DELETE' });
        if (!resp.ok) throw new Error();
        sites = sites.filter(s => s.id !== id);
        render();
        updateBadge();
        showToast('Сайт удалён', 'success');
    } catch {
        showToast('Ошибка удаления', 'error');
    }
}

function reanalyze(url) {
    window.location.href = `/?url=${encodeURIComponent(url)}`;
}

function closeModal() {
    modalOverlay.classList.add('hidden');
    document.body.style.overflow = '';
}

modalClose.addEventListener('click', closeModal);
modalOverlay.addEventListener('click', (e) => {
    if (e.target === modalOverlay) closeModal();
});
document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') closeModal();
});

function updateBadge() {
    const badge = document.getElementById('saved-count');
    if (badge) {
        if (sites.length > 0) {
            badge.textContent = sites.length;
            badge.style.display = '';
        } else {
            badge.style.display = 'none';
        }
    }
}

function infoItem(label, value) {
    if (!value && value !== 0) return '';
    return `
        <div class="info-item">
            <span class="info-label">${escHtml(label)}</span>
            <span class="info-value mono">${escHtml(String(value))}</span>
        </div>`;
}

function gradeClass(grade) {
    if (!grade) return 'grade-f';
    if (grade.startsWith('A')) return 'grade-a';
    if (grade === 'B') return 'grade-b';
    if (grade === 'C') return 'grade-c';
    if (grade === 'D') return 'grade-d';
    return 'grade-f';
}

function scoreColor(pct) {
    if (pct >= 80) return 'var(--grade-a)';
    if (pct >= 60) return 'var(--grade-b)';
    if (pct >= 40) return 'var(--grade-c)';
    if (pct >= 20) return 'var(--grade-d)';
    return 'var(--grade-f)';
}

function formatDate(iso) {
    try {
        const d = new Date(iso);
        return d.toLocaleDateString('ru-RU', { day: 'numeric', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' });
    } catch {
        return iso;
    }
}

function formatBytes(bytes) {
    if (bytes < 1024) return bytes + ' Б';
    if (bytes < 1048576) return (bytes / 1024).toFixed(1) + ' КБ';
    return (bytes / 1048576).toFixed(2) + ' МБ';
}

function escHtml(str) {
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}

function escAttr(str) {
    return str.replace(/'/g, "\\'").replace(/"/g, '&quot;');
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

loadSaved();
