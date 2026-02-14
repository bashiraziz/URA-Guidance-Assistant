from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class CalculatorOutput:
    type: str
    inputs: dict
    outputs: dict
    explanation: str


def _extract_first_amount(text: str) -> float | None:
    match = re.search(r"(\d[\d,]*(?:\.\d+)?)", text.replace(",", ""))
    if not match:
        return None
    return float(match.group(1))


def should_run_vat(question: str) -> bool:
    lower = question.lower()
    return "vat" in lower and _extract_first_amount(question) is not None


def should_run_paye(question: str) -> bool:
    lower = question.lower()
    return "paye" in lower and _extract_first_amount(question) is not None


def calculate_vat(question: str, default_rate: float = 0.18) -> CalculatorOutput | None:
    amount = _extract_first_amount(question)
    if amount is None:
        return None

    lower = question.lower()
    inclusive = "inclusive" in lower or "includes vat" in lower or "vat included" in lower
    if inclusive:
        net = amount / (1 + default_rate)
        vat = amount - net
        gross = amount
        mode = "inclusive"
    else:
        net = amount
        vat = amount * default_rate
        gross = amount + vat
        mode = "exclusive"

    return CalculatorOutput(
        type="vat",
        inputs={"amount": round(amount, 2), "rate": default_rate, "mode": mode},
        outputs={"net_amount": round(net, 2), "vat_amount": round(vat, 2), "gross_amount": round(gross, 2)},
        explanation=f"Calculated VAT using a {default_rate * 100:.0f}% standard rate in {mode} mode.",
    )


def calculate_paye(question: str) -> CalculatorOutput | None:
    gross_income = _extract_first_amount(question)
    if gross_income is None:
        return None

    # Placeholder brackets for structure. Real brackets should come from DB/config.
    brackets = [
        (235000.0, 0.0),
        (335000.0, 0.1),
        (410000.0, 0.2),
    ]
    taxable = gross_income
    tax = 0.0
    previous_cap = 0.0
    for cap, rate in brackets:
        slice_amount = max(0.0, min(taxable, cap) - previous_cap)
        tax += slice_amount * rate
        previous_cap = cap
    if taxable > previous_cap:
        tax += (taxable - previous_cap) * 0.3

    return CalculatorOutput(
        type="paye",
        inputs={"gross_income": round(gross_income, 2), "currency": "UGX"},
        outputs={"estimated_paye": round(tax, 2), "net_income": round(gross_income - tax, 2)},
        explanation="PAYE result is a placeholder estimate; configure official brackets before production use.",
    )
