from __future__ import annotations

import time
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


def get_provider(provider_id: str):
    if provider_id == "fixture":
        return FixtureProvider()
    if provider_id in {"openai", "anthropic", "google"}:
        raise ProviderError("config", f"provider '{provider_id}' requires credentials/configuration")
    raise ProviderError("config", f"unknown provider: {provider_id}")


def doctor(provider_id: str) -> dict[str, Any]:
    provider = get_provider(provider_id)
    return provider.doctor().as_dict()
