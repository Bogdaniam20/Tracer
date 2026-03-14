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
const pdfBtn = document.getElementById('pdf-btn');

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
            resultsDiv.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }
    } catch (err) {
        showError(err.message || 'Не удалось выполнить анализ');
    } finally {
        setLoading(false);
    }
});

pdfBtn?.addEventListener('click', async () => {
    if (!lastAnalysis) return;
    pdfBtn.disabled = true;
    try {
        const resp = await fetch('/api/export/pdf', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ analysis: lastAnalysis }),
        });
        if (!resp.ok) throw new Error('Ошибка генерации PDF');
        const blob = await resp.blob();
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `analysis_${(lastAnalysis.url || 'site').replace(/[^a-zA-Z0-9.-]/g, '_').slice(0, 40)}.pdf`;
        a.click();
        URL.revokeObjectURL(url);
        showToast('PDF загружен', 'success');
    } catch {
        showToast('Не удалось скачать PDF', 'error');
    } finally {
        pdfBtn.disabled = false;
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
    renderGeoVolume(data.geo, data.page_volume);
    renderRedirects(data.redirect_info, data.url);
    renderSeo(data.seo);
    renderSiteMeta(data.site_meta, data.url);
    renderSecurity(data.security);
    renderSsl(data.ssl);
    renderDns(data.dns);
    renderHeaders(data.headers);
    renderTech(data.technologies);
    renderPerformance(data.performance);
    renderWhois(data.whois);
    renderPorts(data.ports);
    renderTraceroute(data.traceroute);
    renderCookies(data.cookies);
}

function renderGeneral(data) {
    const el = document.getElementById('general-info');
    if (!el) return;
    const items = [
        ['URL', data.url],
        ['IP-адрес', data.ip_address || '—'],
    ];
    const r = data.redirect_info || {};
    const s = data.seo || {};
    const m = data.site_meta || {};
    items.push(['Финальный URL', r.final_url || data.url || '—']);
    items.push(['Редиректов', r.redirect_count ?? 0]);
    items.push(['Title', s.title || '—']);
    items.push(['Meta description', s.meta_description || '—']);
    items.push(['Viewport', s.viewport || '—']);
    items.push(['robots.txt', m.robots_txt_exists ? '✓ Найден' : '✗ Не найден']);
    items.push(['sitemap.xml', m.sitemap_exists ? '✓ Найден' : '✗ Не найден']);
    el.innerHTML = infoItemsAll(items);
}

function renderGeoVolume(geo, pageVolume) {
    const section = document.getElementById('geo-volume-section');
    const el = document.getElementById('geo-volume-info');
    if (!section || !el) return;
    section.classList.remove('hidden');

    let html = '';
    const g = geo || {};
    html += `<div class="geo-block">
        <span class="geo-flag">${g.flag_emoji || '🌐'}</span>
        <span class="geo-country">${escHtml(g.country || 'Не определено')}</span>
    </div>`;

    const pv = pageVolume || {};
    if (pv.items && pv.items.length > 0 && pv.total_bytes > 0) {
        const typeLabels = { html: 'HTML', images: 'Изображения', css: 'CSS', js: 'JavaScript' };
        const typeColors = { html: '#22c55e', images: '#3b82f6', css: '#f59e0b', js: '#a855f7' };
        const rows = pv.items.map((item, i) => {
            const sizeMb = (item.bytes / 1048576).toFixed(2);
            const sizeKb = (item.bytes / 1024).toFixed(2);
            const sizeStr = item.bytes >= 1048576 ? `${sizeMb} Мбайт` : `${sizeKb} КБ`;
            return `<tr>
                <td>${escHtml(typeLabels[item.type] || item.type)}</td>
                <td>${sizeStr}</td>
                <td>${item.percent.toFixed(2)} %</td>
            </tr>`;
        }).join('');
        html += `
            <div class="volume-block">
                <h4 class="volume-title">Объём страницы:</h4>
                <div class="volume-content">
                    <table class="volume-table">
                        <tbody>${rows}</tbody>
                        <tfoot><tr><td><strong>всего</strong></td><td><strong>${formatBytes(pv.total_bytes)}</strong></td><td>100 %</td></tr></tfoot>
                    </table>
                    <div class="volume-chart-wrap">
                        <div class="volume-pie" style="background: ${(() => {
                            const nonZero = pv.items.filter(x => x.percent > 0);
                            if (nonZero.length === 0) return 'var(--border)';
                            return 'conic-gradient(' + nonZero.map((item, i) => {
                                const prev = nonZero.slice(0, i).reduce((s, x) => s + x.percent, 0);
                                const color = typeColors[item.type] || '#6b7280';
                                return `${color} ${prev}% ${prev + item.percent}%`;
                            }).join(', ') + ')';
                        })()}"></div>
                        <div class="volume-legend">
                            ${pv.items.map(item => `
                                <div class="volume-legend-item">
                                    <span class="volume-legend-dot" style="background:${typeColors[item.type] || '#6b7280'}"></span>
                                    <span>${escHtml(typeLabels[item.type] || item.type)}</span>
                                </div>
                            `).join('')}
                        </div>
                    </div>
                </div>
            </div>`;
    } else if (!html) {
        html = '<p class="empty-state">Данные недоступны</p>';
    }
    el.innerHTML = html;
}

function renderRedirects(redir, originalUrl) {
    const section = document.getElementById('redirect-section');
    const el = document.getElementById('redirect-info');
    if (!section || !el) return;
    section.classList.remove('hidden');

    const r = redir || {};
    const finalUrl = r.final_url || originalUrl || '—';
    const count = r.redirect_count ?? 0;
    const items = [
        ['Исходный URL', originalUrl || '—'],
        ['Финальный URL', finalUrl],
        ['Количество редиректов', count],
    ];
    let html = `<div class="info-grid">${infoItemsAll(items)}</div>`;

    if (count > 0 && r.chain && r.chain.length > 0) {
        html += `<h4 style="margin-top:1rem;margin-bottom:0.5rem;font-size:0.9rem">Цепочка редиректов</h4><ol class="redirect-chain">${r.chain.map(s => `
            <li><span class="status-badge">${s.status_code}</span> ${escHtml(s.url)}</li>
        `).join('')}</ol>`;
    } else if (count === 0) {
        html += '<p class="empty-state positive" style="margin-top:0.75rem">Прямой доступ без редиректов</p>';
    }
    el.innerHTML = html;
}

function renderSeo(seo) {
    const section = document.getElementById('seo-section');
    const el = document.getElementById('seo-info');
    if (!section || !el) return;
    section.classList.remove('hidden');

    const s = seo || {};
    const items = [
        ['Title', s.title || '—'],
        ['Meta description', s.meta_description || '—'],
        ['Open Graph: title', s.og_title || '—'],
        ['Open Graph: description', s.og_description || '—'],
        ['Open Graph: image', s.og_image || '—'],
        ['Open Graph: type', s.og_type || '—'],
        ['Twitter Card', s.twitter_card || '—'],
        ['Twitter: title', s.twitter_title || '—'],
        ['Viewport', s.viewport || '—'],
        ['Canonical URL', s.canonical_url || '—'],
    ];
    el.innerHTML = infoItemsAll(items);
}

function renderSiteMeta(meta, baseUrl) {
    const section = document.getElementById('site-meta-section');
    const el = document.getElementById('site-meta-info');
    if (!section || !el) return;
    section.classList.remove('hidden');

    const m = meta || {};
    let base = '';
    try {
        if (baseUrl) base = new URL(baseUrl).origin;
    } catch (_) {}
    const robotsLabel = base
        ? (m.robots_txt_exists ? `✓ Найден (${base}/robots.txt)` : `✗ Не найден (${base}/robots.txt)`)
        : (m.robots_txt_exists ? '✓ Найден' : '✗ Не найден');
    const items = [
        ['robots.txt', robotsLabel],
        ['sitemap.xml', m.sitemap_exists ? '✓ Найден' : '✗ Не найден'],
        ['URL sitemap', m.sitemap_url || '—'],
    ];
    let html = `<div class="info-grid">${infoItemsAll(items)}</div>`;
    if (m.robots_txt_preview) {
        html += `<h4 style="margin-top:1rem;margin-bottom:0.5rem;font-size:0.9rem">Содержимое robots.txt</h4><pre class="robots-preview">${escHtml(m.robots_txt_preview)}</pre>`;
    } else if (m.robots_txt_exists) {
        html += '<p class="empty-state" style="margin-top:0.75rem">Файл найден, но содержимое пустое</p>';
    } else {
        html += '<p class="empty-state" style="margin-top:0.75rem;color:var(--text-muted);font-size:0.9rem">robots.txt управляет доступом поисковых роботов к сайту</p>';
    }
    el.innerHTML = html;
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
        ['DNS lookup', perf.dns_lookup_ms ? perf.dns_lookup_ms + ' мс' : '—'],
        ['TCP connect', perf.connect_ms ? perf.connect_ms + ' мс' : '—'],
        ['TTFB', perf.ttfb_ms ? perf.ttfb_ms + ' мс' : '—'],
        ['Общее время', perf.total_ms ? perf.total_ms + ' мс' : '—'],
        ['Размер контента', perf.content_size_bytes ? formatBytes(perf.content_size_bytes) : '—'],
        ['Редиректы', perf.redirect_count ?? '—'],
        ['HTTP версия', perf.http_version || '—'],
        ['Сжатие', perf.content_encoding || 'нет'],
        ['Cache-Control', perf.cache_control || '—'],
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
    const el = document.getElementById('ports-info');
    if (!section || !el) return;
    section.classList.remove('hidden');

    if (!ports || ports.length === 0) {
        el.innerHTML = '<p class="empty-state">Открытые порты не обнаружены</p>';
        return;
    }

    const sorted = [...ports].sort((a, b) => a.port - b.port);
    const useTable = sorted.length > 12;

    if (useTable) {
        el.innerHTML = `
            <div class="ports-scroll">
                <table class="ports-table">
                    <thead><tr><th>Порт</th><th>Сервис</th></tr></thead>
                    <tbody>
                        ${sorted.map(p => `
                            <tr>
                                <td class="port-num-cell"><span class="port-dot"></span> ${p.port}</td>
                                <td>${escHtml(p.service)}</td>
                            </tr>
                        `).join('')}
                    </tbody>
                </table>
            </div>
        `;
    } else {
        el.innerHTML = `
            <div class="ports-grid">
                ${sorted.map(p => `
                    <div class="port-item">
                        <span class="port-dot"></span>
                        <span class="port-number">${p.port}</span>
                        <span class="port-service">${escHtml(p.service)}</span>
                    </div>
                `).join('')}
            </div>
        `;
    }
}

function renderTraceroute(tr) {
    const section = document.getElementById('traceroute-section');
    section.classList.remove('hidden');
    if (!tr) {
        document.getElementById('traceroute-info').innerHTML = '<p class="empty-state warning">Traceroute недоступен</p>';
        return;
    }

    const el = document.getElementById('traceroute-info');
    if (tr.error) {
        el.innerHTML = `<p class="empty-state warning">${escHtml(tr.error)}</p>`;
        return;
    }
    if (!tr.hops || tr.hops.length === 0) {
        el.innerHTML = '<p class="empty-state">Маршрут не определён</p>';
        return;
    }

    el.innerHTML = `
        <p class="traceroute-target">Цель: ${escHtml(tr.target)}</p>
        <ol class="traceroute-list">
            ${tr.hops.map(h => {
                const rtt = h.rtt_ms && h.rtt_ms.length > 0
                    ? h.rtt_ms.map(m => m + ' мс').join(' / ')
                    : '—';
                return `<li>
                    <span class="hop-num">${h.hop}</span>
                    <span class="hop-ip mono">${escHtml(h.ip)}</span>
                    ${h.hostname ? `<span class="hop-host">${escHtml(h.hostname)}</span>` : ''}
                    <span class="hop-rtt">${rtt}</span>
                </li>`;
            }).join('')}
        </ol>
    `;
}

function renderCookies(cookies) {
    const section = document.getElementById('cookies-section');
    if (!cookies) { section.classList.add('hidden'); return; }
    section.classList.remove('hidden');

    const el = document.getElementById('cookies-info');
    if (!cookies.cookies || cookies.cookies.length === 0) {
        el.innerHTML = '<p class="empty-state">Cookies не установлены</p>';
        return;
    }

    const summaryHtml = cookies.summary && cookies.summary.length > 0
        ? `<ul class="cookies-summary">${cookies.summary.map(s => `<li class="${s.startsWith('✓') ? 'positive' : 'warning'}">${escHtml(s)}</li>`).join('')}</ul>`
        : '';

    el.innerHTML = `
        ${summaryHtml}
        <table class="cookies-table">
            <thead><tr><th>Cookie</th><th>Secure</th><th>HttpOnly</th><th>SameSite</th><th>Проблемы</th></tr></thead>
            <tbody>
                ${cookies.cookies.map(c => `
                    <tr>
                        <td class="mono">${escHtml(c.name)}</td>
                        <td>${c.secure ? '✓' : '✗'}</td>
                        <td>${c.httponly ? '✓' : '✗'}</td>
                        <td>${c.samesite || '—'}</td>
                        <td>${c.issues && c.issues.length > 0 ? c.issues.map(i => escHtml(i)).join(', ') : '—'}</td>
                    </tr>
                `).join('')}
            </tbody>
        </table>
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

function infoItemsAll(pairs) {
    return pairs
        .map(([label, value]) => `
            <div class="info-item">
                <span class="info-label">${escHtml(label)}</span>
                <span class="info-value mono">${escHtml(String(value ?? '—'))}</span>
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

// Обработка ?url= при переходе с кнопки "Повторный анализ" в сохранённых
const urlParams = new URLSearchParams(window.location.search);
const urlFromQuery = urlParams.get('url');
if (urlFromQuery) {
    urlInput.value = urlFromQuery;
    form.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
    history.replaceState({}, '', window.location.pathname);
}
