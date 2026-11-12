"""Bounded paid image solving; only image bytes leave the portal session."""
import base64
import re
import time

import requests

from .models import CheckError, Status


class TwoCaptcha:
    def __init__(self, key, length=6, session=None, sleep=time.sleep):
        self.key = key
        self.length = length
        self.session = session or requests.Session()
        self.sleep = sleep
        self.task_id = None
        self.last_error = None
        self.diagnostics = {"engine": "2captcha"}

    def _call(self, method, **payload):
        try:
            response = self.session.post(
                "https://api.2captcha.com/" + method,
                json={"clientKey": self.key, **payload}, timeout=10,
            )
            response.raise_for_status()
            data = response.json()
            if not isinstance(data, dict) or data.get("errorId") != 0:
                raise ValueError("Provider error")
            return data
        except (requests.RequestException, ValueError):
            raise CheckError(Status.CAPTCHA_FAILED,
                             "2Captcha request failed; check account balance/key and provider status") from None

    def recognize(self, content):
        self.task_id = None
        if not self.key:
            raise CheckError(Status.CAPTCHA_FAILED, "CAPTCHA_API_KEY secret is missing")
        if not content or len(content) > 100_000:
            raise CheckError(Status.CAPTCHA_FAILED, "Image exceeds 2Captcha input limits")
        result = self._call("createTask", task={
            "type": "ImageToTextTask", "body": base64.b64encode(content).decode("ascii"),
            "minLength": self.length, "maxLength": self.length,
        })
        task_id = result.get("taskId")
        if type(task_id) is not int or task_id <= 0:
            raise CheckError(Status.CAPTCHA_FAILED, "2Captcha returned no valid task ID")
        self.task_id = task_id
        # At most one paid creation per image; never retry an ambiguous creation.
        for _ in range(12):
            self.sleep(5)
            result = self._call("getTaskResult", taskId=task_id)
            if result.get("status") == "processing":
                continue
            value = result.get("solution", {}).get("text") if isinstance(result.get("solution"), dict) else None
            if result.get("status") == "ready" and isinstance(value, str):
                value = value.strip()
                if re.fullmatch(r"[A-Za-z0-9]{%d}" % self.length, value):
                    return value
            raise CheckError(Status.CAPTCHA_FAILED, "2Captcha returned an invalid answer")
        raise CheckError(Status.CAPTCHA_FAILED, "2Captcha polling limit reached")

    def report_incorrect(self):
        if self.task_id:
            try:
                self._call("reportIncorrect", taskId=self.task_id)
            except CheckError:
                self.diagnostics["report_failed"] = True
