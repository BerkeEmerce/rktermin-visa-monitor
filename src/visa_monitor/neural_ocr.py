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
        self.models = None
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
        if self.models is None:
            try:
                self.models = [ddddocr.DdddOcr(show_ad=False, use_gpu=False, beta=beta)
                               for beta in (False, True)]
            except Exception:
                self.last_error = "Local neural OCR model initialization failed"
                return None
        try:
            # Reject high-scoring disagreements: the models' scores are not
            # calibrated probabilities of correct full-string recognition.
            for image in (original, contrast):
                values, scores = [], []
                for model in self.models:
                    result = model.classification(image, probability=True)
                    self.diagnostics["readings"] += 1
                    value = result.get("text", "")
                    score = float(result.get("confidence", 0))
                    if not isinstance(value, str) or not math.isfinite(score):
                        values.append(None)
                        continue
                    value = re.sub(r"\s", "", value)
                    scores.append(score)
                    valid = re.fullmatch(r"[A-Za-z0-9]{%d}" % self.expected_length, value)
                    values.append(value if valid and score >= 0.80 else None)
                self.diagnostics["agreement"] = bool(values[0] and values[0] == values[1])
                if self.diagnostics["agreement"]:
                    self.diagnostics["candidate_length"] = len(values[0])
                    self.diagnostics["score"] = round(min(scores), 4)
                    return values[0]
        except Exception:
            self.last_error = "Local neural OCR inference failed"
            return None
        self.last_error = "Local neural OCR models did not agree on a valid candidate"
        return None
