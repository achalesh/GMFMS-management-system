import re
from functools import wraps
from io import BytesIO
from pathlib import Path
from threading import RLock
from xml.sax.saxutils import escape

import pypdfium2 as pdfium
import reportlab
from django.conf import settings
from django.core.exceptions import ValidationError
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph

from apps.verification.services import qr_png

WIDTH, HEIGHT = 85.6 * mm, 54 * mm
TEAL = colors.HexColor("#117d69")
INK = colors.HexColor("#163747")


def font_name():
    path = getattr(settings, "ID_CARD_FONT_PATH", "") or str(
        Path(reportlab.__file__).parent / "fonts" / "Vera.ttf"
    )
    if "CardText" not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont("CardText", path))
    if "CardMalayalam" not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(
            TTFont(
                "CardMalayalam",
                str(settings.BASE_DIR / "static/fonts/NotoSansMalayalam-Regular.ttf"),
            )
        )
    return "CardText"


def text(c, value, x, y, width, height, size=7, color=INK):
    font = font_name()
    value = str(value)
    for chunk in re.split(r"([\u0D00-\u0D7F\u200C\u200D]+)", value):
        selected = "CardMalayalam" if any("\u0d00" <= ch <= "\u0d7f" for ch in chunk) else font
        supported = pdfmetrics.getFont(selected).face.charToGlyph
        if any(
            ord(ch) not in supported
            for ch in chunk
            if not ch.isspace() and ch not in "\u200c\u200d"
        ):
            raise ValidationError(
                "The configured card fonts cannot render some characters. Configure a suitable Unicode font before issuing."
            )
    markup = "".join(
        '<font name="CardMalayalam">' + escape(chunk) + "</font>"
        if any("\u0d00" <= ch <= "\u0d7f" for ch in chunk)
        else escape(chunk)
        for chunk in re.split(r"([\u0D00-\u0D7F\u200C\u200D]+)", value)
    )
    for pts in [size, size - 0.5, size - 1, size - 1.5]:
        style = ParagraphStyle(
            "card",
            fontName=font,
            fontSize=pts,
            leading=pts * 1.18,
            textColor=color,
            splitLongWords=True,
            shaping=any("\u0d00" <= ch <= "\u0d7f" for ch in value),
        )
        paragraph = Paragraph(markup, style)
        _, needed = paragraph.wrap(width, height)
        if needed <= height:
            paragraph.drawOn(c, x, y + height - needed)
            return
    raise ValidationError(
        "Card text exceeds the available print area. Shorten the configured branding or use a shorter printable name before issuing."
    )


def logo(c, x, y):
    c.drawImage(
        ImageReader(str(settings.BASE_DIR / "static/img/gramaswaraj-logo.png")),
        x,
        y,
        width=8 * mm,
        height=10 * mm,
        preserveAspectRatio=True,
        anchor="c",
        mask="auto",
    )


def draw_face(c, s, photo, qr, side):
    c.setFillColor(colors.white)
    c.rect(0, 0, WIDTH, HEIGHT, stroke=0, fill=1)
    c.setFillColor(TEAL)
    c.rect(0, HEIGHT - 2 * mm, WIDTH, 2 * mm, stroke=0, fill=1)
    if side == 0:
        logo(c, 4 * mm, 41 * mm)
        text(c, s["brand"], 14 * mm, 43 * mm, 67 * mm, 6 * mm, 11)
        text(c, s["organization"], 14 * mm, 39 * mm, 67 * mm, 5 * mm, 5.7)
        c.drawImage(ImageReader(BytesIO(photo)), 4 * mm, 13 * mm, 18 * mm, 24 * mm, mask="auto")
        text(c, "MEDIA FACILITATOR", 25 * mm, 33 * mm, 56 * mm, 4 * mm, 7.5, color=TEAL)
        text(c, s["name"], 25 * mm, 26 * mm, 56 * mm, 7 * mm, 10)
        text(c, s["number"], 25 * mm, 21 * mm, 35 * mm, 4 * mm, 7)
        text(c, s["panchayat"] + " Grama Panchayat", 25 * mm, 14 * mm, 35 * mm, 6 * mm, 6.4)
        text(c, s["district"] + " District", 4 * mm, 5.5 * mm, 56 * mm, 4 * mm, 5.5)
        text(c, "Valid until " + s["valid_until"], 25 * mm, 10 * mm, 35 * mm, 4 * mm, 5.5)
        c.drawImage(ImageReader(BytesIO(qr)), 61 * mm, 5.5 * mm, 20 * mm, 20 * mm, mask="auto")
        c.setFillColor(TEAL)
        c.rect(0, 0, WIDTH, 5 * mm, stroke=0, fill=1)
        text(
            c,
            s["role"] + " | " + s["card_number"],
            4 * mm,
            0.6 * mm,
            78 * mm,
            3.5 * mm,
            5.4,
            color=colors.white,
        )
    else:
        text(c, "VERIFY BEFORE ACCEPTING", 4 * mm, 43 * mm, 77 * mm, 6 * mm, 9, color=TEAL)
        c.drawImage(ImageReader(BytesIO(qr)), 3 * mm, 14 * mm, 27 * mm, 27 * mm, mask="auto")
        text(c, s["block"] + " Block", 33 * mm, 35 * mm, 48 * mm, 5 * mm, 7)
        text(c, s["district"] + " District", 33 * mm, 30 * mm, 48 * mm, 5 * mm, 7)
        text(
            c,
            "Issued " + s["issue_date"] + " | Version " + str(s["version"]),
            33 * mm,
            25 * mm,
            48 * mm,
            4 * mm,
            5.7,
        )
        text(
            c,
            "Scan to check this card and current authorization. Status online takes precedence.",
            33 * mm,
            15 * mm,
            48 * mm,
            9 * mm,
            6.2,
        )
        text(c, s["signatory"] or "Authorized signatory", 33 * mm, 9 * mm, 48 * mm, 5 * mm, 6.2)
        c.setStrokeColor(colors.HexColor("#b8cac2"))
        c.line(33 * mm, 9 * mm, 81 * mm, 9 * mm)
        text(c, "Official verification: " + s["origin"], 4 * mm, 7 * mm, 27 * mm, 6 * mm, 4.8)
        terms = "Non-transferable. Return to issuer if found."
        if s["organization_phone"]:
            terms += " Office: " + s["organization_phone"]
        text(c, terms, 4 * mm, 1.8 * mm, 77 * mm, 5 * mm, 5.3)


_render_lock = RLock()


def serialized_render(fn):
    @wraps(fn)
    def wrapped(*args, **kwargs):
        with _render_lock:
            return fn(*args, **kwargs)

    return wrapped


@serialized_render
def render_cards(snapshot, portrait, qr_url):
    qr = qr_png(qr_url)
    outputs = []
    for sheet in [False, True]:
        stream = BytesIO()
        c = canvas.Canvas(stream, pagesize=A4 if sheet else (WIDTH, HEIGHT), pageCompression=1)
        c.setTitle("Gramaswaraj ID card - " + snapshot["card_number"])
        c.setAuthor(snapshot["organization"])
        for side in [0, 1]:
            c.saveState()
            if sheet:
                x, y = (A4[0] - WIDTH) / 2, (A4[1] - HEIGHT) / 2
                c.translate(x, y)
            draw_face(c, snapshot, portrait, qr, side)
            if sheet:
                c.setStrokeColor(colors.HexColor("#888888"))
                c.setLineWidth(0.3)
                for x in [0, WIDTH]:
                    for y in [0, HEIGHT]:
                        c.line(x - 3 * mm, y, x - 1 * mm, y) if x == 0 else c.line(
                            x + 1 * mm, y, x + 3 * mm, y
                        )
                        c.line(x, y - 3 * mm, x, y - 1 * mm) if y == 0 else c.line(
                            x, y + 1 * mm, x, y + 3 * mm
                        )
            c.restoreState()
            if sheet:
                c.setFont("Helvetica", 9)
                c.setFillColor(INK)
                c.drawCentredString(
                    A4[0] / 2,
                    30 * mm,
                    "Print at 100% / Actual size. Do not fit to page. Card: 85.6 x 54 mm.",
                )
                c.drawCentredString(
                    A4[0] / 2,
                    24 * mm,
                    "Front"
                    if side == 0
                    else "Back - align centers for duplex printing; test printer orientation first.",
                )
            c.showPage()
        c.save()
        outputs.append(stream.getvalue())
    previews = []
    document = pdfium.PdfDocument(outputs[0])
    try:
        for page in document:
            bitmap = page.render(scale=3)
            image = bitmap.to_pil()
            stream = BytesIO()
            image.save(stream, format="PNG")
            previews.append(stream.getvalue())
            bitmap.close()
            page.close()
    finally:
        document.close()
    return {"pdf": outputs[0], "print_pdf": outputs[1], "front": previews[0], "back": previews[1]}
