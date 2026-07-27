from adapters_clients.workflow.prefect_adapters import (
    PrefectFailureNotification,
    PrefectGitHubDeploymentSpec,
    PrefectNotificationAdapter,
    PrefectWorkflowOrchestrationAdapter,
    PrefectWorkflowEngineAdapter,
    WorkflowDeploymentSpec,
)


class FakeFlow:
    def deploy(self, name, work_pool_name, parameters):
        return {
            "name": name,
            "work_pool_name": work_pool_name,
            "parameters": parameters,
        }


def test_deploy_calls_flow_deploy() -> None:
    adapter = PrefectWorkflowEngineAdapter()

    result = adapter.deploy(
        WorkflowDeploymentSpec(
            flow=FakeFlow(),
            name="nightly",
            work_pool_name="local",
            parameters={"limit": 10},
        )
    )

    assert result == {
        "name": "nightly",
        "work_pool_name": "local",
        "parameters": {"limit": 10},
    }


def test_run_deployment_uses_injected_runner() -> None:
    calls = []

    def runner(deployment_name, parameters):
        calls.append((deployment_name, parameters))
        return "started"

    adapter = PrefectWorkflowEngineAdapter(deployment_runner=runner)

    assert adapter.run_deployment("flow/nightly", limit=10) == "started"
    assert calls == [("flow/nightly", {"limit": 10})]


class FakeDeploymentSource:
    def __init__(self, source, entrypoint):
        self.source = source
        self.entrypoint = entrypoint

    def deploy(self, **kwargs):
        return {
            "source": self.source,
            "entrypoint": self.entrypoint,
            "deploy": kwargs,
        }


class FakeSourceFlow:
    def from_source(self, source, entrypoint):
        return FakeDeploymentSource(source, entrypoint)


def test_prefect_orchestration_deploy_from_github_uses_factories() -> None:
    adapter = PrefectWorkflowOrchestrationAdapter(
        source_factory=lambda **kwargs: {"source": kwargs},
        image_factory=lambda **kwargs: {"image": kwargs},
    )

    result = adapter.deploy_from_github(
        PrefectGitHubDeploymentSpec(
            workflow=FakeSourceFlow(),
            repository_url="https://github.com/example/repo.git",
            flow_entrypoint="src/flows.py:run",
            deployment_name="nightly",
            work_pool_name="default",
            docker_image_name="example/flow",
            parameters={"limit": 5},
        )
    )

    assert result["source"] == {
        "source": {"url": "https://github.com/example/repo.git"}
    }
    assert result["entrypoint"] == "src/flows.py:run"
    assert result["deploy"]["name"] == "nightly"
    assert result["deploy"]["image"] == {
        "image": {
            "name": "example/flow",
            "tag": "latest",
            "dockerfile": "Dockerfile",
        }
    }


class FakeEmailAdapter:
    def __init__(self):
        self.sent = []

    def send_email(self, subject, body, recipient):
        self.sent.append((subject, body, recipient))
        return True


class FakeObject:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


def test_prefect_notification_adapter_sends_task_failure_email() -> None:
    email_adapter = FakeEmailAdapter()
    adapter = PrefectNotificationAdapter(
        email_adapter=email_adapter,
        recipient="owner@example.com",
        prefect_ui_url="https://prefect.example.com",
    )

    assert (
        adapter.send_task_error_notification(
            FakeObject(name="Sync Task"),
            FakeObject(id="task-run-id", name="sync-run"),
            FakeObject(name="Failed"),
        )
        is True
    )
    assert email_adapter.sent == [
        (
            "Prefect task Sync Task entered Failed",
            "Name: Sync Task\nRun Name: sync-run\nState: Failed\nRun URL: https://prefect.example.com/runs/task-run/task-run-id",
            "owner@example.com",
        )
    ]


def test_prefect_notification_payload_dataclass() -> None:
    notification = PrefectFailureNotification(
        subject="subject",
        message="message",
        run_url="url",
    )

    assert notification.subject == "subject"
