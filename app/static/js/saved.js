const t = (key) => (window.__t && window.__t[key]) || key;

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
        savedList.innerHTML = `<p class="empty-state">${t('err_load')}</p>`;
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
                <button class="btn-icon view" title="${t('title_view')}" onclick="viewSite('${s.id}')">
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/>
                        <circle cx="12" cy="12" r="3"/>
                    </svg>
                </button>
                <button class="btn-icon edit-note" title="${t('title_edit_note')}" onclick="editNote('${s.id}')">
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/>
                        <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/>
                    </svg>
                </button>
                <button class="btn-icon reanalyze" title="${t('title_reanalyze')}" data-url="${encodeURIComponent(s.url)}" onclick="reanalyze(this)">
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M21 12a9 9 0 1 1-9-9"/><path d="M21 3v6h-6"/>
                    </svg>
                </button>
                <button class="btn-icon danger" title="${t('title_delete')}" onclick="deleteSite('${s.id}')">
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

    // 1. Общая информация
    const r = a.redirect_info || {}, s = a.seo || {}, m = a.site_meta || {};
    const found = t('label_found'), notFound = t('label_not_found');
    const generalItems = [
        [t('label_url'), a.url],
        [t('label_ip'), a.ip_address || '—'],
        [t('label_final_url'), r.final_url || a.url || '—'],
        [t('label_redirect_count'), r.redirect_count ?? 0],
        [t('label_title'), s.title || '—'],
        [t('label_meta_desc'), s.meta_description || '—'],
        [t('label_viewport'), s.viewport || '—'],
        ['robots.txt', m.robots_txt_exists ? `✓ ${found}` : `✗ ${notFound}`],
        ['sitemap.xml', m.sitemap_exists ? `✓ ${found}` : `✗ ${notFound}`],
    ];
    html += `<div class="card"><h2>${t('section_general')}</h2><div class="info-grid">${infoItemsAll(generalItems)}</div></div>`;

    // 1.5 Превью (скриншот)
    if (a.screenshot) {
        html += `<div class="card"><h2>${t('section_screenshot')}</h2><div class="screenshot-preview"><a href="data:image/png;base64,${a.screenshot}" target="_blank" rel="noopener" class="screenshot-link"><img src="data:image/png;base64,${a.screenshot}" alt="${t('section_screenshot')}" class="screenshot-img"></a></div></div>`;
    }

    // 2. Расположение и объём страницы
    const g = a.geo || {};
    html += `<div class="card"><h2>${t('section_geo_volume')}</h2>
        <div class="geo-block">
            <span class="geo-flag">${g.flag_emoji || '🌐'}</span>
            <span class="geo-country">${escHtml(g.country || t('empty_undefined'))}</span>
        </div>`;
    const pv = a.page_volume || {};
    if (pv.items && pv.items.length > 0 && pv.total_bytes > 0) {
        const typeLabels = { html: t('label_html'), images: t('label_images'), css: t('label_css'), js: t('label_js') };
        const typeColors = { html: '#22c55e', images: '#3b82f6', css: '#f59e0b', js: '#a855f7' };
        const rows = pv.items.map(item => {
            const sizeStr = item.bytes >= 1048576 ? (item.bytes / 1048576).toFixed(2) + ' Мбайт' : (item.bytes / 1024).toFixed(2) + ' КБ';
            return `<tr><td>${escHtml(typeLabels[item.type] || item.type)}</td><td>${sizeStr}</td><td>${item.percent.toFixed(2)} %</td></tr>`;
        }).join('');
        const nonZero = pv.items.filter(x => x.percent > 0);
        const pieBg = nonZero.length === 0 ? 'var(--border)' : 'conic-gradient(' + nonZero.map((item, i) => {
            const prev = nonZero.slice(0, i).reduce((acc, x) => acc + x.percent, 0);
            return `${typeColors[item.type] || '#6b7280'} ${prev}% ${prev + item.percent}%`;
        }).join(', ') + ')';
        html += `<div class="volume-block"><h4 class="volume-title">${t('label_volume')}</h4>
            <div class="volume-content">
                <table class="volume-table"><tbody>${rows}</tbody><tfoot><tr><td><strong>${t('label_total')}</strong></td><td><strong>${formatBytes(pv.total_bytes)}</strong></td><td>100 %</td></tr></tfoot></table>
                <div class="volume-chart-wrap">
                    <div class="volume-pie" style="background:${pieBg}"></div>
                    <div class="volume-legend">${pv.items.map(item => `<div class="volume-legend-item"><span class="volume-legend-dot" style="background:${typeColors[item.type] || '#6b7280'}"></span><span>${escHtml(typeLabels[item.type] || item.type)}</span></div>`).join('')}</div>
                </div>
            </div>
        </div>`;
    }
    html += `</div>`;

    // 3. Редиректы
    const redirItems = [[t('label_original_url'), a.url], [t('label_final_url'), r.final_url || a.url || '—'], [t('label_redirect_count'), r.redirect_count ?? 0]];
    let redirHtml = `<div class="card"><h2>${t('section_redirects')}</h2><div class="info-grid">${infoItemsAll(redirItems)}</div>`;
    if (r.redirect_count > 0 && r.chain && r.chain.length > 0) {
        redirHtml += `<h4 style="margin-top:1rem;margin-bottom:0.5rem;font-size:0.9rem">${t('label_redirect_chain')}</h4><ol class="redirect-chain">${r.chain.map(step => `<li><span class="status-badge">${step.status_code}</span> ${escHtml(step.url)}</li>`).join('')}</ol>`;
    } else {
        redirHtml += `<p class="empty-state positive" style="margin-top:0.75rem">${t('empty_direct')}</p>`;
    }
    html += redirHtml + '</div>';

    // 4. SEO
    const seoItems = [[t('label_title'), s.title || '—'], [t('label_meta_desc'), s.meta_description || '—'], ['Open Graph: title', s.og_title || '—'], ['Open Graph: description', s.og_description || '—'], ['Open Graph: image', s.og_image || '—'], [t('label_viewport'), s.viewport || '—'], ['Canonical URL', s.canonical_url || '—']];
    html += `<div class="card"><h2>${t('section_seo')}</h2><div class="info-grid">${infoItemsAll(seoItems)}</div></div>`;

    // 5. robots.txt и sitemap
    let base = ''; try { if (a.url) base = new URL(a.url).origin; } catch (_) {}
    const robotsLabel = base ? (m.robots_txt_exists ? `✓ ${found} (${base}/robots.txt)` : `✗ ${notFound} (${base}/robots.txt)`) : (m.robots_txt_exists ? `✓ ${found}` : `✗ ${notFound}`);
    const metaItems = [['robots.txt', robotsLabel], ['sitemap.xml', m.sitemap_exists ? `✓ ${found}` : `✗ ${notFound}`], ['URL sitemap', m.sitemap_url || '—']];
    let metaHtml = `<div class="card"><h2>${t('section_site_meta')}</h2><div class="info-grid">${infoItemsAll(metaItems)}</div>`;
    if (m.robots_txt_preview) metaHtml += `<h4 style="margin-top:1rem;font-size:0.9rem">${t('label_robots_content')}</h4><pre class="robots-preview">${escHtml(m.robots_txt_preview)}</pre>`;
    html += metaHtml + '</div>';

    // 6. Безопасность
    if (a.security) {
        const pct = Math.min((a.security.score / a.security.max_score) * 100, 100);
        html += `<div class="card"><h2>${t('section_security')}</h2><div class="security-overview">
            <div class="grade-circle ${gradeClass(a.security.grade)}">${a.security.grade}</div>
            <div class="score-bar-container"><div class="score-bar"><div class="score-fill" style="width:${pct}%;background:${scoreColor(pct)}"></div></div><span class="score-text">${a.security.score} / ${a.security.max_score}</span></div>
        </div><ul class="details-list">${a.security.details.map(d => {
            let cls = 'negative'; if (d.startsWith('[+')) cls = 'positive'; else if (d.startsWith('[!')) cls = 'warning';
            return `<li class="${cls}">${escHtml(d)}</li>`;
        }).join('')}</ul></div>`;
    }

    // 7. SSL/TLS
    if (a.ssl) {
        const sslItems = [[t('label_issuer'), a.ssl.issuer], [t('label_subject'), a.ssl.subject], [t('label_protocol'), a.ssl.protocol_version], [t('label_cipher'), a.ssl.cipher_suite], [t('label_valid_to'), a.ssl.not_after], [t('label_days_expiry'), a.ssl.days_until_expiry || '—']];
        html += `<div class="card"><h2>${t('section_ssl')}</h2><div class="info-grid">${infoItemsAll(sslItems)}</div></div>`;
    }

    // 8. DNS
    const dns = a.dns || {};
    const dnsGroups = [['A', dns.a_records], ['AAAA', dns.aaaa_records], ['MX', dns.mx_records], ['NS', dns.ns_records], ['TXT', dns.txt_records], ['CNAME', dns.cname_records]].filter(([, recs]) => recs && recs.length > 0);
    if (dnsGroups.length > 0) {
        html += `<div class="card"><h2>${t('section_dns')}</h2><div class="dns-records">${dnsGroups.map(([type, recs]) => `<div class="dns-group"><h3>${type}</h3><ul>${recs.map(r => `<li>${escHtml(r)}</li>`).join('')}</ul></div>`).join('')}</div></div>`;
    } else {
        html += `<div class="card"><h2>${t('section_dns')}</h2><p class="empty-state">${t('empty_records')}</p></div>`;
    }

    // 9. HTTP заголовки
    const hdrs = a.headers?.all_headers || {};
    const hdrRows = Object.entries(hdrs);
    if (hdrRows.length > 0) {
        html += `<div class="card"><h2>${t('section_headers')}</h2><div class="headers-table"><table><thead><tr><th>${t('label_header')}</th><th>${t('label_value')}</th></tr></thead><tbody>${hdrRows.map(([k, v]) => `<tr><td>${escHtml(k)}</td><td>${escHtml(v)}</td></tr>`).join('')}</tbody></table></div></div>`;
    }

    // 10. Технологии
    const tech = a.technologies || {};
    const allTechs = [...(tech.frameworks || []), ...(tech.technologies || [])];
    if (allTechs.length > 0) {
        html += `<div class="card"><h2>${t('section_tech')}</h2><div class="tech-tags">${allTechs.map(tech => `<span class="tech-tag">${escHtml(tech)}</span>`).join('')}</div></div>`;
    }

    // 11. Производительность
    const perf = a.performance || {};
    const ms = t('label_ms');
    const perfItems = [
        ['DNS lookup', perf.dns_lookup_ms ? perf.dns_lookup_ms + ' ' + ms : '—'],
        ['TCP connect', perf.connect_ms ? perf.connect_ms + ' ' + ms : '—'],
        ['TTFB', perf.ttfb_ms ? perf.ttfb_ms + ' ' + ms : '—'],
        ['Общее время', perf.total_ms ? perf.total_ms + ' ' + ms : '—'],
        ['Размер контента', perf.content_size_bytes ? formatBytes(perf.content_size_bytes) : '—'],
        ['Редиректы', perf.redirect_count ?? '—'],
        ['HTTP версия', perf.http_version || '—'],
        [t('label_compression'), perf.content_encoding || t('label_no')],
        ['Cache-Control', perf.cache_control || '—'],
    ];
    html += `<div class="card"><h2>${t('section_perf')}</h2><div class="info-grid">${infoItemsAll(perfItems)}</div></div>`;

    // 12. WHOIS
    const w = a.whois || {};
    const whoisItems = [[t('label_domain'), w.domain_name], [t('label_registrar'), w.registrar], [t('label_created'), w.creation_date], [t('label_expires'), w.expiration_date], [t('label_country'), w.country || '—']];
    html += `<div class="card"><h2>${t('section_whois')}</h2><div class="info-grid">${infoItemsAll(whoisItems)}</div></div>`;

    // 13. Порты
    if (a.ports && a.ports.length > 0) {
        const sorted = [...a.ports].sort((x, y) => x.port - y.port);
        const useTable = sorted.length > 12;
        const portsHtml = useTable
            ? `<div class="ports-scroll"><table class="ports-table"><thead><tr><th>${t('label_port')}</th><th>${t('label_service')}</th></tr></thead><tbody>${sorted.map(p => `<tr><td class="port-num-cell"><span class="port-dot"></span> ${p.port}</td><td>${escHtml(p.service)}</td></tr>`).join('')}</tbody></table></div>`
            : `<div class="ports-grid">${sorted.map(p => `<div class="port-item"><span class="port-dot"></span><span class="port-number">${p.port}</span><span class="port-service">${escHtml(p.service)}</span></div>`).join('')}</div>`;
        html += `<div class="card"><h2>${t('section_ports')}</h2>${portsHtml}</div>`;
    } else {
        html += `<div class="card"><h2>${t('section_ports')}</h2><p class="empty-state">${t('empty_ports')}</p></div>`;
    }

    // 14. Traceroute
    const tr = a.traceroute;
    if (tr && tr.error) {
        html += `<div class="card"><h2>Traceroute</h2><p class="traceroute-target">${t('label_target')} ${escHtml(tr.target || a.ip_address || '—')}</p><p class="empty-state warning">${escHtml(tr.error)}</p></div>`;
    } else if (tr && tr.hops && tr.hops.length > 0) {
        const ms = t('label_ms');
        html += `<div class="card"><h2>Traceroute</h2><p class="traceroute-target">${t('label_target')} ${escHtml(tr.target)}</p><ol class="traceroute-list">${tr.hops.map(h => {
            const rtt = h.rtt_ms && h.rtt_ms.length > 0 ? h.rtt_ms.map(m => m + ' ' + ms).join(' / ') : '—';
            const hostPart = h.hostname ? `<span class="hop-host">${escHtml(h.hostname)}</span> <span class="hop-ip mono">${escHtml(h.ip)}</span>` : `<span class="hop-ip mono">${escHtml(h.ip)}</span>`;
            return `<li><span class="hop-num">${h.hop}</span>${hostPart}<span class="hop-rtt">${rtt}</span></li>`;
        }).join('')}</ol></div>`;
    } else {
        html += `<div class="card"><h2>Traceroute</h2><p class="empty-state">${t('empty_route')}</p></div>`;
    }

    // 15. Cookies
    const cookies = a.cookies || {};
    if (cookies.cookies && cookies.cookies.length > 0) {
        const summaryHtml = cookies.summary && cookies.summary.length > 0
            ? `<ul class="cookies-summary">${cookies.summary.map(s => `<li class="${s.startsWith('✓') ? 'positive' : 'warning'}">${escHtml(s)}</li>`).join('')}</ul>` : '';
        html += `<div class="card"><h2>${t('section_cookies')}</h2>${summaryHtml}<table class="cookies-table"><thead><tr><th>${t('label_cookie')}</th><th>${t('label_secure')}</th><th>${t('label_httponly')}</th><th>${t('label_samesite')}</th></tr></thead><tbody>${cookies.cookies.map(c => `<tr><td class="mono">${escHtml(c.name)}</td><td>${c.secure ? '✓' : '✗'}</td><td>${c.httponly ? '✓' : '✗'}</td><td>${c.samesite || '—'}</td></tr>`).join('')}</tbody></table></div>`;
    } else {
        html += `<div class="card"><h2>${t('section_cookies')}</h2><p class="empty-state">${t('empty_cookies')}</p></div>`;
    }

    modalBody.innerHTML = html;
    modalOverlay.classList.remove('hidden');
    document.body.style.overflow = 'hidden';
}

let editingNoteSiteId = null;

function editNote(id) {
    const site = sites.find(s => s.id === id);
    if (!site) return;
    editingNoteSiteId = id;
    document.getElementById('note-modal-url').textContent = site.url;
    document.getElementById('note-edit-text').value = site.note || '';
    document.getElementById('note-modal-overlay').classList.remove('hidden');
    document.body.style.overflow = 'hidden';
}

function closeNoteModal() {
    document.getElementById('note-modal-overlay').classList.add('hidden');
    document.body.style.overflow = '';
    editingNoteSiteId = null;
}

async function saveNote() {
    if (!editingNoteSiteId) return;
    const textarea = document.getElementById('note-edit-text');
    const note = textarea.value.trim();

    try {
        const resp = await fetch(`/api/saved/${editingNoteSiteId}/note`, {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ note }),
        });
        if (!resp.ok) throw new Error();
        const site = sites.find(s => s.id === editingNoteSiteId);
        if (site) site.note = note;
        render();
        closeNoteModal();
        showToast(t('toast_note_ok'), 'success');
    } catch {
        showToast(t('toast_note_err'), 'error');
    }
}

document.getElementById('note-modal-close').addEventListener('click', closeNoteModal);
document.getElementById('note-modal-overlay').addEventListener('click', (e) => {
    if (e.target.id === 'note-modal-overlay') closeNoteModal();
});

async function deleteSite(id) {
    if (!confirm(t('confirm_delete'))) return;

    try {
        const resp = await fetch(`/api/saved/${id}`, { method: 'DELETE' });
        if (!resp.ok) throw new Error();
        sites = sites.filter(s => s.id !== id);
        render();
        updateBadge();
        showToast(t('toast_deleted_ok'), 'success');
    } catch {
        showToast(t('toast_deleted_err'), 'error');
    }
}

function reanalyze(btn) {
    const url = btn?.dataset?.url ? decodeURIComponent(btn.dataset.url) : '';
    if (!url) return;
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

function infoItemsAll(pairs) {
    return pairs.map(([label, value]) => `
        <div class="info-item">
            <span class="info-label">${escHtml(label)}</span>
            <span class="info-value mono">${escHtml(String(value ?? '—'))}</span>
        </div>
    `).join('');
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
        const locale = document.documentElement.lang === 'en' ? 'en-US' : 'ru-RU';
        return d.toLocaleDateString(locale, { day: 'numeric', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' });
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
