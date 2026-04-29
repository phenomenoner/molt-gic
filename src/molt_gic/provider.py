from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any


class ProviderError(RuntimeError):
    def __init__(self, error_class: str, message: str):
        super().__init__(message)
        self.error_class = error_class


@dataclass(frozen=True)
class ProviderReceipt:
    provider: str
    role: str
    model: str
    model_version: str
    latency_ms: int
    cost_usd: float
    retries: int
    status: str
    error_class: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "role": self.role,
            "model": self.model,
            "model_version": self.model_version,
            "latency_ms": self.latency_ms,
            "cost_usd": self.cost_usd,
            "retries": self.retries,
            "status": self.status,
            "error_class": self.error_class,
        }


class FixtureProvider:
    provider_id = "fixture"
    model = "fixture-deterministic"
    model_version = "v1-fixture"

    def doctor(self) -> ProviderReceipt:
        start = time.time()
        return ProviderReceipt(self.provider_id, "doctor", self.model, self.model_version, int((time.time() - start) * 1000), 0.0, 0, "ok")

    def run(self, role: str, prompt: str, timeout_s: float = 30.0) -> tuple[str, ProviderReceipt]:
        start = time.time()
        if timeout_s <= 0:
            raise ProviderError("timeout", "fixture provider timeout")
        if "MOLT_GIC_BAD_PROVIDER_KEY" in prompt:
            raise ProviderError("auth", "fixture provider bad key")
        output = f"[{role}:{self.model_version}] " + prompt[:500]
        receipt = ProviderReceipt(self.provider_id, role, self.model, self.model_version, int((time.time() - start) * 1000), 0.0, 0, "ok")
        return output, receipt


class OpenAICompatibleProvider:
    provider_id = "openai_compatible"

    def __init__(self) -> None:
        self.base_url = os.environ.get("MOLT_GIC_PROVIDER_BASE_URL", "").rstrip("/")
        self.api_key = os.environ.get("MOLT_GIC_PROVIDER_API_KEY", "")
        self.model = os.environ.get("MOLT_GIC_PROVIDER_MODEL", "gpt-4o-mini")
        self.model_version = os.environ.get("MOLT_GIC_PROVIDER_MODEL_VERSION", self.model)
        self.timeout_s = float(os.environ.get("MOLT_GIC_PROVIDER_TIMEOUT", "30"))

    def _check_config(self) -> None:
        if not self.base_url:
            raise ProviderError("config", "MOLT_GIC_PROVIDER_BASE_URL is required")
        if not self.api_key:
            raise ProviderError("config", "MOLT_GIC_PROVIDER_API_KEY is required")

    def doctor(self) -> ProviderReceipt:
        self._check_config()
        start = time.time()
        return ProviderReceipt(self.provider_id, "doctor", self.model, self.model_version, int((time.time() - start) * 1000), 0.0, 0, "ok")

    def run(self, role: str, prompt: str, timeout_s: float | None = None) -> tuple[str, ProviderReceipt]:
        self._check_config()
        start = time.time()
        url = f"{self.base_url}/chat/completions"
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": f"You are the molt-gic {role}. Return concise JSON-safe text."},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0,
        }
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"content-type": "application/json", "authorization": f"Bearer {self.api_key}"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout_s or self.timeout_s) as resp:
                body = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            if exc.code in {401, 403}:
                raise ProviderError("auth", f"provider auth failed: HTTP {exc.code}") from exc
            raise ProviderError("provider_unavailable", f"provider HTTP error: {exc.code}") from exc
        except TimeoutError as exc:
            raise ProviderError("timeout", "provider request timed out") from exc
        except urllib.error.URLError as exc:
            reason = getattr(exc, "reason", exc)
            if isinstance(reason, TimeoutError):
                raise ProviderError("timeout", "provider request timed out") from exc
            raise ProviderError("provider_unavailable", f"provider unavailable: {reason}") from exc
        try:
            text = body["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise ProviderError("malformed_output", "provider response missing choices[0].message.content") from exc
        latency = int((time.time() - start) * 1000)
        usage = body.get("usage") or {}
        tokens = int(usage.get("total_tokens") or 0)
        cost = tokens * float(os.environ.get("MOLT_GIC_PROVIDER_COST_PER_TOKEN", "0"))
        receipt = ProviderReceipt(self.provider_id, role, self.model, self.model_version, latency, cost, 0, "ok")
        return text, receipt


def get_provider(provider_id: str):
    if provider_id == "fixture":
        return FixtureProvider()
    if provider_id in {"openai_compatible", "openai", "openrouter"}:
        return OpenAICompatibleProvider()
    if provider_id in {"anthropic", "google"}:
        raise ProviderError("config", f"provider '{provider_id}' is not implemented in this adapter yet")
    raise ProviderError("config", f"unknown provider: {provider_id}")


def doctor(provider_id: str) -> dict[str, Any]:
    provider = get_provider(provider_id)
    return provider.doctor().as_dict()
