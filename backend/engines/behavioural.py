"""
TrustLayer – Behavioural Biometrics Engine
==========================================
Analyses real keystroke cadence and form-fill behaviour captured
client-side.  Returns a score and structured flags.
"""
from __future__ import annotations
import statistics
from dataclasses import dataclass, field
from models import BehaviouralSignals

BOT_KEYSTROKE_INTERVAL_MS = 80        # ms — humans rarely type faster
BOT_CONSISTENCY_STD_THRESHOLD = 15.0  # ms std-dev — bots are unnaturally consistent
MIN_FORM_FILL_SECONDS = 5             # seconds — too fast = bot
MAX_PASTE_EVENTS = 3                  # paste > 3 is suspicious


@dataclass
class BehaviouralResult:
    score: float
    avg_keystroke_ms: float
    std_keystroke_ms: float
    form_fill_duration_s: float
    paste_events: int
    focus_losses: int
    bot_speed: bool
    bot_consistency: bool
    fast_form: bool
    paste_abuse: bool
    flags: list[str] = field(default_factory=list)
    signals: dict = field(default_factory=dict)


def analyse_behaviour(signals: BehaviouralSignals) -> BehaviouralResult:
    intervals = signals.keystroke_intervals_ms
    flags: list[str] = []
    deductions = 0.0

    # Keystroke speed analysis
    if len(intervals) >= 5:
        avg_ms = statistics.mean(intervals)
        std_ms = statistics.stdev(intervals) if len(intervals) > 1 else 0.0
    else:
        # Too few keystrokes → treat as pasted (suspicious)
        avg_ms = 0.0
        std_ms = 0.0

    bot_speed = avg_ms > 0 and avg_ms < BOT_KEYSTROKE_INTERVAL_MS
    bot_consistency = (
        len(intervals) >= 5 and
        std_ms < BOT_CONSISTENCY_STD_THRESHOLD and
        avg_ms < 120  # very fast AND very consistent
    )
    fast_form = signals.form_fill_duration_s < MIN_FORM_FILL_SECONDS and signals.form_fill_duration_s > 0
    paste_abuse = signals.paste_events > MAX_PASTE_EVENTS

    if bot_speed:
        flags.append("BEH_BOT_SPEED")
        deductions += 22
    if bot_consistency:
        flags.append("BEH_BOT_CONSISTENCY")
        deductions += 12
    if fast_form:
        flags.append("BEH_FAST_FORM")
        deductions += 10
    if paste_abuse:
        flags.append("BEH_PASTE_ABUSE")
        deductions += 8

    score = max(0.0, 100.0 - deductions)

    return BehaviouralResult(
        score=score,
        avg_keystroke_ms=round(avg_ms, 2),
        std_keystroke_ms=round(std_ms, 2),
        form_fill_duration_s=round(signals.form_fill_duration_s, 1),
        paste_events=signals.paste_events,
        focus_losses=signals.focus_losses,
        bot_speed=bot_speed,
        bot_consistency=bot_consistency,
        fast_form=fast_form,
        paste_abuse=paste_abuse,
        flags=flags,
        signals={
            "avg_keystroke_interval_ms": round(avg_ms, 1),
            "std_keystroke_interval_ms": round(std_ms, 1),
            "total_keystrokes": len(intervals),
            "form_fill_duration_s": signals.form_fill_duration_s,
            "paste_events": signals.paste_events,
            "focus_losses": signals.focus_losses,
        },
    )
