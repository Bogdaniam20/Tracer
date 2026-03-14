"""Генерация PDF-отчёта по результатам анализа сайта."""
import os
from datetime import datetime
from io import BytesIO
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

# Шрифт с поддержкой кириллицы (чёрные прямоугольники = отсутствие глифов)
PDF_FONT = "Helvetica"
PDF_FONT_BOLD = "Helvetica-Bold"

_FONT_REGISTERED = False


def _register_cyrillic_font():
    """Регистрирует шрифт с поддержкой кириллицы."""
    global PDF_FONT, PDF_FONT_BOLD, _FONT_REGISTERED
    if _FONT_REGISTERED:
        return

    fonts_dir = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts"
    font_pairs = [
        (fonts_dir / "arial.ttf", fonts_dir / "arialbd.ttf"),
        (fonts_dir / "Arial.ttf", fonts_dir / "Arial Bold.ttf"),
        (Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"), Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")),
        (Path("/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"), Path("/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf")),
    ]

    for reg_path, bold_path in font_pairs:
        if reg_path.exists():
            try:
                pdfmetrics.registerFont(TTFont("CyrillicFont", str(reg_path)))
                if bold_path.exists():
                    pdfmetrics.registerFont(TTFont("CyrillicFont-Bold", str(bold_path)))
                    PDF_FONT_BOLD = "CyrillicFont-Bold"
                else:
                    PDF_FONT_BOLD = "CyrillicFont"
                PDF_FONT = "CyrillicFont"
                _FONT_REGISTERED = True
                return
            except Exception:
                pass
    _FONT_REGISTERED = True


def _safe(val, default="—"):
    """Безопасное преобразование в строку."""
    if val is None or val == "":
        return default
    return str(val)


def _format_bytes(n):
    """Форматирование размера в байтах."""
    if n is None or n == 0:
        return "—"
    if n < 1024:
        return f"{n} Б"
    if n < 1048576:
        return f"{n / 1024:.1f} КБ"
    return f"{n / 1048576:.2f} МБ"


def generate_analysis_pdf(analysis: dict) -> bytes:
    """Генерирует PDF-отчёт из анализа сайта."""
    _register_cyrillic_font()

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=1.5 * cm,
        leftMargin=1.5 * cm,
        topMargin=1.5 * cm,
        bottomMargin=1.5 * cm,
    )
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        name="CustomTitle",
        parent=styles["Heading1"],
        fontName=PDF_FONT_BOLD,
        fontSize=18,
        spaceAfter=12,
    )
    heading_style = ParagraphStyle(
        name="SectionHeading",
        parent=styles["Heading2"],
        fontName=PDF_FONT_BOLD,
        fontSize=12,
        spaceBefore=14,
        spaceAfter=12,
    )
    normal_style = ParagraphStyle(
        name="CyrillicNormal",
        parent=styles["Normal"],
        fontName=PDF_FONT,
        fontSize=10,
    )

    story = []

    # Заголовок
    url = analysis.get("url", "—")
    story.append(Paragraph("Отчёт анализа сайта", title_style))
    story.append(Paragraph(f"<b>URL:</b> {_safe(url)}", normal_style))
    story.append(
        Paragraph(
            f"<i>Дата: {datetime.now().strftime('%d.%m.%Y %H:%M')}</i>",
            normal_style,
        )
    )
    story.append(Spacer(1, 1 * cm))

    # Общая информация
    story.append(Paragraph("Общая информация", heading_style))
    general_data = [
        ["Параметр", "Значение"],
        ["URL", _safe(url)],
        ["IP-адрес", _safe(analysis.get("ip_address"))],
    ]
    geo = analysis.get("geo") or {}
    if geo.get("country") or geo.get("flag_emoji"):
        general_data.append(
            ["Страна", f"{geo.get('flag_emoji', '')} {geo.get('country', '—')}"]
        )
    story.append(_make_table(general_data))
    story.append(Spacer(1, 0.5 * cm))

    # Безопасность
    sec = analysis.get("security")
    if sec:
        story.append(Paragraph("Безопасность", heading_style))
        score = sec.get("score", 0)
        grade = sec.get("grade", "—")
        max_score = sec.get("max_score", 100)
        sec_data = [
            ["Оценка", f"{grade} ({score}/{max_score})"],
        ]
        for d in sec.get("details", [])[:8]:
            txt = d[:80] + "..." if len(d) > 80 else d
            sec_data.append([txt, ""])
        story.append(_make_table(sec_data))
        story.append(Spacer(1, 0.5 * cm))

    # SSL/TLS
    ssl = analysis.get("ssl")
    if ssl and ssl.get("issuer"):
        story.append(Paragraph("SSL / TLS", heading_style))
        ssl_data = [
            ["Издатель", _safe(ssl.get("issuer"))],
            ["Протокол", _safe(ssl.get("protocol_version"))],
            ["Шифр", _safe(ssl.get("cipher_suite"))],
            ["Действителен до", _safe(ssl.get("not_after"))],
            ["Дней до истечения", _safe(ssl.get("days_until_expiry"))],
        ]
        story.append(_make_table(ssl_data))
        story.append(Spacer(1, 0.5 * cm))

    # Объём страницы
    pv = analysis.get("page_volume")
    if pv and pv.get("items"):
        story.append(Paragraph("Объём страницы", heading_style))
        vol_data = [["Тип", "Размер", "%"]]
        for item in pv.get("items", []):
            t = item.get("type", "")
            labels = {"html": "HTML", "images": "Изображения", "css": "CSS", "js": "JavaScript"}
            vol_data.append(
                [
                    labels.get(t, t),
                    _format_bytes(item.get("bytes")),
                    f"{item.get('percent', 0):.2f}%",
                ]
            )
        vol_data.append(["всего", _format_bytes(pv.get("total_bytes")), "100%"])
        story.append(_make_table(vol_data))
        story.append(Spacer(1, 0.5 * cm))

    # Производительность
    perf = analysis.get("performance")
    if perf:
        story.append(Paragraph("Производительность", heading_style))
        perf_data = [
            ["DNS lookup", f"{_safe(perf.get('dns_lookup_ms'))} мс"],
            ["TCP connect", f"{_safe(perf.get('connect_ms'))} мс"],
            ["TTFB", f"{_safe(perf.get('ttfb_ms'))} мс"],
            ["Общее время", f"{_safe(perf.get('total_ms'))} мс"],
            ["Размер контента", _format_bytes(perf.get("content_size_bytes"))],
            ["HTTP версия", _safe(perf.get("http_version"))],
        ]
        story.append(_make_table(perf_data))
        story.append(Spacer(1, 0.5 * cm))

    # WHOIS
    whois = analysis.get("whois")
    if whois and whois.get("domain_name"):
        story.append(Paragraph("WHOIS", heading_style))
        whois_data = [
            ["Домен", _safe(whois.get("domain_name"))],
            ["Регистратор", _safe(whois.get("registrar"))],
            ["Дата создания", _safe(whois.get("creation_date"))],
            ["Дата истечения", _safe(whois.get("expiration_date"))],
        ]
        story.append(_make_table(whois_data))
        story.append(Spacer(1, 0.5 * cm))

    # Открытые порты
    ports = analysis.get("ports") or []
    if ports:
        story.append(Paragraph("Открытые порты", heading_style))
        ports_data = [["Порт", "Сервис"]]
        for p in sorted(ports, key=lambda x: x.get("port", 0)):
            ports_data.append([str(p.get("port", "")), _safe(p.get("service"))])
        story.append(_make_table(ports_data))
        story.append(Spacer(1, 0.5 * cm))

    # SEO
    seo = analysis.get("seo")
    if seo and (seo.get("title") or seo.get("meta_description")):
        story.append(Paragraph("SEO", heading_style))
        seo_data = [
            ["Title", _safe(seo.get("title"))[:100]],
            ["Meta description", _safe(seo.get("meta_description"))[:100]],
        ]
        story.append(_make_table(seo_data))

    doc.build(story)
    return buffer.getvalue()


def _make_table(data: list, col_widths: list | None = None) -> Table:
    """Создаёт стилизованную таблицу."""
    if col_widths is None:
        ncols = len(data[0]) if data else 2
        col_widths = [15 * cm / ncols] * ncols
    t = Table(data, colWidths=col_widths)
    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1f2937")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("TEXTCOLOR", (0, 1), (-1, -1), colors.white),
                ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                ("FONTNAME", (0, 0), (-1, 0), PDF_FONT_BOLD),
                ("FONTNAME", (0, 1), (-1, -1), PDF_FONT),
                ("FONTSIZE", (0, 0), (-1, 0), 10),
                ("FONTSIZE", (0, 1), (-1, -1), 9),
                ("BOTTOMPADDING", (0, 0), (-1, 0), 8),
                ("TOPPADDING", (0, 0), (-1, 0), 8),
                ("TOPPADDING", (0, 1), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 1), (-1, -1), 6),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#374151")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.HexColor("#111827"), colors.HexColor("#1f2937")]),
            ]
        )
    )
    return t
