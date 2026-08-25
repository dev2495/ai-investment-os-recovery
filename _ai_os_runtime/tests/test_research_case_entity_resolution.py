import unittest

from research_case_helpers import extract_research_entity, propose_research_case, start_research_case


def literal(value):
    return "'" + str(value).replace("'", "''") + "'"


def jsonb(value):
    import json
    return literal(json.dumps(value)) + "::jsonb"


class ResearchCaseEntityResolutionTests(unittest.TestCase):
    def test_stale_selected_company_id_does_not_override_unique_ticker_match(self):
        statements = []

        def rows(sql):
            if "FROM research.companies company" in sql:
                return [{
                    "company_id": 28, "company_key": "nse:mstcltd",
                    "legal_name": "Mstc Limited", "display_name": "MSTC",
                    "ticker": "MSTCLTD", "exchange": "NSE",
                    "holding_thesis_id": None,
                }]
            return []

        def statement(sql):
            statements.append(sql)
            return [{"id": 901, "company_id": 28, "ticker": "MSTCLTD", "status": "proposed"}]

        result = propose_research_case({
            "request_text": "Start research on MSTC", "entity": "MSTC",
            "company_id": 1,  # stale Usha Martin selection from the page
            "horizon": "3-5 years",
            "mandate": "Build a source-backed long-term investment decision brief for MSTC.",
        }, run_rows=rows, run_statement=statement, sql_literal=literal, sql_jsonb=jsonb)

        self.assertEqual(result["status"], "proposed")
        self.assertEqual(result["research_case"]["ticker"], "MSTCLTD")
        self.assertIn("'confirmed',28", statements[0])

    def test_zero_match_explains_exact_remediation(self):
        result = propose_research_case({"request_text": "Start research on UNKNOWNCO"},
            run_rows=lambda sql: [], run_statement=lambda sql: [],
            sql_literal=literal, sql_jsonb=jsonb)
        self.assertEqual(result["status"], "needs_input")
        self.assertIn("exact exchange ticker", result["detail"])
        self.assertIn("No case or agent work was created", result["detail"])

    def test_natural_language_scope_after_company_resolves_longest_verified_prefix(self):
        seen_sql = []

        def rows(sql):
            seen_sql.append(sql)
            if "FROM research.companies company" in sql:
                if "Indian Energy Exchange for" in sql:
                    return []
                if "'Indian Energy Exchange'" in sql:
                    return [{
                        "company_id": 18, "company_key": "nse:iex",
                        "legal_name": "Indian Energy Exchange Limited",
                        "display_name": "Indian Energy Exchange Limited",
                        "ticker": "IEX", "exchange": "NSE", "holding_thesis_id": None,
                        "identity_verified": True, "identity_source": "verified_company_registry",
                    }]
            return []

        result = propose_research_case({
            "request_text": (
                "Start long-term research on Indian Energy Exchange for a 5 to 10 year "
                "moat, financial quality, reverse DCF and risk decision"
            ),
        }, run_rows=rows,
            run_statement=lambda sql: [{"id": 904, "ticker": "IEX", "status": "proposed"}],
            sql_literal=literal, sql_jsonb=jsonb)

        self.assertEqual(result["status"], "proposed")
        self.assertEqual(result["research_case"]["ticker"], "IEX")
        self.assertTrue(any("'Indian Energy Exchange'" in sql for sql in seen_sql))


    def test_natural_language_launch_commands_are_bounded_and_normalized(self):
        examples = {
            "Start long-term research on Infosys": "Infosys",
            "Please begin fundamental company research for 'INFY'.": "INFY",
            "Could you launch a new public-company research case about Infosys?": "Infosys",
            "Do equity research into NSE:INFY": "NSE:INFY",
        }
        for command, expected in examples.items():
            with self.subTest(command=command):
                self.assertEqual(extract_research_entity(command), expected)
        self.assertEqual(extract_research_entity("Shivalik Bimetal too latest filings n news n more"), "Shivalik Bimetal")
        self.assertIsNone(extract_research_entity("What research do we have on Infosys?"))
        self.assertIsNone(extract_research_entity("Summarize Infosys"))
        self.assertIsNone(extract_research_entity("Infosys also looks interesting"))

    def test_nested_client_command_is_unwrapped_before_entity_resolution(self):
        seen_sql = []

        def rows(sql):
            seen_sql.append(sql)
            if "FROM research.companies company" in sql:
                return [{
                    "company_id": 18, "company_key": "nse:infy",
                    "legal_name": "Infosys Limited", "display_name": "Infosys",
                    "ticker": "INFY", "exchange": "NSE", "holding_thesis_id": None,
                }]
            return []

        result = propose_research_case({
            "request_text": "Start research on Start long-term research on Infosys",
            "entity": "Start long-term research on Infosys",
        }, run_rows=rows,
            run_statement=lambda sql: [{"id": 902, "ticker": "INFY", "status": "proposed"}],
            sql_literal=literal, sql_jsonb=jsonb)

        self.assertEqual(result["status"], "proposed")
        self.assertIn("'Infosys'", seen_sql[0])
        self.assertNotIn("Start long-term research on Infosys", seen_sql[0])

    def test_blocked_case_does_not_prevent_confirmed_distinct_mandate(self):
        statements = []

        def rows(sql):
            if "FROM research.companies company" in sql:
                return [{
                    "company_id": 18, "company_key": "nse:infy",
                    "legal_name": "Infosys Limited", "display_name": "Infosys",
                    "ticker": "INFY", "exchange": "NSE", "holding_thesis_id": None,
                }]
            if "idempotency_key" in sql:
                return []
            if "FROM research.research_cases" in sql:
                return [{"id": 44, "company_id": 18, "ticker": "INFY", "status": "blocked"}]
            return []

        result = propose_research_case({
            "request_text": "Start long-term research on Infosys",
            "mandate": "Assess the five-year capital-allocation record.",
            "create_distinct_confirmed": True,
        }, run_rows=rows,
            run_statement=lambda sql: statements.append(sql) or [{"id": 903, "ticker": "INFY", "status": "proposed"}],
            sql_literal=literal, sql_jsonb=jsonb)

        self.assertEqual(result["status"], "proposed")
        self.assertTrue(statements)

    def test_blocked_case_returns_actionable_choices_without_duplicate(self):
        def rows(sql):
            if "FROM research.companies company" in sql:
                return [{
                    "company_id": 18, "company_key": "nse:infy",
                    "legal_name": "Infosys Limited", "display_name": "Infosys",
                    "ticker": "INFY", "exchange": "NSE", "holding_thesis_id": None,
                }]
            if "idempotency_key" in sql:
                return [{"id": 44, "company_id": 18, "ticker": "INFY", "status": "blocked"}]
            return []

        result = propose_research_case({"request_text": "Start long-term research on Infosys"},
            run_rows=rows, run_statement=lambda sql: self.fail("duplicate case must not be inserted"),
            sql_literal=literal, sql_jsonb=jsonb)
        self.assertEqual(result["status"], "blocked_conflict")
        self.assertEqual(result["action_choices"], ["view_or_repair_existing", "create_distinct_mandate"])

    def test_zero_source_preflight_creates_workstream_without_model_dispatch(self):
        statements = []
        graph_calls = []

        def rows(sql):
            if "FROM research.model_run_preflights" in sql:
                return [{
                    "id": 80, "status": "approved", "public_only": True,
                    "private_data_egress_allowed": False, "external_write_allowed": False,
                    "broker_write_allowed": False, "approval_status": "approved",
                    "source_count": 0, "document_count": 0,
                }]
            if "SELECT * FROM research.research_cases" in sql:
                return [{
                    "id": 110, "status": "proposed", "resolution_status": "confirmed",
                    "case_key": "research-test", "company_id": 55, "ticker": "TEST",
                    "exchange": "NSE", "company_name": "Test Limited", "source_plan": [],
                    "budget": {}, "data_boundary": {},
                }]
            return []

        result = start_research_case(
            {"research_case_id": 110, "model_preflight_id": 80, "operator_confirmed": True},
            run_rows=rows,
            run_statement=lambda sql: statements.append(sql) or [{"id": 110, "status": "collecting"}],
            sql_literal=literal,
            sql_jsonb=jsonb,
            start_graph=lambda payload: graph_calls.append(payload) or {"graph_run_id": 230},
        )

        self.assertEqual(result["status"], "collecting")
        self.assertFalse(result["model_dispatch_allowed"])
        self.assertEqual(result["source_count"], 0)
        self.assertEqual(result["model_gate"], "waiting_for_qualified_public_sources")
        self.assertEqual(len(graph_calls), 1)
        self.assertIn("awaiting_sources", statements[0])
        self.assertIn("paid model roles are waiting for qualified public evidence", statements[0])

if __name__ == "__main__":
    unittest.main()
