from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable


@dataclass(frozen=True)
class WorkflowDeploymentSpec:
    """Workflow deployment request.

    Parameters
    ----------
    flow
        Flow object or callable to deploy.
    name
        Deployment name.
    work_pool_name
        Target work pool.
    parameters
        Default deployment parameters.
    """

    flow: Any
    name: str
    work_pool_name: str
    parameters: dict[str, Any]


class PrefectWorkflowEngineAdapter:
    """Deploy and run workflows through Prefect-style callables.

    Parameters
    ----------
    deployment_runner
        Callable used to trigger a deployment by name.
    """

    def __init__(self, deployment_runner: Callable[..., Any] | None = None) -> None:
        self.__deployment_runner = deployment_runner

    def deploy(self, spec: WorkflowDeploymentSpec) -> Any:
        """Deploy a flow.

        Parameters
        ----------
        spec
            Deployment specification.

        Returns
        -------
        Any
            Deployment result returned by the flow.
        """

        return spec.flow.deploy(
            name=spec.name,
            work_pool_name=spec.work_pool_name,
            parameters=spec.parameters,
        )

    def run_deployment(self, deployment_name: str, **parameters: Any) -> Any:
        """Run a deployed workflow.

        Parameters
        ----------
        deployment_name
            Deployment name or path.
        **parameters
            Runtime parameters.

        Returns
        -------
        Any
            Runner result.
        """

        if self.__deployment_runner is None:
            from prefect.deployments import run_deployment

            self.__deployment_runner = run_deployment
        return self.__deployment_runner(deployment_name, parameters=parameters)


@dataclass(frozen=True)
class PrefectGitHubDeploymentSpec:
    """Prefect deployment request backed by a GitHub source.

    Parameters
    ----------
    workflow
        Prefect flow object.
    repository_url
        GitHub repository URL.
    flow_entrypoint
        Flow entrypoint, for example ``"src/app/flows.py:run"``.
    deployment_name
        Prefect deployment name.
    work_pool_name
        Target work pool.
    docker_image_name
        Docker image name.
    docker_image_tag
        Docker image tag.
    dockerfile
        Dockerfile path.
    parameters
        Default deployment parameters.
    job_variables
        Optional Prefect job variables.
    """

    workflow: Any
    repository_url: str
    flow_entrypoint: str
    deployment_name: str
    work_pool_name: str
    docker_image_name: str
    docker_image_tag: str = "latest"
    dockerfile: str = "Dockerfile"
    parameters: dict[str, Any] | None = None
    job_variables: dict[str, Any] | None = None


class PrefectWorkflowOrchestrationAdapter:
    """Create, run, and deploy Prefect tasks and flows.

    Parameters
    ----------
    notification_adapter
        Optional adapter with ``send_task_error_notification`` and
        ``send_flow_error_notification`` methods.
    run_deployment
        Optional Prefect deployment runner.
    source_factory
        Optional factory for Prefect Git source objects.
    image_factory
        Optional factory for Prefect Docker image objects.
    """

    def __init__(
        self,
        notification_adapter: Any | None = None,
        run_deployment: Callable[..., Any] | None = None,
        source_factory: Callable[..., Any] | None = None,
        image_factory: Callable[..., Any] | None = None,
    ) -> None:
        self.__notification_adapter = notification_adapter
        self.__run_deployment = run_deployment
        self.__source_factory = source_factory
        self.__image_factory = image_factory

    def task(
        self,
        name: str,
        version: str = "v1",
        on_failure: list[Callable[..., Any]] | None = None,
        **kwargs: Any,
    ) -> Callable[[Callable[..., Any]], Any]:
        """Create a Prefect task decorator with notification callbacks.

        Parameters
        ----------
        name
            Task name.
        version
            Task version.
        on_failure
            Additional failure callbacks.
        **kwargs
            Extra keyword arguments passed to ``prefect.task``.

        Returns
        -------
        Callable[[Callable[..., Any]], Any]
            Prefect task decorator.
        """

        from prefect import task

        callbacks = list(on_failure or [])
        if self.__notification_adapter is not None:
            callbacks.append(self.__notification_adapter.send_task_error_notification)
        return task(name=name, version=version, on_failure=callbacks, **kwargs)

    def flow(
        self,
        name: str,
        version: str = "v1",
        on_failure: list[Callable[..., Any]] | None = None,
        **kwargs: Any,
    ) -> Callable[[Callable[..., Any]], Any]:
        """Create a Prefect flow decorator with notification callbacks.

        Parameters
        ----------
        name
            Flow name.
        version
            Flow version.
        on_failure
            Additional failure callbacks.
        **kwargs
            Extra keyword arguments passed to ``prefect.flow``.

        Returns
        -------
        Callable[[Callable[..., Any]], Any]
            Prefect flow decorator.
        """

        from prefect import flow

        callbacks = list(on_failure or [])
        if self.__notification_adapter is not None:
            callbacks.append(self.__notification_adapter.send_flow_error_notification)
        return flow(name=name, version=version, on_failure=callbacks, **kwargs)

    def run_deployment(self, deployment_name: str, **parameters: Any) -> Any:
        """Run a deployed Prefect flow.

        Parameters
        ----------
        deployment_name
            Deployment path.
        **parameters
            Runtime parameters.

        Returns
        -------
        Any
            Prefect runner result.
        """

        if self.__run_deployment is None:
            from prefect.deployments import run_deployment

            self.__run_deployment = run_deployment
        return self.__run_deployment(deployment_name, parameters=parameters)

    def deploy_from_github(self, spec: PrefectGitHubDeploymentSpec) -> Any:
        """Deploy a Prefect flow from a GitHub repository.

        Parameters
        ----------
        spec
            Deployment specification.

        Returns
        -------
        Any
            Prefect deploy result.
        """

        source_factory = self.__source_factory
        image_factory = self.__image_factory
        if source_factory is None:
            from prefect.runner.storage import GitRepository

            source_factory = GitRepository
        if image_factory is None:
            from prefect.deployments.runner import DockerImage

            image_factory = DockerImage

        source = source_factory(url=spec.repository_url)
        image = image_factory(
            name=spec.docker_image_name,
            tag=spec.docker_image_tag,
            dockerfile=spec.dockerfile,
        )
        deployment = spec.workflow.from_source(
            source=source,
            entrypoint=spec.flow_entrypoint,
        )
        return deployment.deploy(
            name=spec.deployment_name,
            work_pool_name=spec.work_pool_name,
            image=image,
            push=True,
            parameters=spec.parameters,
            job_variables=spec.job_variables,
        )


@dataclass(frozen=True)
class PrefectFailureNotification:
    """Normalized Prefect failure notification payload.

    Parameters
    ----------
    subject
        Notification subject.
    message
        Notification body.
    run_url
        Optional Prefect run URL.
    """

    subject: str
    message: str
    run_url: str | None = None


class PrefectNotificationAdapter:
    """Send notifications from Prefect failure callbacks.

    Parameters
    ----------
    email_adapter
        Adapter with ``send_email(subject, body, recipient)``.
    recipient
        Recipient email address.
    prefect_ui_url
        Optional Prefect UI base URL for run links.
    error_store
        Optional adapter with ``put(key, value)`` for failed notifications.
    clock
        Timestamp provider used for deterministic tests.
    """

    def __init__(
        self,
        email_adapter: Any,
        recipient: str,
        prefect_ui_url: str | None = None,
        error_store: Any | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.__email_adapter = email_adapter
        self.__recipient = recipient
        self.__prefect_ui_url = prefect_ui_url.rstrip("/") if prefect_ui_url else None
        self.__error_store = error_store
        self.__clock = clock or datetime.now

    def build_task_failure_notification(
        self, task: Any, task_run: Any, state: Any
    ) -> PrefectFailureNotification:
        """Build a task failure notification from Prefect callback objects.

        Parameters
        ----------
        task
            Prefect task object.
        task_run
            Prefect task run object.
        state
            Prefect state object.

        Returns
        -------
        PrefectFailureNotification
            Failure notification payload.
        """

        task_name = getattr(task, "name", "Task")
        state_name = getattr(state, "name", "Unknown")
        run_id = getattr(task_run, "id", None)
        run_url = (
            f"{self.__prefect_ui_url}/runs/task-run/{run_id}"
            if self.__prefect_ui_url and run_id
            else None
        )
        return PrefectFailureNotification(
            subject=f"Prefect task {task_name} entered {state_name}",
            message=self.__format_message(task_name, task_run, state, run_url),
            run_url=run_url,
        )

    def build_flow_failure_notification(
        self, flow: Any, flow_run: Any, state: Any
    ) -> PrefectFailureNotification:
        """Build a flow failure notification from Prefect callback objects.

        Parameters
        ----------
        flow
            Prefect flow object.
        flow_run
            Prefect flow run object.
        state
            Prefect state object.

        Returns
        -------
        PrefectFailureNotification
            Failure notification payload.
        """

        flow_name = getattr(flow, "name", "Flow")
        state_name = getattr(state, "name", "Unknown")
        run_id = getattr(flow_run, "id", None)
        run_url = (
            f"{self.__prefect_ui_url}/runs/flow-run/{run_id}"
            if self.__prefect_ui_url and run_id
            else None
        )
        return PrefectFailureNotification(
            subject=f"Prefect flow {flow_name} entered {state_name}",
            message=self.__format_message(flow_name, flow_run, state, run_url),
            run_url=run_url,
        )

    def send_task_error_notification(
        self, task: Any, task_run: Any, state: Any
    ) -> bool:
        """Send a task failure email from a Prefect callback.

        Parameters
        ----------
        task
            Prefect task object.
        task_run
            Prefect task run object.
        state
            Prefect state object.

        Returns
        -------
        bool
            True when the email adapter reports success.
        """

        return self.__send(self.build_task_failure_notification(task, task_run, state))

    def send_flow_error_notification(
        self, flow: Any, flow_run: Any, state: Any
    ) -> bool:
        """Send a flow failure email from a Prefect callback.

        Parameters
        ----------
        flow
            Prefect flow object.
        flow_run
            Prefect flow run object.
        state
            Prefect state object.

        Returns
        -------
        bool
            True when the email adapter reports success.
        """

        return self.__send(self.build_flow_failure_notification(flow, flow_run, state))

    def send_reauthentication_required_notification(self, service_name: str) -> bool:
        """Send a reauthentication-required notification.

        Parameters
        ----------
        service_name
            Service that needs new credentials.

        Returns
        -------
        bool
            True when the email adapter reports success.
        """

        notification = PrefectFailureNotification(
            subject=f"{service_name} needs reauthentication",
            message=f"{service_name} needs reauthentication before workflows resume.",
        )
        return self.__send(notification)

    def __format_message(
        self,
        name: str,
        run: Any,
        state: Any,
        run_url: str | None,
    ) -> str:
        lines = [
            f"Name: {name}",
            f"Run Name: {getattr(run, 'name', 'Unknown')}",
            f"State: {getattr(state, 'name', 'Unknown')}",
        ]
        if run_url:
            lines.append(f"Run URL: {run_url}")
        return "\n".join(lines)

    def __send(self, notification: PrefectFailureNotification) -> bool:
        try:
            return bool(
                self.__email_adapter.send_email(
                    subject=notification.subject,
                    body=notification.message,
                    recipient=self.__recipient,
                )
            )
        except Exception as error:
            if self.__error_store is not None:
                timestamp = round(self.__clock().timestamp() * 1_000)
                self.__error_store.put(
                    f"error_logs:email_notification_service:{timestamp}",
                    {"error": str(error)},
                )
            return False
