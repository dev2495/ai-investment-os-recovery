BEGIN;
INSERT INTO research.financial_formula_definitions(formula_key,version,label,expression,basis,unit,created_by) VALUES
('ebit_margin_pre_exception',1,'EBIT margin before exceptional items','(PBT before exceptional + finance cost - share of JV profit) / revenue * 100','{"scope":"consolidated","period":"annual","classification":"machine_calculated","ebit_definition":"PBT before exceptional + finance cost - share of JV profit"}'::jsonb,'percent','Codex governed capital-efficiency v1'),
('financing_capital_turnover',1,'Financing capital turnover','revenue / average(equity + current borrowings + non-current borrowings - cash)','{"scope":"consolidated","period":"annual","capital_basis":"average opening and closing financing capital"}'::jsonb,'multiple','Codex governed capital-efficiency v1'),
('roce_financing_capital',1,'ROCE — financing capital basis','EBIT before exceptional / average(equity + current borrowings + non-current borrowings - cash) * 100','{"scope":"consolidated","period":"annual","capital_basis":"average opening and closing financing capital","issuer_reported":false}'::jsonb,'percent','Codex governed capital-efficiency v1'),
('roic_financing_capital',1,'ROIC — financing capital basis','EBIT before exceptional * (1 - reported effective tax rate) / average financing capital * 100','{"scope":"consolidated","period":"annual","capital_basis":"average opening and closing financing capital","tax_method":"continuing tax expense / continuing PBT","issuer_reported":false}'::jsonb,'percent','Codex governed capital-efficiency v1')
ON CONFLICT(formula_key,version) DO NOTHING;
WITH vals(formula_key,value,caveats) AS (VALUES
('ebit_margin_pre_exception',17.81493663066978,'["Machine-calculated from FY2026 consolidated annual-report inputs; not human-reviewed."]'::jsonb),
('financing_capital_turnover',1.2233537111825175,'["Average FY2025/FY2026 financing capital; not comparable to operating invested-capital definitions."]'::jsonb),
('roce_financing_capital',21.793968841611246,'["Calculated, not issuer-reported ROCE; financing-capital basis; not human-reviewed."]'::jsonb),
('roic_financing_capital',16.738117008301582,'["NOPAT applies the reported continuing effective tax rate to EBIT; financing-capital basis; not human-reviewed."]'::jsonb)
), ins AS (
INSERT INTO research.financial_ratio_results(production_run_id,company_id,formula_definition_id,period_end,statement_scope,value,calculation_status,caveats)
SELECT 1,43,fd.id,'2026-03-31','consolidated',vals.value,'machine_calculated',vals.caveats FROM vals JOIN research.financial_formula_definitions fd ON fd.formula_key=vals.formula_key AND fd.version=1
ON CONFLICT(production_run_id,formula_definition_id,period_end,statement_scope) DO UPDATE SET value=excluded.value,calculation_status=excluded.calculation_status,caveats=excluded.caveats RETURNING id,formula_definition_id)
INSERT INTO research.financial_ratio_inputs(ratio_result_id,input_role,fact_id)
SELECT rr.id,roles.input_role,sf.id FROM research.financial_ratio_results rr JOIN research.financial_formula_definitions fd ON fd.id=rr.formula_definition_id
JOIN LATERAL (VALUES
('current_revenue','2026-03-31'::date,'revenue'),('current_pbt_before_exceptional','2026-03-31','pbt_before_exceptional'),('current_finance_cost','2026-03-31','finance_cost'),('current_share_of_jv_profit','2026-03-31','share_of_jv_profit'),('current_total_equity','2026-03-31','total_equity'),('current_current_borrowings','2026-03-31','current_borrowings'),('current_non_current_borrowings','2026-03-31','non_current_borrowings'),('current_cash','2026-03-31','cash'),('prior_total_equity','2025-03-31','total_equity'),('prior_current_borrowings','2025-03-31','current_borrowings'),('prior_non_current_borrowings','2025-03-31','non_current_borrowings'),('prior_cash','2025-03-31','cash'),('current_tax_expense','2026-03-31','tax_expense'),('current_pbt_continuing','2026-03-31','pbt_continuing')) roles(input_role,period_end,fact_key) ON true
JOIN research.financial_source_facts sf ON sf.production_run_id=1 AND sf.period_end=roles.period_end AND sf.fact_key=roles.fact_key
WHERE rr.production_run_id=1 AND rr.period_end='2026-03-31' AND fd.formula_key IN ('ebit_margin_pre_exception','financing_capital_turnover','roce_financing_capital','roic_financing_capital')
ON CONFLICT DO NOTHING;
INSERT INTO research.financial_ratio_inputs(ratio_result_id,input_role,fact_id)
SELECT rr.id,roles.input_role,sf.id
FROM research.financial_ratio_results rr
JOIN research.financial_formula_definitions fd ON fd.id=rr.formula_definition_id
CROSS JOIN (VALUES
('current_revenue','2026-03-31'::date,'revenue'),('current_pbt_before_exceptional','2026-03-31','pbt_before_exceptional'),('current_finance_cost','2026-03-31','finance_cost'),('current_share_of_jv_profit','2026-03-31','share_of_jv_profit'),('current_total_equity','2026-03-31','total_equity'),('current_current_borrowings','2026-03-31','current_borrowings'),('current_non_current_borrowings','2026-03-31','non_current_borrowings'),('current_cash','2026-03-31','cash'),('prior_total_equity','2025-03-31','total_equity'),('prior_current_borrowings','2025-03-31','current_borrowings'),('prior_non_current_borrowings','2025-03-31','non_current_borrowings'),('prior_cash','2025-03-31','cash'),('current_tax_expense','2026-03-31','tax_expense'),('current_pbt_continuing','2026-03-31','pbt_continuing')) roles(input_role,period_end,fact_key)
JOIN research.financial_source_facts sf ON sf.production_run_id=1 AND sf.period_end=roles.period_end AND sf.fact_key=roles.fact_key
WHERE rr.production_run_id=1 AND rr.period_end='2026-03-31' AND fd.formula_key IN ('ebit_margin_pre_exception','financing_capital_turnover','roce_financing_capital','roic_financing_capital')
ON CONFLICT DO NOTHING;

COMMIT;
