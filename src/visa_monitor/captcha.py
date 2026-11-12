"""Optional local OCR. Disabled until permission and live feasibility are established."""
import base64
import hashlib
import io
import re
from collections import Counter
from dataclasses import dataclass
from .calendar_parser import endpoint, portal_url, soup
from .models import CheckError, Status

@dataclass
class Challenge:
    action: str
    fields: list[tuple[str,str]]
    image: str

def extract_challenge(html,current):
    field = soup(html).select_one('input[name="captchaText"]')
    if field is None or (form:=field.find_parent("form")) is None:
        raise CheckError(Status.PARSE_ERROR,"Unrecognized CAPTCHA form")
    action = portal_url(form.get("action") or current,current)
    if endpoint(action) not in ("appointment_showMonth.do","appointment_captcha.do"):
        raise CheckError(Status.PARSE_ERROR,"Refusing non-calendar form submission")
    if form.get("method","get").lower()!="post":
        raise CheckError(Status.PARSE_ERROR,"Unexpected CAPTCHA form method")
    fields = [(i["name"],i.get("value","")) for i in form.select('input[type="hidden"][name]')]
    if any(k.startswith("action:") for k,v in fields):
        raise CheckError(Status.PARSE_ERROR,"Unexpected hidden dispatch field")
    if any(k in ("firstname","lastname","email","passportNumber") and v for k,v in fields):
        raise CheckError(Status.PARSE_ERROR,"Applicant data unexpectedly present in CAPTCHA form")
    submits = [i for i in form.select('input[type="submit"],button[type="submit"]')
               if i.get("name")=="action:appointment_showMonth"]
    if len(submits)!=1:
        raise CheckError(Status.PARSE_ERROR,"Calendar CAPTCHA submit action not recognized")
    fields.append((submits[0]["name"],submits[0].get("value",submits[0].get_text(strip=True))))
    node = form.select_one("captcha img[src],img[src*='captcha' i],img[src^='data:image/']")
    image = node.get("src") if node else None
    if image is None:
        for node in form.select("[style]"):
            match = re.search(r"url\([\"']?(data:image/[^)\"']+)[\"']?\)",node.get("style",""))
            if match:
                image = match[1]
                break
    if not image:
        raise CheckError(Status.PARSE_ERROR,"CAPTCHA image not recognized")
    return Challenge(action,fields,image)

def image_bytes(challenge,current,transport):
    if challenge.image.startswith("data:image/"):
        try:
            prefix,data = challenge.image.split(",",1)
            if ";base64" not in prefix or len(data)>3_000_000:
                raise ValueError()
            return base64.b64decode(data,validate=True)
        except (ValueError,TypeError):
            raise CheckError(Status.PARSE_ERROR,"Invalid CAPTCHA image data") from None
    response = transport.request("GET",portal_url(challenge.image,current))
    if not response.headers.get("Content-Type","").lower().startswith("image/"):
        raise CheckError(Status.PARSE_ERROR,"CAPTCHA image response is not an image")
    return response.content

def fingerprint(data):
    return hashlib.sha256(data).hexdigest()

class LocalOCR:
    def recognize(self,data):
        try:
            import cv2
            import numpy as np
            import pytesseract
            from PIL import Image, ImageOps
            if len(data)>2_000_000:
                return None
            with Image.open(io.BytesIO(data)) as source:
                if source.width*source.height>2_000_000:
                    return None
                gray = np.array(ImageOps.grayscale(source).resize((source.width*3,source.height*3)))
            otsu = cv2.threshold(gray,0,255,cv2.THRESH_BINARY+cv2.THRESH_OTSU)[1]
            adaptive = cv2.adaptiveThreshold(gray,255,cv2.ADAPTIVE_THRESH_GAUSSIAN_C,cv2.THRESH_BINARY,31,9)
            opened = cv2.morphologyEx(otsu,cv2.MORPH_OPEN,np.ones((2,2),np.uint8))
            candidates = []
            for image in (gray,otsu,adaptive,opened):
                for mode in (7,8):
                    value = pytesseract.image_to_string(image,config=f"--psm {mode}",timeout=5).strip()
                    value = re.sub(r"\s","",value)
                    if re.fullmatch(r"[A-Za-z0-9]{4,10}",value):
                        candidates.append(value)
            if not candidates:
                return None
            value,votes = Counter(candidates).most_common(1)[0]
            return value if votes>=2 else None
        except Exception:
            return None
