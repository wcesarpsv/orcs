# Report formatting migrated from streamlit_app.py.
import base64, html, re
from io import BytesIO
from PIL import Image
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image as PDFImage, KeepTogether


def data_url(image):
    return "data:image/jpeg;base64," + base64.b64encode(image).decode("ascii")

def polish(client, text):
    response = client.chat.completions.create(
        model="gpt-4o-mini", temperature=0.2,
        messages=[
            {"role": "system", "content": "Rewrite technician notes in concise professional English for a service report. Preserve all facts and meaning. Do not add assumptions, actions, tests, outcomes or serial numbers. Return only the rewritten notes."},
            {"role": "user", "content": text}
        ]
    )
    return (response.choices[0].message.content or text).strip()

def build_report(kind, place, rdl, details, units, extras, key_collected=None, key_reason="", key_return_destination=None):
    if kind == "PM":
        if key_collected not in ("Yes", "No", "Return SST Key"):
            raise ValueError("Select an SST key status.")
        if key_collected == "No" and not key_reason.strip():
            raise ValueError("Provide the reason the SST key could not be collected.")
        if key_collected == "Return SST Key" and key_return_destination not in ("Office", "Warehouse"):
            raise ValueError("Select where the SST key will be returned.")
    reference = re.sub(r"^RDL\s*:\s*", "", rdl, flags=re.I).strip()
    heading = {
        "PM": "PM completed", "INSTALLATION": "WJS Large Carmanah - Installation",
        "DEINSTALLATION": "WJS Sign Deinstallation", "BREAKFIX WJS": "WJS Breakfix"
    }[kind]
    sections = [{"text": f"{heading} - {place} (RDL: {reference}) - Summary"}]
    if kind == "PM":
        body = details + "\n\nBurster bins, rollers, and all related peripherals were cleaned.\nSerial numbers for all components were recorded for database entry.\nAll hardware components, including the pin pad, were tested and verified as operational."
    elif kind == "INSTALLATION":
        body = "Upon arrival at the site, the retailer indicated the preferred installation location and desired height for the sign.\n\n" + (details or "No issues reported.")
    elif kind == "DEINSTALLATION":
        body = "Upon arrival at the site, the retailer indicated the sign to be removed.\n\n" + (details or "No issues reported.")
    else:
        body = "Upon arrival at the site, I identified an issue affecting the operation of the jackpot sign.\n\n" + details + "\n\nFollowing troubleshooting, replacement of the existing WJS was required to restore normal operation of the jackpot sign."
    sections.append({"text": body.strip()})
    for unit in units:
        lines = [unit["title"]]
        if unit["item"]:
            lines.append("Item: " + unit["item"])
        if unit["pn"]:
            lines.append("P/N: " + unit["pn"])
        lines.append("S/N: " + (unit["sn"] or "Not provided"))
        sections.append({"text": "\n".join(lines), "image": unit.get("image")})
    if kind in ("INSTALLATION", "BREAKFIX WJS"):
        closing = "After completion, I explained the work performed to the retailer and demonstrated that the equipment was operating correctly."
        if kind == "BREAKFIX WJS":
            closing = "After installing the replacement WJS, the jackpot sign was tested and verified to be operating correctly.\n\n" + closing
        sections.append({"text": closing})
    elif kind == "DEINSTALLATION":
        sections.append({"text": "The equipment is being returned to the warehouse."})
    if extras:
        sections.append({"text": "Additional materials used:\n" + "\n".join("- " + x for x in extras)})
    if kind == "PM":
        if key_collected == "Yes":
            key_text = "SST's key was successfully collected and will be returned to the office."
        elif key_collected == "Return SST Key":
            key_text = ("The SST key was collected during a previous visit and will be returned "
                        f"to the {key_return_destination.lower()}.")
        else:
            key_text = ("SST's key could not be collected for return to the office.\n\n"
                        + "Reason: " + key_reason.strip()
                        + "\n\nThe SST's key was returned to the retailer upon completion.")
        # Keep the key status and retailer return statement at the very end,
        # including when additional materials are present.
        sections.append({"text": key_text})
    return sections

def report_html(sections):
    chunks = []
    for index, section in enumerate(sections):
        tag = "h2" if index == 0 else "p"
        chunks.append(f'<{tag} style="white-space:pre-wrap;overflow-wrap:anywhere">{html.escape(section["text"])}</{tag}>')
        if section.get("image"):
            chunks.append(f'<img src="{data_url(section["image"])}" alt="{html.escape(section["text"].splitlines()[0], quote=True)} label photo" style="display:block;max-width:100%;width:460px;height:auto;margin-bottom:24px">')
    return '<div style="font-family:Arial,sans-serif;line-height:1.5;color:#111;background:white;padding:20px">' + ''.join(chunks) + '</div>'

def make_pdf(sections):
    output = BytesIO()
    styles = getSampleStyleSheet()
    styles["BodyText"].textColor = colors.HexColor("#111111")
    document = SimpleDocTemplate(output, pagesize=A4, rightMargin=42, leftMargin=42, topMargin=42, bottomMargin=42)
    story = []
    for index, section in enumerate(sections):
        style = styles["Heading2"] if index == 0 else styles["BodyText"]
        # Split paragraphs to support multi-page technician notes.
        paragraphs = [Paragraph(html.escape(p).replace("\n", "<br/>"), style)
                      for p in section["text"].split("\n\n") if p.strip()]
        image = section.get("image")
        if image:
            with Image.open(BytesIO(image)) as im:
                width, height = im.size
            factor = min(460 / width, 260 / height, 1)
            photo = PDFImage(BytesIO(image), width=width * factor, height=height * factor)
            photo.hAlign = "LEFT"
            story.append(KeepTogether(paragraphs + [Spacer(1, 8), photo]))
        else:
            story.extend(paragraphs)
        story.append(Spacer(1, 14))
    document.build(story)
    return output.getvalue()
