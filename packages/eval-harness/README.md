# Awaaz eval harness

LLM-as-customer simulator that drives every SPEC §4 scenario against the FSM
and asserts the final outcome. Used by the nightly `eval-suite.yml` GH Action
and locally via:

```bash
cd apps/api
python -m awaaz_api.scripts.run_eval_suite
```

Golden conversations live in `apps/api/awaaz_api/tests/fixtures/golden/`.
