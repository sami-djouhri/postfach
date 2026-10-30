import json
import logging
import re

import httpx

from app.config import settings
from app.schemas import FristItem, LlmAnalysisResult

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "Du bist ein Assistent zur Briefanalyse. Analysiere den folgenden gescannten Brieftext.\n"
    "Antworte ausschliesslich als reines JSON-Objekt, ohne Markdown-Codeblock und ohne Kommentar.\n"
    'Schema: {"absender":"...","kategorie":"...","titel":"...","zusammenfassung":"...",'
    '"fristen":[{"typ":"zahlung|kuendigung|antwort|termin","datum":"YYYY-MM-DD","beschreibung":"..."}]}\n'
    "Kategorien: Rechnung, Vertrag, Behoerde, Versicherung, Bank, Gesundheit, Sonstiges.\n"
    "Wenn keine Fristen vorhanden sind, gib ein leeres Array zurueck. titel: 3-8 Worte, sprechend."
)

# llama.cpp/llama-server: Modell-Name aus /v1/models; wir lassen es bei "default" weil
# der Server jeweils nur ein geladenes Modell bedient.
_MODEL_NAME = "default"

# Strippt umschliessende ```json ... ``` oder ``` ... ``` Codeblöcke, die viele LLMs
# trotz Anweisung zurückgeben.
_JSON_FENCE_RE = re.compile(r"^\s*```(?:json)?\s*(.*?)\s*```\s*$", re.DOTALL)


def _strip_codeblock(text: str) -> str:
    m = _JSON_FENCE_RE.match(text)
    return m.group(1) if m else text


class LlmService:
    def __init__(self):
        self.base_url = settings.LLM_BASE_URL.rstrip("/")
        self.timeout = settings.LLM_TIMEOUT_SEC

    async def is_available(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                resp = await client.get(f"{self.base_url}/health")
                return resp.status_code == 200
        except Exception:
            return False

    async def analyze(self, ocr_text: str) -> LlmAnalysisResult:
        if not ocr_text or not ocr_text.strip():
            return LlmAnalysisResult(error="Kein OCR-Text vorhanden")

        if not await self.is_available():
            return LlmAnalysisResult(error="KI nicht verfuegbar")

        # Sehr lange Briefe abschneiden: der Anfang trägt typischerweise Absender + Anliegen.
        text = ocr_text[:3000]

        payload = {
            "model": _MODEL_NAME,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": text},
            ],
            "temperature": 0.1,
            "max_tokens": 320,
            # llama.cpp respektiert response_format wenn neuerer Build; ältere ignorieren es ohne Fehler.
            "response_format": {"type": "json_object"},
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.post(f"{self.base_url}/v1/chat/completions", json=payload)
                resp.raise_for_status()
                data = resp.json()
                content = data["choices"][0]["message"]["content"].strip()
        except httpx.TimeoutException:
            return LlmAnalysisResult(error="KI-Analyse Timeout (Server zu langsam)")
        except Exception as e:
            logger.error("LLM request failed: %s", e)
            return LlmAnalysisResult(error=f"KI-Fehler: {str(e)}")

        cleaned = _strip_codeblock(content)
        try:
            result = json.loads(cleaned)
        except json.JSONDecodeError:
            logger.warning("LLM returned non-JSON response: %s", content[:300])
            return LlmAnalysisResult(error="KI-Antwort konnte nicht verarbeitet werden")

        fristen = []
        for f in result.get("fristen", []) or []:
            if isinstance(f, dict) and f.get("datum") and f.get("beschreibung"):
                fristen.append(FristItem(
                    typ=f.get("typ", "termin"),
                    datum=f["datum"],
                    beschreibung=f["beschreibung"],
                ))
        return LlmAnalysisResult(
            titel=result.get("titel"),
            absender=result.get("absender"),
            kategorie=result.get("kategorie"),
            zusammenfassung=result.get("zusammenfassung"),
            fristen=fristen,
        )
