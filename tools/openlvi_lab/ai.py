"""Optional on-premises Ollama narrative for pre-validated Fault Doctor findings.

Never sends raw sensor history, credentials, device addresses or owner data.
No actuator tools are exposed. If Ollama is unavailable, deterministic
Fault Doctor remains usable offline with no cloud subscription.
"""
from __future__ import annotations
import ipaddress
import json
import re
import urllib.parse
import urllib.request
from .core import number

_ALLOWED_MODEL = re.compile(r"^[a-zA-Z0-9._:-]{1,80}$")


def local_endpoint(url):
    parsed = urllib.parse.urlsplit(url)
    if (parsed.scheme != "http" or parsed.username or parsed.password
            or parsed.query or parsed.fragment or parsed.path not in ("", "/")
            or not parsed.hostname):
        raise ValueError("Use an uncredentialed local HTTP IP address, no URL path")
    try:
        address = ipaddress.ip_address(parsed.hostname)
    except ValueError as exc:
        raise ValueError("Ollama endpoint must use a literal IP address") from exc
    if (not isinstance(address, ipaddress.IPv4Address)
            or not (address.is_private or address.is_loopback)):
        raise ValueError("Only IPv4 private LAN or localhost endpoint allowed")
    port = parsed.port
    if port != 11434:
        raise ValueError("Only Ollama port 11434 is allowed")
    return f"http://{address}:{port}/api/generate"


def explain(findings, *, url, model="qwen2.5:0.5b", timeout=12, opener=None):
    """Compose a constrained local model response without any controller API."""
    if not isinstance(findings, list) or len(findings) > 24:
        raise ValueError("Expected at most 24 deterministic findings")
    if not isinstance(model, str) or not _ALLOWED_MODEL.fullmatch(model):
        raise ValueError("Invalid Ollama model name")
    if not isinstance(timeout, (float, int)) or not 1 <= timeout <= 30:
        raise ValueError("Timeout must be 1-30s")
    url = local_endpoint(url)
    allowed = []
    for item in findings:
        if not isinstance(item, dict):
            raise ValueError("Finding must be an object")
        code = item.get("code")
        severity = item.get("severity")
        if not isinstance(code, str) or not re.fullmatch(r"[a-z_]{1,45}", code):
            raise ValueError("Finding code invalid")
        if severity not in ("info", "warning", "critical"):
            raise ValueError("Finding severity invalid")
        evidence = {}
        for key, value in item.get("evidence", {}).items():
            if (isinstance(key, str) and re.fullmatch(r"[a-z_]{1,45}", key)
                    and type(value) in (int, float)):
                evidence[key] = number(value, key)
        allowed.append({"code": code, "severity": severity, "evidence": evidence})
    prompt = (
        "You are an English-language HVAC technician's advisory assistant. "
        "You may summarize ONLY the supplied verified numeric evidence and "
        "the coded observations. You cannot confirm faults, control equipment, "
        "invent sensor values or recommend overriding manufacturer safeties. "
        "Do not request keys or credentials. If evidence is inconclusive say so.\\n"
        + json.dumps(allowed, separators=(",", ":"))
    )
    payload = json.dumps({
        "model": model, "stream": False, "prompt": prompt,
        "options": {"temperature": 0.0, "num_predict": 280},
    }).encode("utf-8")
    req = urllib.request.Request(
        url, data=payload, method="POST",
        headers={"Content-Type": "application/json"},
    )
    open_fn = opener or urllib.request.urlopen
    with open_fn(req, timeout=timeout) as response:
        data = response.read(30000)
    obj = json.loads(data)
    answer = obj.get("response")
    if not isinstance(answer, str):
        raise ValueError("Ollama did not provide text")
    return {
        "response": answer[:4000],
        "source": "optional_local_ollama",
        "diagnosis_verified": False,
        "commands_issued": 0,
    }
