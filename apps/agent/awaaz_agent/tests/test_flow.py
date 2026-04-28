"""Voice flow — minimal sanity check that initial instructions render."""

from __future__ import annotations


def test_initial_instructions_have_required_pieces() -> None:
    from awaaz_agent.flow import build_initial_instructions

    class _Room:
        metadata = '{"brand_name":"Lawn Bazaar","customer_name":"Ali","order_number":"1001","total":5000,"address":"Main St"}'

    class _Job:
        room = _Room()

    instr = build_initial_instructions(_Job())
    assert "Lawn Bazaar" in instr
    assert "1001" in instr
    assert "5000" in instr
    assert "Ali" in instr
