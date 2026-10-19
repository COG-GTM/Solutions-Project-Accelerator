"""Industrial Automation Parameter Extraction using optional Ollama LLM support.

This module defines a class `IndustrialParameterExtractor` that can extract:
 - Tagname / Object identifier (e.g., LIT1005)
 - Parameter name (chosen from provided parameter hints)
 - Parameter value (numeric / string) from natural language text

Design Goals:
 1. Fast rule-based baseline (no model required)
 2. Optional enhancement via an Ollama local model (if installed)
 3. Clear reasoning trace to aid debugging

Example:
    >>> hints = ["CfgLoLo", "CfgLo", "CfgHi", "CfgHiHi"]
    >>> text = "The high high limit of Water Tank Level (LIT1005) should be 90%"
    >>> extractor = IndustrialParameterExtractor(hints)
    >>> result = extractor.extract(text)
    >>> result['tagname']
    'LIT1005'
    >>> result['parameter']
    'CfgHiHi'
    >>> result['value']
    '90'

Integration Notes:
 - If you want to force using the LLM classification, pass use_llm=True.
 - Ollama invocation is attempted via subprocess calling: `ollama run <model>`.
 - If Ollama or the model is not available, the code silently falls back to rules.

Limitations / Future Enhancements:
 - Add unit inference (%, PSI, °C) to the value metadata.
 - Add confidence calibration using statistical scoring across multiple candidate phrases.
 - Extend tagname regex patterns to site-specific conventions if necessary.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
import math
import os
import re
import subprocess
import textwrap
import shutil
from typing import List, Optional, Dict, Any


TAGNAME_REGEXES = [
    # Common instrumentation tag styles: PREFIX + digits, optionally inside parentheses
    re.compile(r"\b([A-Z]{2,6}\d{3,6})\b"),
    re.compile(r"\(([A-Z]{2,6}\d{3,6})\)"),
]

# Parameter semantic cue dictionary. Keys are canonical semantic labels.
PARAMETER_CUES = {
    "CfgLoLo": ["low low", "lolo", "lo-lo", "very low", "min min", "minimum minimum"],
    "CfgLo": ["low", "lo", "minimum", "min"],
    "CfgHiHi": ["high high", "hihi", "hi-hi", "very high", "max max", "maximum maximum"],
    "CfgHi": ["high", "hi", "maximum", "max"],
}

# Ranking severity for tie-breaking when multiple cues match
SEVERITY_ORDER = {"CfgLoLo": 0, "CfgLo": 1, "CfgHi": 2, "CfgHiHi": 3}

# Value extraction regex (captures integers / decimals with optional percent sign)
VALUE_REGEX = re.compile(r"(?<![A-Za-z0-9_])(\d+(?:\.\d+)?)(\s*%)?\b")


@dataclass
class ExtractionResult:
    tagname: Optional[str]
    parameter: Optional[str]
    value: Optional[str]
    confidence: float
    reasoning: str
    metadata: Dict[str, Any]

    def as_dict(self) -> Dict[str, Any]:  # convenience for serialization
        return {
            "tagname": self.tagname,
            "parameter": self.parameter,
            "value": self.value,
            "confidence": self.confidence,
            "reasoning": self.reasoning,
            "metadata": self.metadata,
        }


class IndustrialParameterExtractor:
    """Extracts parameters for industrial automation objects from natural language text.

    Parameters
    ----------
    parameter_hints: list[str]
        List of parameter names that are valid targets (e.g., ["CfgLoLo", "CfgLo", "CfgHi", "CfgHiHi"]).
    model_name: str, optional
        Ollama model to use when use_llm=True (default: 'llama3')
    use_llm: bool
        If True, attempt to classify parameter using an LLM; else rule-based only.
    llm_timeout: int
        Timeout in seconds for Ollama subprocess.
    """

    def __init__(
        self,
        parameter_hints: List[str],
        model_name: str = "llama3",
        use_llm: bool = False,
        llm_timeout: int = 10,
    ) -> None:
        self.parameter_hints = parameter_hints
        self.model_name = model_name
        self.use_llm = use_llm
        self.llm_timeout = llm_timeout

    # ---------------- Public API ---------------- #
    def extract(self, text: str) -> Dict[str, Any]:
        """Run extraction pipeline on input text.

        Returns a dictionary with keys: tagname, parameter, value, confidence, reasoning, metadata.
        """
        reasoning_parts: List[str] = []

        tagname = self._extract_tagname(text)
        if tagname:
            reasoning_parts.append(f"Tagname identified: {tagname}")
        else:
            reasoning_parts.append("No tagname found with current regex patterns.")

        numeric_candidates = list(self._extract_values(text))
        reasoning_parts.append(
            f"Numeric candidates: {', '.join(c['match'] for c in numeric_candidates) if numeric_candidates else 'None'}"
        )

        parameter = None
        parameter_conf = 0.0
        rule_meta = {}

        # Rule-based selection
        if self.parameter_hints:
            parameter, parameter_conf, rule_meta = self._classify_parameter_rules(text, numeric_candidates)
            reasoning_parts.append(
                f"Rule-based parameter decision: {parameter} (confidence={parameter_conf:.2f})"
                if parameter else "Rule-based classification failed to select a parameter."
            )

        # Optional LLM refinement
        llm_used = False
        if self.use_llm and parameter is not None:
            llm_choice, llm_conf, llm_reason = self._classify_parameter_llm(text, numeric_candidates)
            if llm_choice and llm_conf >= parameter_conf:
                reasoning_parts.append(f"LLM override: {llm_choice} (conf={llm_conf:.2f}) reason: {llm_reason}")
                parameter = llm_choice
                parameter_conf = llm_conf
                llm_used = True
            elif llm_choice:
                reasoning_parts.append(
                    f"LLM suggestion {llm_choice} (conf={llm_conf:.2f}) rejected; lower than rule confidence {parameter_conf:.2f}."
                )
            else:
                reasoning_parts.append("LLM classification unavailable or failed.")

        # Pick value: choose value nearest to parameter semantic cues region or last number if ambiguous
        value, value_conf, value_meta = self._select_value(text, parameter, numeric_candidates)
        if value:
            reasoning_parts.append(f"Value selected: {value} (confidence={value_conf:.2f})")
        else:
            reasoning_parts.append("No value extracted.")

        # Aggregate confidence (heuristic: geometric mean of non-zero confidences)
        conf_components = [c for c in [parameter_conf, value_conf] if c > 0]
        if conf_components:
            agg_conf = math.prod(conf_components) ** (1 / len(conf_components))
        else:
            agg_conf = 0.0

        reasoning = " | ".join(reasoning_parts)
        result = ExtractionResult(
            tagname=tagname,
            parameter=parameter,
            value=value,
            confidence=round(agg_conf, 3),
            reasoning=reasoning,
            metadata={
                "rule_meta": rule_meta,
                "value_meta": value_meta,
                "llm_used": llm_used,
                "parameter_hints": self.parameter_hints,
            },
        )
        return result.as_dict()

    # ---------------- Tagname Extraction ---------------- #
    def _extract_tagname(self, text: str) -> Optional[str]:
        for pattern in TAGNAME_REGEXES:
            match = pattern.search(text)
            if match:
                return match.group(1)
        return None

    # ---------------- Parameter Classification (Rules) ---------------- #
    def _classify_parameter_rules(self, text: str, numeric_candidates: List[Dict[str, Any]]):
        lowered = text.lower()
        scores = {}
        cue_spans = {}
        for hint in self.parameter_hints:
            cues = PARAMETER_CUES.get(hint, [])
            score = 0
            spans = []
            for cue in cues:
                for m in re.finditer(re.escape(cue), lowered):
                    score += len(cue.split())  # weight by phrase length
                    spans.append((m.start(), m.end()))
            # Additional generic cues based on direction
            if hint.lower().startswith("cfglo"):
                if re.search(r"\b(low(?!\s*high)|below|less than|min(?:imum)?)\b", lowered):
                    score += 0.5
            if hint.lower().startswith("cfghi"):
                if re.search(r"\b(high(?!\s*low)|above|greater than|max(?:imum)?)\b", lowered):
                    score += 0.5
            if score:
                scores[hint] = score
                cue_spans[hint] = spans

        if not scores:
            return None, 0.0, {"detail": "No cues matched"}

        # If multiple, tie-break by highest score then severity order if both in same direction region
        best = sorted(scores.items(), key=lambda kv: (kv[1], SEVERITY_ORDER.get(kv[0], -1)))
        best_hint, best_score = best[-1]

        # Normalize score to [0,1]
        max_possible = max(s for _, s in scores.items())
        conf = best_score / (max_possible if max_possible else 1)

        return best_hint, conf, {"scores": scores, "cue_spans": cue_spans}

    # ---------------- LLM Parameter Classification (Optional) ---------------- #
    def _classify_parameter_llm(self, text: str, numeric_candidates: List[Dict[str, Any]]):
        if not self._ollama_available():  # early out
            return None, 0.0, "Ollama not available"

        prompt = self._build_llm_prompt(text)
        try:
            completed = subprocess.run(
                ["ollama", "run", self.model_name],
                input=prompt.encode("utf-8"),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=self.llm_timeout,
            )
        except Exception as e:  # noqa: BLE001
            return None, 0.0, f"LLM invoke failed: {e}"

        if completed.returncode != 0:
            return None, 0.0, f"LLM error: {completed.stderr.decode(errors='ignore')[:120]}"

        raw = completed.stdout.decode(errors="ignore").strip()
        # Expect a JSON object or a line with parameter name
        llm_choice = None
        reasoning = raw
        confidence = 0.0
        try:
            possible_json = self._extract_json(raw)
            if possible_json:
                llm_choice = possible_json.get("parameter")
                confidence = float(possible_json.get("confidence", 0.0))
                reasoning = possible_json.get("reasoning", raw)
            else:
                # fallback: search for a hint token
                for hint in self.parameter_hints:
                    if hint.lower() in raw.lower():
                        llm_choice = hint
                        confidence = 0.55  # baseline if not provided
                        break
        except Exception:  # noqa: BLE001
            pass

        if llm_choice not in self.parameter_hints:
            return None, 0.0, reasoning[:160]
        return llm_choice, confidence, reasoning[:400]

    def _build_llm_prompt(self, text: str) -> str:
        hints = ", ".join(self.parameter_hints)
        prompt = f"""
You are an assistant for extracting which configuration parameter (one of: {hints}) is referenced in the following text.
Return a compact JSON with keys: parameter, confidence (0-1), reasoning (short).
If unsure, pick the most semantically appropriate; prefer highest severity if phrase contains 'high high' or 'low low'.
Text: {text}
JSON:
"""
        return textwrap.dedent(prompt).strip()

    def _extract_json(self, s: str) -> Optional[Dict[str, Any]]:
        match = re.search(r"\{.*?\}", s, flags=re.DOTALL)
        if not match:
            return None
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            return None

    def _ollama_available(self) -> bool:
        return bool(shutil.which("ollama"))

    # ---------------- Value Selection ---------------- #
    def _extract_values(self, text: str):
        for m in VALUE_REGEX.finditer(text):
            yield {
                "match": m.group(1),
                "full": m.group(0),
                "span": m.span(1),
                "percent": bool(m.group(2)),
            }

    def _select_value(self, text: str, parameter: Optional[str], numeric_candidates: List[Dict[str, Any]]):
        if not numeric_candidates:
            return None, 0.0, {"detail": "No numeric candidates"}
        if len(numeric_candidates) == 1:
            cand = numeric_candidates[0]
            return cand["match"], 0.9, {"strategy": "single_candidate"}

        lowered = text.lower()
        best = None
        best_score = -1
        for cand in numeric_candidates:
            # Base score: later numbers closer to end often used for assignment
            span_mid = (cand["span"][0] + cand["span"][1]) / 2
            base = span_mid / len(text)
            score = base
            window = lowered[max(0, cand["span"][0]-25): cand["span"][1]+25]
            if parameter:
                cues = PARAMETER_CUES.get(parameter, [])
                for cue in cues:
                    if cue in window:
                        score += 1.0
            # keywords indicating value
            if re.search(r"\b(set(?:point)?|should be|=|equals?|limit|configured? to)\b", window):
                score += 0.8
            if cand["percent"]:
                score += 0.2
            if score > best_score:
                best_score = score
                best = cand

        if not best:
            return None, 0.0, {"detail": "Scoring failed"}

        # Normalize confidence (heuristic)
        conf = min(1.0, 0.5 + best_score / (best_score + 1.5))
        return best["match"], conf, {"strategy": "scored", "score": best_score, "span": best["span"]}


# ---------------- Simple CLI Demo ---------------- #
def _demo():  # pragma: no cover - convenience function
    import argparse
    parser = argparse.ArgumentParser(description="Industrial Parameter Extraction Demo")
    parser.add_argument("text", help="Input sentence containing tagname and parameter value")
    parser.add_argument("--hints", nargs="*", default=["CfgLoLo", "CfgLo", "CfgHi", "CfgHiHi"], help="Parameter hints")
    parser.add_argument("--llm", action="store_true", help="Use Ollama model if available")
    args = parser.parse_args()
    extractor = IndustrialParameterExtractor(args.hints, use_llm=args.llm)
    result = extractor.extract(args.text)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":  # pragma: no cover
    _demo()
