"""Offline evaluation; never contacts the portal. Keep the manifest and images private."""
import argparse
import json
from pathlib import Path
from visa_monitor.captcha import LocalOCR
from visa_monitor.neural_ocr import NeuralOCR

parser = argparse.ArgumentParser()
parser.add_argument("manifest",help="JSON list: image path, expected text, optional server_accepted boolean")
parser.add_argument("--engine", choices=["tesseract", "neural"], default="tesseract")
parser.add_argument("--length", type=int, default=6)
args = parser.parse_args()
path = Path(args.manifest)
samples = json.loads(path.read_text(encoding="utf-8"))
if not samples:
    raise SystemExit("No samples: recognition and verification rates are not measurable")
correct = submitted = accepted = 0
ocr = NeuralOCR(args.length) if args.engine == "neural" else LocalOCR()
for sample in samples:
    prediction = ocr.recognize((path.parent/sample["image"]).read_bytes())
    correct += prediction==sample["expected"]
    if sample.get("server_accepted") is not None:
        submitted += 1
        accepted += sample["server_accepted"] is True
print(json.dumps({"samples":len(samples),"exact_recognition_rate":correct/len(samples),
    "server_submissions":submitted,"server_acceptance_rate":accepted/submitted if submitted else None}))
