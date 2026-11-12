import io
import sys
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from visa_monitor.neural_ocr import NeuralOCR


@pytest.fixture
def image_bytes():
    from PIL import Image
    buffer = io.BytesIO()
    Image.new("RGB", (300, 50), "white").save(buffer, format="PNG")
    return buffer.getvalue()


def backend(monkeypatch, outputs):
    model = Mock(classification=Mock(side_effect=outputs))
    factory = Mock(return_value=model)
    monkeypatch.setitem(sys.modules, "ddddocr", SimpleNamespace(DdddOcr=factory))
    return model, factory


def test_neural_candidate_runs_locally_without_gpu(monkeypatch, image_bytes):
    model, factory = backend(monkeypatch, [{"text": "abc123", "confidence": 0.95}])
    ocr = NeuralOCR()
    assert ocr.recognize(image_bytes) == "abc123"
    factory.assert_called_once_with(show_ad=False, use_gpu=False)
    assert model.classification.call_count == 1
    assert "abc123" not in str(ocr.diagnostics)


def test_neural_normalization_fallback_is_bounded(monkeypatch, image_bytes):
    model, _ = backend(monkeypatch, [
        {"text": "bad", "confidence": 0.99},
        {"text": "abc123", "confidence": 0.91},
    ])
    ocr = NeuralOCR()
    assert ocr.recognize(image_bytes) == "abc123"
    assert model.classification.call_count == 2


@pytest.mark.parametrize("output", [
    {"text": "abc123", "confidence": 0.3},
    {"text": "abc123", "confidence": float("nan")},
    {"text": "<html>", "confidence": 1.0},
    {"text": "abc12", "confidence": 1.0},
])
def test_neural_rejects_invalid_or_low_score_output(monkeypatch, image_bytes, output):
    model, _ = backend(monkeypatch, [output, output])
    ocr = NeuralOCR()
    assert ocr.recognize(image_bytes) is None
    assert model.classification.call_count == 2
    assert ocr.last_error == "Local neural OCR returned no valid candidate"


def test_neural_inference_error_does_not_leak_exception(monkeypatch, image_bytes):
    backend(monkeypatch, [RuntimeError("private runtime data")])
    ocr = NeuralOCR()
    assert ocr.recognize(image_bytes) is None
    assert ocr.last_error == "Local neural OCR inference failed"
    assert "private" not in str(ocr.diagnostics)


def test_neural_invalid_image_does_not_invoke_model(monkeypatch):
    _, factory = backend(monkeypatch, [])
    ocr = NeuralOCR()
    assert ocr.recognize(b"not an image") is None
    assert ocr.last_error == "CAPTCHA image could not be decoded"
    assert not factory.called


def test_neural_model_is_reused(monkeypatch, image_bytes):
    _, factory = backend(monkeypatch, [{"text": "abc123", "confidence": 0.9}] * 2)
    ocr = NeuralOCR()
    assert ocr.recognize(image_bytes) == ocr.recognize(image_bytes) == "abc123"
    assert factory.call_count == 1
