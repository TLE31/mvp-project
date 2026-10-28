from changeguard.risk import ENDPOINT_POINTS, WEIGHTS, score_risk


def test_risk_score_has_weighted_factor_breakdown():
    risk = score_risk(
        {
            "impacted_endpoints": ["GET /a", "GET /b", "GET /c"],
            "max_call_depth": 5,
            "max_fan_in": 5,
            "impacted_configs": ["feature.enabled"],
            "untested_changes": ["A.run()"],
        },
        ["src/main/java/ARepository.java"],
    )

    assert risk["score"] == 100
    assert risk["level"] == "HIGH"
    assert sum(item["weight"] for item in risk["breakdown"].values()) == 100
    assert set(risk["breakdown"]) == set(WEIGHTS)
    assert ENDPOINT_POINTS > 0


def test_low_risk_empty_change():
    assert score_risk({})["level"] == "LOW"
