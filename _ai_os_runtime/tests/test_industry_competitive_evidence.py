from extract_industry_competitive_evidence import extract_industry_observations_from_pages


def test_extracts_quantified_and_explicitly_unavailable_market_share() -> None:
    rows=extract_industry_observations_from_pages([
      "Our global market share is small, but we now have capabilities.",
      "We are augmenting our rope and wire capacity by 40,000 MT.",
      "We are moving from being a producer of standard products to a provider of engineered, high-performance solutions.",
      "Infrastructure investment is lifting demand across cranes, ports and piling. Urbanisation is driving demand for elevator ropes.",
      "Every rope is a consumable replaced on a safety-mandated cycle.",
    ],"2026-03-31")
    by_key={row["observation_key"]:row for row in rows}
    assert by_key["global_market_share_small"]["metric_availability"]=="not_disclosed"
    assert by_key["rope_wire_capacity_added_40000_mt"]["value_numeric"]==40000
    assert len(rows)==5
