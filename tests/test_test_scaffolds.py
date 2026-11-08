import pathlib
import subprocess
import sys

import pytest

from devOS import resource_cli
from devOS.use_cases import generate_test_scaffolds


def test_custom_scaffolds_are_owned_and_collect_without_importing_services(tmp_path):
    endpoint = tmp_path / "routes.py"
    endpoint.write_text("@router.post('/things/{key}')\nasync def create_thing(key: str, request: Request, service=Depends(get_service)):\n    pass\n")
    use_case = tmp_path / "use_case.py"
    use_case.write_text("class CalculateUseCase:\n    def __init__(self, adapter):\n        self.adapter = adapter\n    def execute(self, request):\n        return self.adapter.calculate(request)\n")
    tests = tmp_path / "tests"
    tests.mkdir()
    for kind, source in {"api": endpoint, "services": use_case}.items():
        output = tests / f"test_{kind}.py"
        arguments = ["tests", kind, str(source), "--module", "missing.live_service", "--output", str(output)]
        assert resource_cli.main(arguments) == 0
        before = output.read_bytes()
        assert resource_cli.main(arguments) == 1
        assert output.read_bytes() == before
    result = subprocess.run([sys.executable, "-m", "pytest", str(tests), "-q", "--no-cov"], cwd=tmp_path, capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "2 skipped" in result.stdout and "passed" not in result.stdout
    assert "mock.Mock(name='adapter')" in (tests / "test_services.py").read_text()
    assert "use_case.execute(request=request)" in (tests / "test_services.py").read_text()


@pytest.mark.parametrize("source,kind,diagnostic", [
    ("@router.get(dynamic_path)\ndef read(): pass", "api", "static route path"),
    ("class Feature:\n    def execute(self, *args): pass", "services", "variadic"),
    ("class Feature: pass", "services", "No use-case"),
    ("def function(): pass", "api", "No decorated"),
])
def test_unsupported_source_patterns_report_diagnostics(source, kind, diagnostic):
    with pytest.raises(ValueError, match=diagnostic):
        generate_test_scaffolds.GenerateTestScaffoldsUseCase().execute(source, "consumer.feature", kind)
