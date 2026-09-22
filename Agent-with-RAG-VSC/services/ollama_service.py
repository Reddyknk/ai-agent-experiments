from __future__ import annotations

import os
import shutil
import subprocess
import time
from typing import Any

import requests

from config import OLLAMA_BASE_URL


class OllamaManager:
    def __init__(self):
        self.started_by_app = False

    def is_running(self) -> bool:
        try:
            result = subprocess.run(["ollama", "ps"], capture_output=True, text=True, check=False)
            return result.returncode == 0
        except FileNotFoundError:
            return False

    def ensure_running(self) -> bool:
        if self.is_running():
            return False
        if shutil.which("ollama") is None:
            return False
        subprocess.Popen(["ollama", "serve"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.started_by_app = True
        time.sleep(1)
        return True

    def stop_if_started_by_app(self) -> None:
        if self.started_by_app and self.is_running():
            try:
                subprocess.run(["ollama", "stop", "all"], check=False, capture_output=True)
            except Exception:
                pass
            self.started_by_app = False

    def list_models(self) -> list[str]:
        try:
            result = subprocess.run(["ollama", "list"], capture_output=True, text=True, check=False)
            if result.returncode != 0:
                return []
            lines = result.stdout.strip().splitlines()[1:]
            return [line.split()[0] for line in lines if line.strip()]
        except FileNotFoundError:
            return []

    def list_generation_models(self) -> list[str]:
        try:
            response = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=5)
            response.raise_for_status()
            models = response.json().get("models", [])
            return [
                model.get("name")
                for model in models
                if model.get("name") and "embedding" not in model.get("capabilities", [])
            ]
        except (requests.RequestException, ValueError, TypeError):
            return []

    def pull_model(self, model_name: str) -> bool:
        if shutil.which("ollama") is None:
            return False
        result = subprocess.run(["ollama", "pull", model_name], capture_output=True, text=True, check=False)
        return result.returncode == 0
