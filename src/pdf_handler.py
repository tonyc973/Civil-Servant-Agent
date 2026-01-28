import os
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.colors import black, white, Color
from PyPDFForm import PdfWrapper

class PDFHandler:
    def __init__(self, assets_dir="assets"):
        self.assets_dir = assets_dir
        # Ensure the assets folder exists
        os.makedirs(self.assets_dir, exist_ok=True)

    def _generate_dynamic_template(self, service_config):
        """
        Draws a blank PDF template based on the service configuration.
        This allows the app to support ANY new service automatically.
        """
        filename = service_config["template_file"]
        filepath = os.path.join(self.assets_dir, filename)
        
        print(f"🛠️ GENERATING NEW TEMPLATE: {filepath}")
        
        c = canvas.Canvas(filepath, pagesize=A4)
        width, height = A4
        margin = 40
        
        # 1. Draw Container Border
        c.setStrokeColor(black)
        c.setLineWidth(1)
        c.rect(margin, margin, width - 2*margin, height - 2*margin)
        
        # 2. Draw Header
        c.setFont("Helvetica-Bold", 16)
        c.drawCentredString(width/2, height - 80, service_config["name"].upper())
        
        c.setFont("Helvetica", 10)
        c.drawCentredString(width/2, height - 100, "OFFICIAL STATE DOCUMENT • AUTOMATED GENERATION")
        
        c.line(margin, height - 120, width - margin, height - 120)
        
        # 3. Draw Fields Loop
        current_y = height - 160
        fields = service_config["required_fields"]
        
        for key, label in fields.items():
            # Check if we are running out of page space (simple logic)
            if current_y < margin + 50:
                c.showPage() # New page
                current_y = height - 50
            
            # Draw Label
            c.setFillColor(black)
            c.setFont("Helvetica", 10)
            c.drawString(margin + 20, current_y, label + ":")
            
            # Draw Underline / Visual Guide
            field_x = margin + 200 # Fixed indent for values
            field_w = (width - margin - 40) - field_x
            
            c.setStrokeColor(Color(0.7, 0.7, 0.7))
            c.line(field_x, current_y - 2, field_x + field_w, current_y - 2)
            
            # Create the ACTUAL Interactive Form Field
            c.acroForm.textfield(
                name=key,
                tooltip=label,
                x=field_x,
                y=current_y - 2,
                width=field_w,
                height=16,
                fontSize=10,
                fontName="Helvetica",
                borderStyle='solid',
                borderColor=white, # Invisible border looks cleaner
                forceBorder=True
            )
            
            current_y -= 40 # Move down for the next field
            
        c.save()
        print(f"✅ TEMPLATE SAVED: {filepath}")
        return filepath

    def fill_form(self, data, service_config, output_name="Application.pdf"):
        """
        Universal fill function.
        1. Checks if template exists. If not, makes it.
        2. Fills it with the JSON data.
        """
        filename = service_config["template_file"]
        template_path = os.path.join(self.assets_dir, filename)
        
        # Auto-create template if it's missing (Dynamic behavior)
        if not os.path.exists(template_path):
            self._generate_dynamic_template(service_config)
            
        try:
            print(f"📝 FILLING PDF: {template_path} with data: {data}")
            
            wrapper = PdfWrapper(template_path)
            filled = wrapper.fill(data)
            
            with open(output_name, "wb+") as f:
                f.write(filled.read())
            
            print(f"🎉 PDF EXPORTED SUCCESSFULLY: {output_name}")
            return True
        except Exception as e:
            print(f"❌ PDF ERROR: {e}")
            return False