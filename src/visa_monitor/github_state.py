"""Durable non-sensitive state; missing/corrupt state fails closed."""
import base64
import os
import re
import requests
from .state import State

class StateStorageError(Exception):
    pass

class GitHubState:
    branch = "monitor-state"

    def __init__(self,repository=None,token=None,session=None):
        self.repository = repository or os.environ.get("GITHUB_REPOSITORY","")
        token = token or os.environ.get("GH_TOKEN","")
        if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+",self.repository) or not token:
            raise StateStorageError("GitHub repository or token missing")
        self.api = f"https://api.github.com/repos/{self.repository}"
        self.session = session or requests.Session()
        self.session.headers.update({"Authorization":f"Bearer {token}","Accept":"application/vnd.github+json",
                                     "X-GitHub-Api-Version":"2022-11-28"})
        self.sha = None
        self.new_branch = False

    def call(self,method,path,**kwargs):
        try:
            response = self.session.request(method,self.api+path,timeout=20,**kwargs)
        except requests.RequestException:
            raise StateStorageError("GitHub state request failed") from None
        if response.status_code not in (200,201,404):
            raise StateStorageError(f"GitHub state HTTP {response.status_code}; refusing unsafe reset")
        return response

    def load(self,initialize=False):
        response = self.call("GET",f"/contents/state.json?ref={self.branch}")
        if response.status_code==404:
            if not initialize:
                raise StateStorageError("State missing: run manual monitor with initialize_state once")
            branch = self.call("GET",f"/git/ref/heads/{self.branch}")
            if branch.status_code==200:
                raise StateStorageError("Existing state branch lacks state.json; investigate before resetting")
            self.new_branch = True
            return State()
        try:
            payload = response.json()
            self.sha = payload["sha"]
            return State.decode(base64.b64decode(payload["content"],validate=False).decode("utf-8"))
        except (KeyError,ValueError,TypeError):
            raise StateStorageError("Corrupt persistent state; refusing to reset") from None

    def save(self,state):
        if self.new_branch:
            commit = os.environ.get("GITHUB_SHA","")
            if not re.fullmatch(r"[a-fA-F0-9]{40}",commit):
                raise StateStorageError("GITHUB_SHA required for initial state branch")
            response = self.call("POST","/git/refs",json={"ref":f"refs/heads/{self.branch}","sha":commit})
            if response.status_code!=201:
                raise StateStorageError("Unable to initialize state branch")
            self.new_branch = False
        payload = {"message":"Update monitor state [skip ci]","branch":self.branch,
                   "content":base64.b64encode(state.encode().encode()).decode()}
        if self.sha:
            payload["sha"] = self.sha
        response = self.call("PUT","/contents/state.json",json=payload)
        if response.status_code not in (200,201):
            raise StateStorageError("Unable to persist monitor state")
        self.sha = response.json()["content"]["sha"]
