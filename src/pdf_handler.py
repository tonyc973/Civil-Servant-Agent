import os
from datetime import datetime
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.colors import Color
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# Fontă Unicode (conține diacriticele românești ă â î ș ț).
# Helvetica/WinAnsi nu le conține, de aceea nu se vedeau în PDF.
_FONT_DIR = "/usr/share/fonts/truetype/dejavu"
_FONT = "Helvetica"
_FONT_BOLD = "Helvetica-Bold"
try:
    pdfmetrics.registerFont(TTFont("DejaVu", os.path.join(_FONT_DIR, "DejaVuSans.ttf")))
    pdfmetrics.registerFont(TTFont("DejaVu-Bold", os.path.join(_FONT_DIR, "DejaVuSans-Bold.ttf")))
    _FONT = "DejaVu"
    _FONT_BOLD = "DejaVu-Bold"
except Exception as e:
    print(f"⚠️ Fontă Unicode indisponibilă, folosesc Helvetica: {e}")

# Paletă oficială (tricolor + bleumarin administrativ)
NAVY = Color(0.03, 0.13, 0.36)
GOLD = Color(0.78, 0.60, 0.13)
BLUE = Color(0.00, 0.17, 0.50)   # albastru drapel
YELLOW = Color(0.99, 0.82, 0.09)  # galben drapel
RED = Color(0.81, 0.07, 0.15)     # roșu drapel
INK = Color(0.13, 0.15, 0.20)
MUTED = Color(0.45, 0.48, 0.55)
LINE = Color(0.80, 0.83, 0.88)
ROW_BG = Color(0.955, 0.965, 0.985)


def _flag(c, x, y, w=52, h=38):
    """Drapel tricolor stilizat cu chenar auriu (emblemă antet)."""
    sw = w / 3.0
    for i, col in enumerate((BLUE, YELLOW, RED)):
        c.setFillColor(col)
        c.rect(x + i * sw, y - h, sw, h, stroke=0, fill=1)
    c.setStrokeColor(GOLD)
    c.setLineWidth(1.4)
    c.rect(x, y - h, w, h, stroke=1, fill=0)


def _tricolor_rule(c, x, y, total_w, h=3):
    """Bară tricoloră subțire (separator antet)."""
    seg = total_w / 3.0
    for i, col in enumerate((BLUE, YELLOW, RED)):
        c.setFillColor(col)
        c.rect(x + i * seg, y, seg, h, stroke=0, fill=1)


def _stamp(c, cx, cy, r=34):
    """Ștampilă rotundă cu marcaj L.S. (loco sigilli)."""
    c.setStrokeColor(Color(0.55, 0.60, 0.70))
    c.setLineWidth(1.2)
    c.circle(cx, cy, r, stroke=1, fill=0)
    c.circle(cx, cy, r - 4, stroke=1, fill=0)
    c.setFillColor(Color(0.55, 0.60, 0.70))
    c.setFont(_FONT_BOLD, 11)
    c.drawCentredString(cx, cy + 6, "L.S.")
    c.setFont(_FONT, 6)
    c.drawCentredString(cx, cy - 4, "LOC PENTRU")
    c.drawCentredString(cx, cy - 12, "ȘTAMPILĂ")


def _wrap(text, font, size, max_w):
    """Împarte textul pe rânduri care încap în lățimea dată."""
    words = str(text).split()
    lines, cur = [], ""
    for w in words:
        t = (cur + " " + w).strip()
        if pdfmetrics.stringWidth(t, font, size) <= max_w or not cur:
            cur = t
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines or [""]


class PDFHandler:
    def __init__(self, assets_dir="assets"):
        self.assets_dir = assets_dir
        os.makedirs(self.assets_dir, exist_ok=True)

    def fill_form(self, data, service_config, output_name="Application.pdf"):
        """
        Generează un document oficial (stil administrația publică din România),
        desenând direct valorile completate cu o fontă Unicode — vizibile în orice
        cititor PDF, cu diacritice corecte. Funcționează automat pentru orice serviciu.
        """
        try:
            print(f"📝 GENEREZ PDF: {output_name} cu datele: {data}")

            c = canvas.Canvas(output_name, pagesize=A4)
            width, height = A4
            margin = 45
            cl = margin + 18                 # marginea internă stânga
            cr = width - margin - 18         # marginea internă dreapta
            service_name = service_config["name"]
            today = datetime.now().strftime("%d.%m.%Y")

            self._frame(c, width, height, margin)
            self._watermark(c, width, height)

            # ── ANTET ────────────────────────────────────────────────
            top = height - margin - 12
            _flag(c, margin + 10, top, 52, 38)
            c.setFillColor(NAVY)
            c.setFont(_FONT_BOLD, 16)
            c.drawString(margin + 78, top - 12, "ROMÂNIA")
            c.setFillColor(MUTED)
            c.setFont(_FONT, 8)
            c.drawString(margin + 78, top - 26, "ADMINISTRAȚIA PUBLICĂ DIGITALĂ")
            c.drawString(margin + 78, top - 37, "Ghișeu unic pentru servicii publice")

            # Casetă număr de înregistrare (dreapta-sus)
            bx, by, bw, bh = cr - 196, top - 40, 196, 40
            c.setFillColor(Color(0.97, 0.98, 1.0))
            c.setStrokeColor(LINE)
            c.setLineWidth(0.8)
            c.roundRect(bx, by, bw, bh, 4, stroke=1, fill=1)
            c.setFillColor(MUTED)
            c.setFont(_FONT, 8)
            c.drawString(bx + 10, by + bh - 14, "Nr. de înregistrare")
            c.setFillColor(INK)
            c.setFont(_FONT_BOLD, 9)
            c.drawString(bx + 108, by + bh - 14, "________")
            c.setFillColor(MUTED)
            c.setFont(_FONT, 8)
            c.drawString(bx + 10, by + 10, "Data")
            c.setFillColor(INK)
            c.setFont(_FONT_BOLD, 9)
            c.drawString(bx + 108, by + 10, today)

            _tricolor_rule(c, margin, top - 52, width - 2 * margin)

            # ── TITLU ────────────────────────────────────────────────
            ty = top - 92
            c.setFillColor(NAVY)
            c.setFont(_FONT_BOLD, 22)
            c.drawCentredString(width / 2, ty, "C E R E R E")
            c.setFillColor(INK)
            c.setFont(_FONT, 11.5)
            c.drawCentredString(width / 2, ty - 18, service_name.upper())
            c.setStrokeColor(LINE)
            c.setLineWidth(0.8)
            c.line(width / 2 - 120, ty - 28, width / 2 + 120, ty - 28)

            # ── FORMULĂ INTRODUCTIVĂ ─────────────────────────────────
            iy = ty - 56
            c.setFillColor(INK)
            c.setFont(_FONT, 10)
            c.drawString(cl, iy, f"Către:  {service_name}")
            c.setFillColor(MUTED)
            c.setFont(_FONT, 9.5)
            c.drawString(cl, iy - 16,
                         "Prin prezenta, subsemnatul(a), solicit și declar pe propria răspundere următoarele informații:")

            # ── GRILĂ CÂMPURI ────────────────────────────────────────
            y = iy - 36
            label_w = (cr - cl) * 0.40
            val_x = cl + label_w + 12
            val_w = cr - val_x - 10
            footer_limit = margin + 150

            for key, label in service_config["required_fields"].items():
                value = str(data.get(key, "") or "")
                lines = _wrap(value, _FONT_BOLD, 10, val_w) if value else ["—"]
                row_h = max(24, 8 + len(lines) * 13)

                if y - row_h < footer_limit:
                    c.showPage()
                    self._frame(c, width, height, margin)
                    self._watermark(c, width, height)
                    y = height - margin - 30

                # fundal alternant + chenar rând
                c.setFillColor(ROW_BG)
                c.setStrokeColor(LINE)
                c.setLineWidth(0.6)
                c.rect(cl, y - row_h, cr - cl, row_h, stroke=1, fill=1)
                c.setStrokeColor(LINE)
                c.line(val_x - 6, y - row_h, val_x - 6, y)

                # etichetă
                c.setFillColor(NAVY)
                c.setFont(_FONT_BOLD, 9.5)
                c.drawString(cl + 8, y - 16, label)

                # valoare (desenată ca text vizibil)
                c.setFillColor(INK if value else MUTED)
                c.setFont(_FONT_BOLD if value else _FONT, 10)
                ly = y - 16
                for ln in lines:
                    c.drawString(val_x, ly, ln)
                    ly -= 13

                y -= row_h + 4

            # ── SUBSOL: declarație, dată, semnătură, ștampilă ────────
            self._footer(c, width, margin, cl, cr, today)

            c.save()
            print(f"🎉 PDF EXPORTAT CU SUCCES: {output_name}")
            return True
        except Exception as e:
            print(f"❌ EROARE PDF: {e}")
            return False

    # ── elemente repetate pe fiecare pagină ──────────────────────────
    def _frame(self, c, width, height, margin):
        c.setStrokeColor(NAVY)
        c.setLineWidth(1.4)
        c.rect(margin - 6, margin - 6, width - 2 * (margin - 6), height - 2 * (margin - 6), stroke=1, fill=0)
        c.setStrokeColor(GOLD)
        c.setLineWidth(0.6)
        c.rect(margin - 2, margin - 2, width - 2 * (margin - 2), height - 2 * (margin - 2), stroke=1, fill=0)

    def _watermark(self, c, width, height):
        c.saveState()
        c.setFillColor(Color(0.92, 0.93, 0.96))
        c.setFont(_FONT_BOLD, 60)
        c.translate(width / 2, height / 2)
        c.rotate(45)
        c.drawCentredString(0, 0, "DOCUMENT OFICIAL")
        c.restoreState()

    def _footer(self, c, width, margin, cl, cr, today):
        fy = margin + 96
        c.setFillColor(MUTED)
        c.setFont(_FONT, 9)
        c.drawString(cl, fy, "Declar că datele furnizate sunt corecte și complete, conform documentelor justificative.")

        # dată + semnătură
        c.setFillColor(INK)
        c.setFont(_FONT, 10)
        c.drawString(cl, fy - 34, f"Data:  {today}")
        c.drawString(cr - 200, fy - 34, "Semnătura solicitantului")
        c.setStrokeColor(Color(0.6, 0.63, 0.7))
        c.setLineWidth(0.8)
        c.line(cr - 200, fy - 50, cr - 40, fy - 50)

        # ștampilă oficială (zona centrală, fără suprapunere cu data)
        _stamp(c, width * 0.40, fy - 30, r=30)

        # notă subsol
        _tricolor_rule(c, margin, margin + 14, width - 2 * margin, h=2)
        c.setFillColor(MUTED)
        c.setFont(_FONT, 7)
        c.drawCentredString(width / 2, margin + 2,
                            f"Document generat automat la {today} prin sistemul agentic conversațional  •  pagină valabilă cu semnătură și ștampilă")
