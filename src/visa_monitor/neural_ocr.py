"""CPU-only OCR using the packaged MIT-licensed ddddocr ONNX model.

No remote inference, runtime model download, or guessed-candidate enumeration.
Model scores are diagnostic heuristics, not calibrated acceptance probabilities.
"""
import io
import math
import re


class NeuralOCR:
    def __init__(self, expected_length=6):
        self.expected_length = expected_length
        self.model = None
        self.last_error = None
        self.diagnostics = {"engine": "neural", "readings": 0}

    def recognize(self, data):
        self.last_error = None
        self.diagnostics = {"engine": "neural", "readings": 0}
        if len(data) > 2_000_000:
            self.last_error = "CAPTCHA image exceeds OCR size limit"
            return None
        try:
            import ddddocr
            from PIL import Image, ImageOps
        except ImportError:
            self.last_error = "Local neural OCR dependencies are missing"
            return None
        try:
            with Image.open(io.BytesIO(data)) as source:
                if source.width * source.height > 2_000_000:
                    self.last_error = "CAPTCHA image dimensions exceed OCR limit"
                    return None
                original = source.convert("RGB")
                contrast = ImageOps.autocontrast(ImageOps.grayscale(source)).convert("RGB")
        except Exception:
            self.last_error = "CAPTCHA image could not be decoded"
            return None
        if self.model is None:
            try:
                self.model = ddddocr.DdddOcr(show_ad=False, use_gpu=False)
            except Exception:
                self.last_error = "Local neural OCR model initialization failed"
                return None
        try:
            # Use the original pixels first. Try contrast normalization only if
            # that result fails basic format/score checks. Never submit a list.
            for image in (original, contrast):
                result = self.model.classification(image, probability=True)
                self.diagnostics["readings"] += 1
                value = result.get("text", "")
                score = float(result.get("confidence", 0))
                if not isinstance(value, str) or not math.isfinite(score):
                    continue
                value = re.sub(r"\s", "", value)
                self.diagnostics["candidate_length"] = len(value)
                self.diagnostics["score"] = round(score, 4)
                if re.fullmatch(r"[A-Za-z0-9]{%d}" % self.expected_length, value) and score >= 0.80:
                    return value
        except Exception:
            self.last_error = "Local neural OCR inference failed"
            return None
        self.last_error = "Local neural OCR returned no valid candidate"
        return None
