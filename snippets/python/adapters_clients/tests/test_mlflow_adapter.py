from pathlib import Path

import pandas as pd

from adapters_clients.mlflow.experiment_tracking_adapter import (
    MLflowAdapter,
    MLflowArtifact,
    MLflowRun,
)


class FakeExperiment:
    experiment_id = "existing-experiment"


class FakeRunInfo:
    run_id = "run-1"


class FakeStartedRun:
    info = FakeRunInfo()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False


class FakeFlavor:
    def __init__(self):
        self.logged_models = []

    def log_model(self, *args, **kwargs):
        self.logged_models.append((args, kwargs))


class FakeDataApi:
    def __init__(self):
        self.inputs = []

    def from_pandas(self, data_frame):
        self.inputs.append(data_frame)
        return {"rows": len(data_frame)}


class FakeMLflow:
    def __init__(self):
        self.tracking_uri = None
        self.created = []
        self.set_experiments = []
        self.params = []
        self.metrics = []
        self.tags = []
        self.artifacts = []
        self.dicts = []
        self.texts = []
        self.figures = []
        self.inputs = []
        self.autolog_calls = []
        self.sklearn = FakeFlavor()
        self.data = FakeDataApi()

    def set_tracking_uri(self, tracking_uri):
        self.tracking_uri = tracking_uri

    def get_experiment_by_name(self, experiment_name):
        return None

    def create_experiment(self, experiment_name, artifact_location=None):
        self.created.append((experiment_name, artifact_location))
        return "experiment-1"

    def set_experiment(self, experiment_id):
        self.set_experiments.append(experiment_id)

    def autolog(self, **kwargs):
        self.autolog_calls.append(kwargs)

    def start_run(self, run_name, experiment_id):
        self.started_run = (run_name, experiment_id)
        return FakeStartedRun()

    def log_params(self, params):
        self.params.append(params)

    def set_tags(self, tags):
        self.tags.append(tags)

    def log_metric(self, key, value):
        self.metrics.append((key, value))

    def log_artifact(self, path, artifact_path=None):
        self.artifacts.append((Path(path).name, artifact_path))

    def log_dict(self, value, artifact_file):
        self.dicts.append((value, artifact_file))

    def log_text(self, value, artifact_file):
        self.texts.append((value, artifact_file))

    def log_figure(self, value, artifact_file):
        self.figures.append((value, artifact_file))

    def log_input(self, data_set):
        self.inputs.append(data_set)


class FakeModel:
    def predict(self, model_input):
        return pd.DataFrame({"prediction": [42]})


def test_start_experiment_creates_missing_experiment(tmp_path) -> None:
    fake_mlflow = FakeMLflow()
    adapter = MLflowAdapter(
        tracking_uri="file:///tmp/mlruns",
        artifact_location=tmp_path,
        mlflow_client=fake_mlflow,
    )

    adapter.start_experiment("demo")

    assert fake_mlflow.tracking_uri == "file:///tmp/mlruns"
    assert fake_mlflow.created == [("demo", tmp_path.as_uri())]
    assert fake_mlflow.set_experiments == ["experiment-1"]


def test_log_artifacts_supports_common_formats() -> None:
    fake_mlflow = FakeMLflow()
    adapter = MLflowAdapter(
        mlflow_client=fake_mlflow,
        signature_factory=lambda input_example, output_example: "signature",
    )

    adapter.log_artifacts(
        [
            MLflowArtifact(
                type="dict",
                filename="summary.json",
                value={"rmse": 0.1},
                file_path="reports",
            ),
            MLflowArtifact(type="notes", filename="notes", value="hello"),
            MLflowArtifact(
                type="dataframe",
                filename="predictions.csv",
                value=pd.DataFrame({"y": [1]}),
                file_path="tables",
            ),
            MLflowArtifact(
                type="other",
                filename="raw.bin",
                value=b"bytes",
                file_path="raw",
            ),
        ]
    )

    assert fake_mlflow.dicts == [({"rmse": 0.1}, "reports/summary.json")]
    assert fake_mlflow.texts == [("hello", "notes.txt")]
    assert ("predictions.csv", "tables") in fake_mlflow.artifacts
    assert ("raw.bin", "raw") in fake_mlflow.artifacts
    assert fake_mlflow.inputs == [{"rows": 1}]


def test_execute_run_logs_metrics_tags_artifacts_and_model() -> None:
    fake_mlflow = FakeMLflow()
    adapter = MLflowAdapter(
        mlflow_client=fake_mlflow,
        signature_factory=lambda input_example, output_example: "signature",
    )
    adapter.experiment_id = "experiment-1"

    def evaluate(alpha):
        return {"rmse": 0.2}, FakeModel()

    result = adapter.execute_run(
        MLflowRun(
            run_name="alpha-run",
            model_type="sklearn",
            evaluate_inputs={"alpha": 0.1},
            evaluate=evaluate,
            input_example=pd.DataFrame({"x": [1]}),
            tags={"stage": "test"},
        )
    )

    assert result.run_id == "run-1"
    assert fake_mlflow.autolog_calls == [{"log_input_examples": True}]
    assert fake_mlflow.params == [{"alpha": 0.1}]
    assert fake_mlflow.tags == [{"stage": "test"}]
    assert fake_mlflow.metrics == [("rmse", 0.2)]
    assert fake_mlflow.sklearn.logged_models


class FakeRegistry:
    def __init__(self):
        self.registered = []
        self.challengers = []

    def register_model(self, run_id, run_name):
        self.registered.append((run_id, run_name))

    def set_model_as_challenger(self, run_name):
        self.challengers.append(run_name)


def test_evaluate_experiments_registers_best_run() -> None:
    fake_mlflow = FakeMLflow()
    registry = FakeRegistry()
    adapter = MLflowAdapter(
        mlflow_client=fake_mlflow,
        model_registry=registry,
        signature_factory=lambda input_example, output_example: "signature",
    )

    def evaluate(score):
        return {"score": score}, FakeModel()

    runs = [
        MLflowRun(
            run_name="low",
            model_type="sklearn",
            evaluate_inputs={"score": 0.1},
            evaluate=evaluate,
            input_example=pd.DataFrame({"x": [1]}),
        ),
        MLflowRun(
            run_name="high",
            model_type="sklearn",
            evaluate_inputs={"score": 0.9},
            evaluate=evaluate,
            input_example=pd.DataFrame({"x": [1]}),
        ),
    ]

    adapter.evaluate_experiments(
        "demo",
        runs,
        objective=lambda metrics: float(metrics["score"]),
        save_best_model=True,
        challenge_champion=True,
    )

    assert registry.registered == [("run-1", "high")]
    assert registry.challengers == ["high"]
