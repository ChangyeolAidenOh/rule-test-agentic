"""Business rule test scenarios for evaluation."""

SCENARIOS = [
    {
        "scenario_id": "S1",
        "complexity": "simple",
        "raw_rule": (
            "갱신 시 65세 이상 보험료 15% 인상, "
            "5년 무사고 시 10%만"
        ),
        "description": "Renewal premium adjustment by age and claim history",
    },
    {
        "scenario_id": "S2",
        "complexity": "medium",
        "raw_rule": (
            "입원일당 가입 후 90일 이후 지급, "
            "1일 10만원, 연 180일 한도"
        ),
        "description": "Hospital daily benefit with waiting period and annual cap",
    },
    {
        "scenario_id": "S3",
        "complexity": "complex",
        "raw_rule": (
            "동일 질병 180일 내 재입원 시 1회 입원 간주, "
            "연간 한도 합산"
        ),
        "description": "Re-hospitalization consolidation rule within 180 days",
    },
    {
        "scenario_id": "S4",
        "complexity": "hard",
        "raw_rule": (
            "해약환급금 = 납입누계 - 위험보험료 - 사업비, "
            "해지공제 적용"
        ),
        "description": "Surrender value calculation with deductions",
    },
    {
        "scenario_id": "S5",
        "complexity": "hard",
        "raw_rule": (
            "3대 질병 진단비 지급. 90일 면책. "
            "갑상선/피부암은 소액암 20%"
        ),
        "description": "Critical illness diagnosis benefit with exclusion period and minor cancer clause",
    },
]


def get_scenario(scenario_id: str) -> dict:
    """Get a scenario by ID."""
    for s in SCENARIOS:
        if s["scenario_id"] == scenario_id:
            return s
    raise ValueError(f"Scenario not found: {scenario_id}")


def get_all_scenarios() -> list[dict]:
    """Get all scenarios."""
    return SCENARIOS
