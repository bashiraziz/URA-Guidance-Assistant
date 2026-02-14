from app.services.calculators import calculate_vat


def test_vat_exclusive_mode():
    result = calculate_vat("Compute VAT on 100000 UGX")
    assert result is not None
    assert result.outputs["net_amount"] == 100000.0
    assert result.outputs["vat_amount"] == 18000.0
    assert result.outputs["gross_amount"] == 118000.0


def test_vat_inclusive_mode():
    result = calculate_vat("VAT inclusive amount is 118000 UGX")
    assert result is not None
    assert round(result.outputs["net_amount"], 2) == 100000.0
    assert round(result.outputs["vat_amount"], 2) == 18000.0
