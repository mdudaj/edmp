from __future__ import annotations

import base64
import io
import re
from typing import Any


TOKEN_PATTERN = re.compile(r"\[\[\s*([a-zA-Z0-9_]+)\s*\]\]")
MM_TO_PT = 72.0 / 25.4
MAX_INLINE_PDF_LABELS = 120
PDF_SHEET_PRESETS = {
    'a4-38x21.2': {
        'page_size_mm': (210.0, 297.0),
        'label_size_mm': (38.1, 21.2),
        'grid': (5, 13),  # 65-up
        'gap_mm': (0.0, 0.0),
    }
}


def _replace_tokens(text: str, payload: dict[str, Any]) -> str:
    return TOKEN_PATTERN.sub(
        lambda match: '' if payload.get(match.group(1)) is None else str(payload.get(match.group(1))),
        text or '',
    )


def _normalize_labels(payload: dict[str, Any]) -> list[str]:
    labels = payload.get('labels')
    if isinstance(labels, list):
        normalized = [str(item).strip() for item in labels if str(item).strip()]
    else:
        normalized = []
    if not normalized:
        single = str(payload.get('label') or payload.get('content') or '').strip()
        if single:
            normalized = [single]
    return normalized


def _zpl_qr_block(label: str) -> str:
    return f"^XA^FO40,40^BQN,2,6^FDQA,{label}^FS^FO40,200^A0N,28,28^FD{label}^FS^XZ"


def _normalize_pdf_sheet_preset(payload: dict[str, Any]) -> str:
    value = str(payload.get('pdf_sheet_preset') or '').strip()
    return value if value in PDF_SHEET_PRESETS else 'a4-38x21.2'


def _expand_pdf_batch_labels(labels: list[str], payload: dict[str, Any]) -> tuple[list[str], int]:
    batch_count = payload.get('batch_count')
    if not isinstance(batch_count, int) or batch_count <= 1:
        return labels, 1
    expanded: list[str] = []
    for item in labels:
        expanded.extend([item] * batch_count)
    return expanded, batch_count


def _render_a4_pdf_sheet(labels: list[str], preset_key: str) -> tuple[str | None, str | None]:
    try:
        import qrcode
        from reportlab.pdfgen import canvas
    except ImportError as exc:
        return None, f'missing_pdf_dependencies: {exc}'

    preset = PDF_SHEET_PRESETS[preset_key]
    page_w_mm, page_h_mm = preset['page_size_mm']
    label_w_mm, label_h_mm = preset['label_size_mm']
    cols, rows = preset.get('grid', (0, 0))
    gap_x_mm, gap_y_mm = preset['gap_mm']

    page_w_pt = page_w_mm * MM_TO_PT
    page_h_pt = page_h_mm * MM_TO_PT
    label_w_pt = label_w_mm * MM_TO_PT
    label_h_pt = label_h_mm * MM_TO_PT
    gap_x_pt = gap_x_mm * MM_TO_PT
    gap_y_pt = gap_y_mm * MM_TO_PT

    if not cols or not rows:
        usable_w_pt = page_w_pt
        usable_h_pt = page_h_pt
        cols = max(1, int((usable_w_pt + gap_x_pt) // (label_w_pt + gap_x_pt)))
        rows = max(1, int((usable_h_pt + gap_y_pt) // (label_h_pt + gap_y_pt)))
    margin_x_pt = (page_w_pt - ((cols * label_w_pt) + ((cols - 1) * gap_x_pt))) / 2
    margin_y_pt = (page_h_pt - ((rows * label_h_pt) + ((rows - 1) * gap_y_pt))) / 2
    labels_per_page = rows * cols

    pdf_buffer = io.BytesIO()
    pdf = canvas.Canvas(pdf_buffer, pagesize=(page_w_pt, page_h_pt))
    pdf.setFont('Helvetica', 7)

    for index, label in enumerate(labels):
        page_index = index % labels_per_page
        if page_index == 0 and index > 0:
            pdf.showPage()
            pdf.setFont('Helvetica', 7)
        row = page_index // cols
        col = page_index % cols
        x = margin_x_pt + (col * (label_w_pt + gap_x_pt))
        y = page_h_pt - margin_y_pt - label_h_pt - (row * (label_h_pt + gap_y_pt))

        qr = qrcode.QRCode(box_size=2, border=1)
        qr.add_data(label)
        qr.make(fit=True)
        qr_img = qr.make_image(fill_color='black', back_color='white').get_image()
        qr_size = min(label_h_pt * 0.58, label_w_pt * 0.54)
        text = label[:48]
        font_size = 7
        max_text_width = label_w_pt - 4
        while font_size > 5 and pdf.stringWidth(text, 'Helvetica', font_size) > max_text_width:
            font_size -= 1
        pdf.setFont('Helvetica', font_size)
        text_width = pdf.stringWidth(text, 'Helvetica', font_size)
        spacing = 2
        group_height = qr_size + spacing + font_size
        group_y = y + ((label_h_pt - group_height) / 2)
        qr_x = x + ((label_w_pt - qr_size) / 2)
        qr_y = group_y + font_size + spacing
        text_x = x + ((label_w_pt - text_width) / 2)
        text_y = group_y
        pdf.drawInlineImage(qr_img, qr_x, qr_y, qr_size, qr_size)
        pdf.drawString(text_x, text_y, text)

    pdf.save()
    encoded = base64.b64encode(pdf_buffer.getvalue()).decode('ascii')
    return encoded, None


def render_label_preview(*, output_format: str, template_content: str, payload: dict[str, Any]) -> dict[str, Any]:
    labels = _normalize_labels(payload)
    if output_format == 'zpl':
        if labels:
            if template_content:
                rendered_blocks = []
                for label in labels:
                    rendered_blocks.append(
                        _replace_tokens(template_content, {**payload, 'label': label, 'content': label})
                    )
                return {
                    'engine': 'zpl-inline',
                    'label_count': len(rendered_blocks),
                    'rendered': '\n'.join(rendered_blocks),
                }
            return {
                'engine': 'zpl-inline',
                'label_count': len(labels),
                'rendered': '\n'.join(_zpl_qr_block(label) for label in labels),
            }
        rendered = _replace_tokens(template_content, payload)
        return {'engine': 'zpl-inline', 'label_count': 1, 'rendered': rendered}
    if output_format == 'pdf':
        preset_key = _normalize_pdf_sheet_preset(payload)
        labels, batch_count = _expand_pdf_batch_labels(labels, payload)
        preset = PDF_SHEET_PRESETS[preset_key]
        if labels:
            response = {
                'engine': 'qrcode-reportlab-pylabels',
                'sheet_preset': preset_key,
                'label_count': len(labels),
                'batch_count': batch_count,
                'layout': {
                    'grid': preset.get('grid'),
                    'label_size_mm': preset.get('label_size_mm'),
                    'page_size_mm': preset.get('page_size_mm'),
                },
            }
            if len(labels) > MAX_INLINE_PDF_LABELS:
                response['rendered'] = 'sheet payload too large for inline preview'
                response['render_warning'] = (
                    f'inline pdf disabled when labels>{MAX_INLINE_PDF_LABELS}'
                )
                return response
            pdf_base64, render_error = _render_a4_pdf_sheet(labels, preset_key)
            response['rendered'] = _replace_tokens(template_content, payload)
            if pdf_base64:
                response['pdf_base64'] = pdf_base64
            if render_error:
                response['render_error'] = render_error
            return response
        rendered = _replace_tokens(template_content, payload)
        return {
            'engine': 'qrcode-reportlab-pylabels',
            'sheet_preset': preset_key,
            'label_count': 1,
            'batch_count': batch_count,
            'layout': {
                'grid': preset.get('grid'),
                'label_size_mm': preset.get('label_size_mm'),
                'page_size_mm': preset.get('page_size_mm'),
            },
            'rendered': rendered,
        }
    rendered = _replace_tokens(template_content, payload)
    return {'engine': 'raw', 'rendered': rendered}
