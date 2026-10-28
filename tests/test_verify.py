from changeguard.verify import compare_tests


def test_comparison_identifies_unpredicted_failure():
    result = compare_tests(
        ["ServiceTest"],
        {
            "tests": [
                {"name": "ServiceTest", "result": "passed"},
                {"name": "ControllerTest", "result": "failed", "failures": 1},
            ]
        },
    )

    assert result["failed_unpredicted"] == ["ControllerTest"]
    assert result["predicted_count"] == 1
    assert result["actual_failed_count"] == 1
