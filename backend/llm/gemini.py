"""
TrustLayer – Gemini LLM Integration
=====================================
Sends structured assessment signals to Gemini 1.5 Flash and returns
a concise, professional risk-analyst-style narrative.

Gracefully falls back to a high-quality templated explanation if the API
key is missing or the API call fails.
"""
from __future__ import annotations
import json
from backend.config import GEMINI_API_KEY, GEMINI_MODEL


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
    if GEMINI_API_KEY == "PASTE_KEY_HERE" or not GEMINI_API_KEY:
        return _template_explanation(trust_score, decision, risk_band, reason_codes, pipeline_scores)

    try:
        import google.generativeai as genai  # type: ignore
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel(GEMINI_MODEL)

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

        response = model.generate_content(prompt)
        return response.text.strip()

    except Exception as exc:
        # Log but don't crash – return templated explanation
        print(f"[LLM] Gemini call failed ({exc}), using template fallback")
        return _template_explanation(trust_score, decision, risk_band, reason_codes, pipeline_scores)
