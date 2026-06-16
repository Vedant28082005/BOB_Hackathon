"""
TrustLayer – LLM Narration Integration
=======================================
Sends structured assessment signals to an NVIDIA NIM (OpenAI-compatible)
DeepSeek model and returns a concise, professional risk-analyst narrative.

Gracefully falls back to a high-quality templated explanation if the API
key is missing or the API call fails.
"""
from __future__ import annotations
import json
from config import settings

# Reused OpenAI client (points at NVIDIA's OpenAI-compatible endpoint).
_client = None


def _get_client():
    global _client
    if _client is None:
        from openai import OpenAI
        _client = OpenAI(
            base_url=settings.nvidia_base_url,
            api_key=settings.nvidia_api_key,
        )
    return _client


def _template_explanation(
    trust_score: float,
    decision: str,
    risk_band: str,
    reason_codes: list[dict],
    pipeline_scores: dict[str, float],
) -> str:
    critical = [rc for rc in reason_codes if rc["severity"] in ("CRITICAL", "HIGH")]
    info = [rc for rc in reason_codes if rc["severity"] == "INFO"]

    decision_prose = {
        "APPROVE":        "The applicant's identity has been verified with high confidence. All mandatory checks have passed and no material risk signals were detected.",
        "STEP_UP":        "The applicant's identity could not be fully verified at this stage. One or more signals require additional verification before a final decision can be reached.",
        "MANUAL_REVIEW":  "The automated assessment has flagged this application for mandatory human review. Significant risk signals were identified that cannot be resolved by automated means alone.",
        "REJECT":         "The application has been automatically declined. One or more hard-fail conditions were triggered that render this identity submission unacceptable.",
    }.get(decision, "Assessment complete.")

    risk_prose = {
        "LOW":      "The overall risk profile is low, with strong signal consistency across all verification channels.",
        "MEDIUM":   "The risk profile is moderate. While most signals are within acceptable bounds, some inconsistencies were detected.",
        "HIGH":     "The risk profile is elevated. Multiple concerning signals were identified across the verification pipeline.",
        "CRITICAL": "The risk profile is critical. The application exhibits strong indicators of fraudulent or deceptive behaviour.",
    }.get(risk_band, "")

    issues_prose = ""
    if critical:
        issue_list = "; ".join(f"{rc['title']} ({rc['severity']})" for rc in critical[:3])
        issues_prose = f" The primary drivers of this decision are: {issue_list}."

    doc_s = pipeline_scores.get("document", 0)
    bio_s = pipeline_scores.get("biometric", 0)
    dev_s = pipeline_scores.get("device", 0)
    beh_s = pipeline_scores.get("behavioural", 0)
    graph_s = pipeline_scores.get("identity_graph", 0)

    return (
        f"{decision_prose} {risk_prose}{issues_prose} "
        f"Stage scores — Document forensics: {doc_s:.0f}/100; "
        f"Biometric verification: {bio_s:.0f}/100; "
        f"Device & network signals: {dev_s:.0f}/100; "
        f"Behavioural biometrics: {beh_s:.0f}/100; "
        f"Identity graph: {graph_s:.0f}/100. "
        f"Composite trust score: {trust_score:.1f}/100 (Risk band: {risk_band})."
    )


def generate_explanation(
    trust_score: float,
    decision: str,
    risk_band: str,
    reason_codes: list[dict],
    pipeline_scores: dict[str, float],
    applicant_name: str,
) -> str:
    key = settings.nvidia_api_key
    if not key or key == "PASTE_KEY_HERE":
        return _template_explanation(trust_score, decision, risk_band, reason_codes, pipeline_scores)

    prompt = f"""You are a senior fraud analyst at a digital bank writing an internal risk-decisioning report.
Write a concise (3-5 sentences), professional explanation of the following KYC assessment outcome.
Be specific about the signals that drove the decision. Use precise, analyst-grade language.
Do NOT mention that you are an AI. Do NOT use bullet points – write in flowing prose.

Assessment summary:
- Applicant: {applicant_name}
- Trust Score: {trust_score}/100
- Risk Band: {risk_band}
- Decision: {decision}
- Reason codes: {json.dumps([{"code": r["code"], "severity": r["severity"], "title": r["title"]} for r in reason_codes if r["severity"] != "INFO"], indent=2)}
- Pipeline stage scores: {json.dumps(pipeline_scores)}

Write the explanation now:"""

    try:
        completion = _get_client().chat.completions.create(
            model=settings.nvidia_model,
            messages=[{"role": "user", "content": prompt}],
            temperature=1,
            top_p=0.95,
            max_tokens=16384,
            extra_body={"chat_template_kwargs": {"thinking": True, "reasoning_effort": "high"}},
            stream=False,
        )
        text = (completion.choices[0].message.content or "").strip()
        return text or _template_explanation(trust_score, decision, risk_band, reason_codes, pipeline_scores)

    except Exception as exc:
        # Log but don't crash – return templated explanation
        print(f"[LLM] NVIDIA call failed ({exc}), using template fallback")
        return _template_explanation(trust_score, decision, risk_band, reason_codes, pipeline_scores)
