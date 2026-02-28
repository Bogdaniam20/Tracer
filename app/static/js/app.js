const form = document.getElementById('analyze-form');
const urlInput = document.getElementById('url-input');
const analyzeBtn = document.getElementById('analyze-btn');
const btnText = analyzeBtn.querySelector('.btn-text');
const btnLoader = analyzeBtn.querySelector('.btn-loader');
const errorBox = document.getElementById('error-box');
const resultsDiv = document.getElementById('results');
const saveBar = document.getElementById('save-bar');
const saveBtn = document.getElementById('save-btn');
const saveNote = document.getElementById('save-note');

let lastAnalysis = null;
let lastUrl = '';

form.addEventListener('submit', async (e) => {
    e.preventDefault();
    const url = urlInput.value.trim();
    if (!url) return;

    setLoading(true);
    hideError();
    resultsDiv.classList.add('hidden');
    saveBar.classList.add('hidden');
    lastAnalysis = null;

    try {
        const resp = await fetch('/api/analyze', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ url }),
        });

        if (!resp.ok) {
            throw new Error(`Ошибка сервера: ${resp.status}`);
        }

        const data = await resp.json();

        if (data.error) {
            showError(data.error);
        } else {
            lastAnalysis = data;
            lastUrl = url;
            renderResults(data);
            resultsDiv.classList.remove('hidden');
            saveBar.classList.remove('hidden');
            resetSaveBtn();
        }
    } catch (err) {
        showError(err.message || 'Не удалось выполнить анализ');
    } finally {
        setLoading(false);
    }
});

saveBtn.addEventListener('click', async () => {
    if (!lastAnalysis) return;

    saveBtn.disabled = true;

    try {
        const resp = await fetch('/api/saved', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                url: lastUrl,
                analysis: lastAnalysis,
                note: saveNote.value.trim(),
            }),
        });

        if (!resp.ok) throw new Error('Ошибка сохранения');

        saveBtn.classList.add('saved');
        saveBtn.innerHTML = `
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <polyline points="20 6 9 17 4 12"/>
            </svg>
            Сохранено
        `;
        showToast('Сайт сохранён', 'success');
        updateBadge();
    } catch {
        saveBtn.disabled = false;
        showToast('Не удалось сохранить', 'error');
    }
});

function resetSaveBtn() {
    saveBtn.disabled = false;
    saveBtn.classList.remove('saved');
    saveBtn.innerHTML = `
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M19 21l-7-5-7 5V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2z"/>
        </svg>
        Сохранить
    `;
    saveNote.value = '';
}

function updateBadge() {
    fetch('/api/saved').then(r => r.json()).then(data => {
        const badge = document.getElementById('saved-count');
        if (badge && data.length > 0) {
            badge.textContent = data.length;
            badge.style.display = '';
        }
    }).catch(() => {});
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

function setLoading(loading) {
    analyzeBtn.disabled = loading;
    btnText.classList.toggle('hidden', loading);
    btnLoader.classList.toggle('hidden', !loading);
}

function showError(msg) {
    errorBox.textContent = msg;
    errorBox.classList.remove('hidden');
}

function hideError() {
    errorBox.classList.add('hidden');
}

function renderResults(data) {
    renderGeneral(data);
    renderSecurity(data.security);
    renderSsl(data.ssl);
    renderDns(data.dns);
    renderHeaders(data.headers);
    renderTech(data.technologies);
    renderPerformance(data.performance);
    renderWhois(data.whois);
    renderPorts(data.ports);
}

function renderGeneral(data) {
    const el = document.getElementById('general-info');
    el.innerHTML = infoItems([
        ['URL', data.url],
        ['IP-адрес', data.ip_address || '—'],
    ]);
}

function renderSecurity(sec) {
    const section = document.getElementById('security-section');
    if (!sec) { section.classList.add('hidden'); return; }
    section.classList.remove('hidden');

    const gradeEl = document.getElementById('security-grade');
    gradeEl.textContent = sec.grade;
    gradeEl.className = 'grade-circle ' + gradeClass(sec.grade);

    const fill = document.getElementById('score-fill');
    const pct = Math.min((sec.score / sec.max_score) * 100, 100);
    fill.style.width = pct + '%';
    fill.style.background = scoreColor(pct);

    document.getElementById('score-text').textContent = `${sec.score} / ${sec.max_score}`;

    const list = document.getElementById('security-details');
    list.innerHTML = sec.details.map(d => {
        let cls = 'negative';
        if (d.startsWith('[+')) cls = 'positive';
        else if (d.startsWith('[!')) cls = 'warning';
        return `<li class="${cls}">${escHtml(d)}</li>`;
    }).join('');
}

function renderSsl(ssl) {
    const section = document.getElementById('ssl-section');
    if (!ssl) { section.classList.add('hidden'); return; }
    section.classList.remove('hidden');

    document.getElementById('ssl-info').innerHTML = infoItems([
        ['Издатель', ssl.issuer],
        ['Субъект', ssl.subject],
        ['Протокол', ssl.protocol_version],
        ['Шифр', ssl.cipher_suite],
        ['Размер ключа', ssl.key_size ? ssl.key_size + ' бит' : '—'],
        ['Действителен с', ssl.not_before],
        ['Действителен до', ssl.not_after],
        ['Дней до истечения', ssl.days_until_expiry || '—'],
        ['SAN', ssl.san?.join(', ') || '—'],
    ]);
}

function renderDns(dns) {
    const section = document.getElementById('dns-section');
    if (!dns) { section.classList.add('hidden'); return; }
    section.classList.remove('hidden');

    const el = document.getElementById('dns-info');
    const groups = [
        ['A', dns.a_records],
        ['AAAA', dns.aaaa_records],
        ['MX', dns.mx_records],
        ['NS', dns.ns_records],
        ['TXT', dns.txt_records],
        ['CNAME', dns.cname_records],
    ].filter(([, recs]) => recs && recs.length > 0);

    if (groups.length === 0) {
        el.innerHTML = '<p class="empty-state">Записи не найдены</p>';
        return;
    }

    el.innerHTML = groups.map(([type, recs]) => `
        <div class="dns-group">
            <h3>${type}</h3>
            <ul>${recs.map(r => `<li>${escHtml(r)}</li>`).join('')}</ul>
        </div>
    `).join('');
}

function renderHeaders(hdrs) {
    const section = document.getElementById('headers-section');
    if (!hdrs) { section.classList.add('hidden'); return; }
    section.classList.remove('hidden');

    const all = hdrs.all_headers || {};
    const rows = Object.entries(all);

    if (rows.length === 0) {
        document.getElementById('headers-info').innerHTML = '<p class="empty-state">Заголовки недоступны</p>';
        return;
    }

    document.getElementById('headers-info').innerHTML = `
        <table>
            <thead><tr><th>Заголовок</th><th>Значение</th></tr></thead>
            <tbody>
                ${rows.map(([k, v]) => `<tr><td>${escHtml(k)}</td><td>${escHtml(v)}</td></tr>`).join('')}
            </tbody>
        </table>
    `;
}

function renderTech(tech) {
    const section = document.getElementById('tech-section');
    if (!tech) { section.classList.add('hidden'); return; }
    section.classList.remove('hidden');

    const el = document.getElementById('tech-info');
    const allTechs = [
        ...(tech.frameworks || []).map(t => ({ name: t, type: 'framework' })),
        ...(tech.technologies || []).map(t => ({ name: t, type: 'tech' })),
    ];

    if (allTechs.length === 0) {
        el.innerHTML = '<p class="empty-state">Технологии не определены</p>';
        return;
    }

    el.innerHTML = `
        <div class="tech-tags">
            ${allTechs.map(t => `<span class="tech-tag ${t.type}">${escHtml(t.name)}</span>`).join('')}
        </div>
    `;
}

function renderPerformance(perf) {
    const section = document.getElementById('perf-section');
    if (!perf) { section.classList.add('hidden'); return; }
    section.classList.remove('hidden');

    document.getElementById('perf-info').innerHTML = infoItems([
        ['Общее время', perf.total_ms ? perf.total_ms + ' мс' : '—'],
        ['TTFB', perf.ttfb_ms ? perf.ttfb_ms + ' мс' : '—'],
        ['Размер контента', perf.content_size_bytes ? formatBytes(perf.content_size_bytes) : '—'],
        ['Редиректы', perf.redirect_count ?? '—'],
    ]);
}

function renderWhois(w) {
    const section = document.getElementById('whois-section');
    if (!w) { section.classList.add('hidden'); return; }
    section.classList.remove('hidden');

    document.getElementById('whois-info').innerHTML = infoItems([
        ['Домен', w.domain_name],
        ['Регистратор', w.registrar],
        ['Дата создания', w.creation_date],
        ['Дата истечения', w.expiration_date],
        ['NS серверы', w.name_servers?.join(', ') || '—'],
        ['Страна', w.country || '—'],
    ]);
}

function renderPorts(ports) {
    const section = document.getElementById('ports-section');
    if (!ports || ports.length === 0) {
        section.classList.remove('hidden');
        document.getElementById('ports-info').innerHTML = '<p class="empty-state">Открытые порты не обнаружены</p>';
        return;
    }
    section.classList.remove('hidden');

    document.getElementById('ports-info').innerHTML = `
        <div class="ports-grid">
            ${ports.map(p => `
                <div class="port-item">
                    <span class="port-dot"></span>
                    <span class="port-number">${p.port}</span>
                    <span class="port-service">${escHtml(p.service)}</span>
                </div>
            `).join('')}
        </div>
    `;
}

function infoItems(pairs) {
    return pairs
        .filter(([, v]) => v !== undefined && v !== null && v !== '')
        .map(([label, value]) => `
            <div class="info-item">
                <span class="info-label">${escHtml(label)}</span>
                <span class="info-value mono">${escHtml(String(value))}</span>
            </div>
        `).join('');
}

function gradeClass(grade) {
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
