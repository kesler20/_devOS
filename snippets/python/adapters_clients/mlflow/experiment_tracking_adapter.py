from __future__ import annotations

import json
import pickle
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Literal, Protocol


ModelType = Literal[
    "sklearn",
    "xgboost",
    "lightgbm",
    "catboost",
    "pyfunc",
    "pytorch",
    "spark",
    "fastai",
    "statsmodels",
    "onnx",
    "spacy",
    "pmdarima",
    "tensorflow",
    "keras",
    "h2o",
    "prophet",
]

ArtifactType = Literal["notes", "dataframe", "dict", "figure", "other"]


class PredictiveModel(Protocol):
    """Protocol for models that can produce predictions."""

    def predict(self, model_input: Any) -> Any:
        """Predict from a model input."""

        ...


@dataclass
class MLflowArtifact:
    """Artifact logged with a run.

    Parameters
    ----------
    type
        Artifact type, for example ``"dataframe"`` or ``"dict"``.
    filename
        Artifact filename. Missing common extensions are inferred.
    value
        Artifact value or file path.
    file_path
        Optional MLflow artifact subfolder.
    """

    type: ArtifactType
    filename: str
    value: Any
    file_path: str | Path | None = None


@dataclass
class MLflowRun:
    """One experiment-tracking run.

    Parameters
    ----------
    run_name
        Human-readable run name.
    model_type
        MLflow flavor name.
    evaluate_inputs
        Keyword arguments passed to ``evaluate`` and logged as params.
    evaluate
        Callable returning ``(metrics, model)``.
    input_example
        Example input used for model signatures and input artifacts.
    artifacts
        Optional run artifacts.
    tags
        Optional MLflow tags.
    """

    run_name: str
    model_type: ModelType
    evaluate_inputs: dict[str, Any]
    evaluate: Callable[..., tuple[dict[str, Any] | None, PredictiveModel]]
    input_example: Any
    artifacts: list[MLflowArtifact] | None = None
    tags: dict[str, str] | None = None


@dataclass(frozen=True)
class MLflowRunEvaluation:
    """Result from an MLflow run.

    Parameters
    ----------
    run_id
        MLflow run ID.
    run_name
        Run name.
    metrics
        Metrics returned by the run evaluation.
    """

    run_id: str
    run_name: str
    metrics: dict[str, Any] | None


class MLflowAdapter:
    """Track model experiments in MLflow.

    This is a reusable extraction of the modelOps ``ExperimentTracking``
    pattern. It keeps modelops-style run and artifact dataclasses local to the
    snippet so generated projects can copy it without importing modelops.

    Parameters
    ----------
    tracking_uri
        Optional MLflow tracking URI.
    artifact_location
        Optional default artifact location for new experiments.
    mlflow_client
        Optional imported MLflow module or test fake.
    model_registry
        Optional object with ``register_model`` and
        ``set_model_as_challenger``.
    progress
        Optional iterator wrapper such as ``tqdm.tqdm``.
    signature_factory
        Optional function compatible with ``mlflow.models.infer_signature``.
    """

    def __init__(
        self,
        tracking_uri: str | None = None,
        artifact_location: str | Path | None = None,
        mlflow_client: Any | None = None,
        model_registry: Any | None = None,
        progress: Callable[[list[MLflowRun]], Any] | None = None,
        signature_factory: Callable[[Any, Any], Any] | None = None,
    ) -> None:
        self.__mlflow = mlflow_client or self.__load_mlflow()
        self.__model_registry = model_registry
        self.__progress = progress or (lambda runs: runs)
        self.__signature_factory = signature_factory
        self.tracking_uri = tracking_uri
        self.artifact_location = (
            Path(artifact_location).as_uri() if artifact_location is not None else None
        )
        self.experiment_id: str | None = None
        if self.tracking_uri is not None:
            self.__mlflow.set_tracking_uri(self.tracking_uri)

    def start_experiment(self, experiment_name: str) -> None:
        """Create or select an MLflow experiment.

        Parameters
        ----------
        experiment_name
            MLflow experiment name.
        """

        experiment = self.__mlflow.get_experiment_by_name(experiment_name)
        if experiment is None:
            self.experiment_id = self.__mlflow.create_experiment(
                experiment_name,
                artifact_location=self.artifact_location,
            )
        else:
            self.experiment_id = experiment.experiment_id
        self.__mlflow.set_experiment(experiment_id=self.experiment_id)

    def execute_run(self, run: MLflowRun) -> MLflowRunEvaluation:
        """Evaluate and log one MLflow run.

        Parameters
        ----------
        run
            Run specification.

        Returns
        -------
        MLflowRunEvaluation
            Logged run metadata.
        """

        self.__mlflow.autolog(log_input_examples=True)
        with self.__mlflow.start_run(
            run_name=run.run_name,
            experiment_id=self.experiment_id,
        ) as mlflow_run:
            metrics, model = run.evaluate(**run.evaluate_inputs)
            artifacts = list(run.artifacts or [])
            artifacts.append(
                MLflowArtifact(
                    type="dataframe",
                    filename="input_example.csv",
                    value=run.input_example,
                )
            )

            self.__mlflow.log_params(run.evaluate_inputs)
            if run.tags is not None:
                self.__mlflow.set_tags(run.tags)

            output_example = self.__predict_output_example(model, run.input_example)
            if output_example is not None:
                artifacts.append(
                    MLflowArtifact(
                        type="dataframe",
                        filename="output_example.csv",
                        value=output_example,
                    )
                )

            if metrics is not None:
                for key, value in metrics.items():
                    self.__log_metric(key, value)

            self.__log_artifacts(artifacts)
            self.__log_model(
                input_example=run.input_example,
                output_example=output_example,
                model_params=run.evaluate_inputs,
                model=model,
                model_type=run.model_type,
            )

            return MLflowRunEvaluation(
                run_id=mlflow_run.info.run_id,
                run_name=run.run_name,
                metrics=metrics,
            )

    def evaluate_experiments(
        self,
        experiment_name: str,
        runs: list[MLflowRun],
        objective: Callable[[dict[str, Any]], float] | None = None,
        save_best_model: bool = False,
        challenge_champion: bool = False,
    ) -> list[MLflowRunEvaluation]:
        """Evaluate a set of runs in one MLflow experiment.

        Parameters
        ----------
        experiment_name
            MLflow experiment name.
        runs
            Run specifications.
        objective
            Optional scoring function used to select the best run.
        save_best_model
            Whether to register the best run in ``model_registry``.
        challenge_champion
            Whether to mark the registered best run as challenger.

        Returns
        -------
        list[MLflowRunEvaluation]
            Logged run results.
        """

        self.start_experiment(experiment_name)
        results: list[MLflowRunEvaluation] = []
        best_result: MLflowRunEvaluation | None = None
        best_score: float | None = None

        for run in self.__progress(runs):
            result = self.execute_run(run)
            results.append(result)
            if objective is None or result.metrics is None:
                continue
            score = objective(result.metrics)
            if best_score is None or score > best_score:
                best_result = result
                best_score = score

        if save_best_model and best_result is not None:
            if self.__model_registry is None:
                raise ValueError("model_registry is required to save the best model.")
            self.__model_registry.register_model(
                best_result.run_id, best_result.run_name
            )
            if challenge_champion:
                self.__model_registry.set_model_as_challenger(best_result.run_name)

        return results

    def log_artifacts(self, artifacts: list[MLflowArtifact]) -> None:
        """Log artifacts with the current active MLflow run.

        Parameters
        ----------
        artifacts
            Artifacts to log.
        """

        self.__log_artifacts(artifacts)

    def __load_mlflow(self) -> Any:
        import mlflow

        return mlflow

    def __log_metric(self, key: str, value: Any) -> None:
        try:
            self.__mlflow.log_metric(key, value)
        except Exception:
            pass

    def __predict_output_example(
        self, model: PredictiveModel, input_example: Any
    ) -> Any | None:
        try:
            return model.predict(input_example)
        except Exception:
            return None

    def __log_artifacts(self, artifacts: list[MLflowArtifact]) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory_name:
            temporary_directory = Path(temporary_directory_name)
            for artifact in artifacts:
                artifact_filename = self.__filename_with_default_suffix(artifact)
                artifact_path = self.__artifact_path(artifact.file_path)
                artifact_file = (
                    artifact_filename
                    if artifact_path is None
                    else f"{artifact_path}/{artifact_filename}"
                )
                suffix = Path(artifact_filename).suffix.lower()
                artifact_value = artifact.value

                if artifact.type == "figure":
                    if isinstance(artifact_value, (str, Path)):
                        self.__mlflow.log_artifact(
                            str(Path(artifact_value)),
                            artifact_path=artifact_path,
                        )
                    else:
                        self.__mlflow.log_figure(artifact_value, artifact_file)
                    continue

                if artifact.type == "notes":
                    self.__mlflow.log_text(str(artifact_value), artifact_file)
                    continue

                if artifact.type == "dict":
                    self.__log_dict_artifact(artifact_value, artifact_file, suffix)
                    continue

                if artifact.type == "dataframe":
                    self.__log_dataframe_artifact(
                        artifact_value,
                        temporary_directory / artifact_filename,
                        artifact_path,
                        suffix,
                    )
                    continue

                self.__log_other_artifact(
                    artifact_value,
                    temporary_directory / artifact_filename,
                    artifact_path,
                    suffix,
                )

    def __filename_with_default_suffix(self, artifact: MLflowArtifact) -> str:
        if Path(artifact.filename).suffix:
            return artifact.filename
        if artifact.type == "dataframe":
            return f"{artifact.filename}.csv"
        if artifact.type == "dict":
            return f"{artifact.filename}.json"
        if artifact.type == "notes":
            return f"{artifact.filename}.txt"
        return artifact.filename

    def __artifact_path(self, file_path: str | Path | None) -> str | None:
        if file_path is None:
            return None
        return str(file_path).replace("\\", "/").strip("/")

    def __log_dict_artifact(
        self,
        artifact_value: Any,
        artifact_file: str,
        suffix: str,
    ) -> None:
        value = (
            artifact_value if isinstance(artifact_value, dict) else dict(artifact_value)
        )
        if suffix == ".json":
            self.__mlflow.log_dict(value, artifact_file)
            return
        if suffix in [".yaml", ".yml"]:
            try:
                import yaml

                content = yaml.safe_dump(value, sort_keys=False)
            except ImportError:
                content = json.dumps(value, default=str, indent=2)
            self.__mlflow.log_text(content, artifact_file)
            return
        raise ValueError(f"Unsupported dict artifact extension: {suffix or '<none>'}")

    def __log_dataframe_artifact(
        self,
        artifact_value: Any,
        local_path: Path,
        artifact_path: str | None,
        suffix: str,
    ) -> None:
        data_frame = self.__to_dataframe(artifact_value)
        if suffix == ".csv":
            data_frame.to_csv(local_path, index=False)
        elif suffix == ".json":
            data_frame.to_json(local_path, orient="records", indent=2)
        elif suffix == ".parquet":
            data_frame.to_parquet(local_path, index=False)
        elif suffix in [".xlsx", ".xls"]:
            data_frame.to_excel(local_path, index=False)
        else:
            raise ValueError(
                f"Unsupported dataframe artifact extension: {suffix or '<none>'}"
            )

        try:
            data_set = self.__mlflow.data.from_pandas(data_frame)
            self.__mlflow.log_input(data_set)
        except Exception:
            pass
        self.__mlflow.log_artifact(
            str(local_path),
            artifact_path=artifact_path or "data",
        )

    def __log_other_artifact(
        self,
        artifact_value: Any,
        local_path: Path,
        artifact_path: str | None,
        suffix: str,
    ) -> None:
        if isinstance(artifact_value, (str, Path)):
            path_value = Path(artifact_value)
            if path_value.exists() and path_value.is_file():
                self.__mlflow.log_artifact(
                    str(path_value),
                    artifact_path=artifact_path,
                )
            else:
                self.__mlflow.log_text(str(artifact_value), local_path.name)
            return

        if isinstance(artifact_value, bytes):
            local_path.write_bytes(artifact_value)
        elif isinstance(artifact_value, dict):
            local_path.write_text(
                json.dumps(artifact_value, default=str, indent=2),
                encoding="utf-8",
            )
        else:
            local_path.write_text(
                json.dumps(artifact_value, default=str, indent=2),
                encoding="utf-8",
            )
        self.__mlflow.log_artifact(str(local_path), artifact_path=artifact_path)

    def __to_dataframe(self, value: Any) -> Any:
        try:
            import numpy as np
            import pandas as pd
        except ImportError as error:
            raise ImportError("pandas is required for dataframe artifacts.") from error

        if isinstance(value, pd.DataFrame):
            return value
        if isinstance(value, pd.Series):
            return value.to_frame()
        if isinstance(value, np.ndarray):
            return pd.DataFrame(value)
        return pd.DataFrame(value)

    def __log_model(
        self,
        input_example: Any,
        output_example: Any,
        model_params: dict[str, Any],
        model: PredictiveModel,
        model_type: ModelType,
    ) -> None:
        if model_type == "pyfunc":
            self.__log_custom_model(input_example, output_example, model_params, model)
            return

        flavor = getattr(self.__mlflow, model_type)
        flavor.log_model(
            model,
            "model",
            input_example=input_example,
            signature=self.__infer_signature(input_example, output_example),
        )

    def __log_custom_model(
        self,
        input_example: Any,
        output_example: Any,
        model_params: dict[str, Any],
        model: PredictiveModel,
    ) -> None:
        for key, value in model_params.items():
            self.__mlflow.log_param(key, value)

        import mlflow.pyfunc as pyfunc
        from mlflow.pyfunc import PythonModel

        class CustomModelWrapper(PythonModel):
            def __init__(self, custom_model: PredictiveModel):
                self.custom_model = custom_model

            def predict(
                self,
                context: Any,
                model_input: Any,
                params: dict[str, Any] | None = None,
            ) -> Any:
                return self.custom_model.predict(model_input)

        pyfunc.log_model(
            artifact_path="model",
            python_model=CustomModelWrapper(model),
            input_example=input_example,
            signature=self.__infer_signature(input_example, output_example),
        )

        with tempfile.TemporaryDirectory() as temporary_directory_name:
            model_path = Path(temporary_directory_name) / "model.pkl"
            with model_path.open("wb") as model_file:
                pickle.dump(model, model_file)
            self.__mlflow.log_artifact(str(model_path), artifact_path="Model")

    def __infer_signature(self, input_example: Any, output_example: Any) -> Any:
        if self.__signature_factory is None:
            from mlflow.models import infer_signature

            self.__signature_factory = infer_signature
        return self.__signature_factory(input_example, output_example)
