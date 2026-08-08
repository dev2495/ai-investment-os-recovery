from extract_governance_forensics import extract_observations_from_pages


def test_extracts_active_issues_and_no_adverse_disclosures_with_pages() -> None:
    pages = [
        "The statutory auditors have not reported any fraud. No whistle blower complaints were received.",
        "The report contains no qualification, reservation or adverse remark. Emphasis of Matter refers to Note 38.",
        "Proceedings in the CBI case remain ongoing. Under PMLA immovable property attachment of Rs. 190.37 crore remains in force.",
        "All related party transactions were in the ordinary course of business and on an arm's length basis.",
    ]

    rows = extract_observations_from_pages(pages, "2026-03-31")
    by_key = {row["observation_key"]: row for row in rows}

    assert by_key["statutory_audit_no_qualification"]["source_page"] == 2
    assert by_key["statutory_audit_emphasis_of_matter"]["severity"] == "high"
    assert by_key["cbi_proceedings_ongoing"]["observation_status"] == "active_issue"
    assert by_key["pmla_property_attachment"]["disclosed_value"] == 190.37
    assert by_key["related_party_arm_length_disclosure"]["source_page"] == 4
    assert by_key["whistleblower_complaints_none"]["source_page"] == 1
    assert all(row["verification_status"] == "machine_extracted" for row in rows)


def test_does_not_infer_missing_disclosures() -> None:
    rows = extract_observations_from_pages(["The board reviewed general operations."], "2026-03-31")
    assert rows == []
