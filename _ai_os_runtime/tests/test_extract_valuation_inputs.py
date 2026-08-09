from extract_valuation_inputs import extract_valuation_inputs_from_pages


def test_extracts_consolidated_diluted_inputs() -> None:
    page = """The following reflects the income and share data used in the basic and diluted EPS computations:
    Profit for the year from continuing operations 49,088 40,739
    Weighted average number of equity shares outstanding for the purpose of basic EPS (B) 30,45,07,507 30,47,10,987
    Weighted average number of equity shares adjusted for the effect of dilution (C) 30,47,41,780 30,47,41,780
    Basic EPS (in Rs.) 16.12 13.37 Diluted EPS (in Rs.) 16.11 13.37"""
    rows = extract_valuation_inputs_from_pages(["cover", page], 2026)
    by_key = {row["input_key"]: row for row in rows}
    assert by_key["diluted_weighted_average_shares"]["value_numeric"] == 304741780
    assert by_key["basic_weighted_average_shares"]["value_numeric"] == 304507507
    assert by_key["diluted_eps_continuing"]["value_numeric"] == 16.11
    assert all(row["source_page"] == 2 for row in rows)


def test_rejects_page_without_required_labels() -> None:
    assert extract_valuation_inputs_from_pages(["EPS was discussed without a table"], 2026) == []
