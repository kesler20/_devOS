"""
The file api provides a better interface for editing files in python
"""
from datetime import timedelta, datetime
from pathlib import Path
import json
import os
import typing
import logging
import uuid
from prefect import Task, get_run_logger, Flow, get_client
from prefect.client.schemas.objects import TaskRun, State, TaskRunResult
from prefect.context import FlowRunContext
import asyncio
from modelOS_spec.clients.google_api.gmail_api import GmailApi
import modelOS_spec.infrastructure.schema as schema
import modelOS_spec.domain.entities as entities
import modelOS_spec.use_cases.ports as ports
import modelOS_spec.infrastructure.credentials.config as configs
import redis  # type: ignore
import redis.exceptions  # type: ignore
import json
import typing
import mlflow
import subprocess
import tempfile
import boto3
from botocore.client import Config as BotoConfig
import pandas as pd
import numpy as np
from sklearn.metrics import mean_squared_error, r2_score, mean_absolute_error
import paho.mqtt.client as mqtt  # Mosquitto/Paho client
import inspect


class RedisTimeSeriesAdapter:
    """Adapter for Redis Time Series data storage.

    The adapter uses the RedisTimeSeries module to store time series data in Redis.

    For more information on Redis Time Series, see: https://oss.redislabs.com/redistimeseries/

    Example
    -------
    ```python
    from datetime import timedelta
    from modelOS_spec.infrastructure.adapters import RedisTimeSeriesAdapter


    adapter = RedisTimeSeriesAdapter()
    adapter.add("temperature", 25.0)
    data = adapter.query("temperature", timedelta(days=1), "hours")
    ```
    """

    def __init__(self) -> None:
        self.client = redis.Redis(
            host=configs.RedisConfigsCreds.REDIS_HOST.value,
            port=int((configs.RedisConfigsCreds.REDIS_PORT.value or 6379)),
            password=configs.RedisConfigsCreds.REDIS_PASSWORD.value,
            decode_responses=True,
        )

    def __format_keys(self, keys: typing.Any):
        if isinstance(keys, str):
            keys = keys if keys.startswith("ts:") else f"ts:{keys}"
            return keys
        elif isinstance(keys, list):
            return [key if key.startswith("ts:") else f"ts:{key}" for key in keys]
        else:
            raise ValueError("Keys must be a string or a list of strings.")

    def add(
        self,
        key: str,
        value: float,
        timestamp: typing.Optional[int] = None,
    ):
        """
        Add a value to the time series with the current timestamp.

        Parameters
        ----------
        key : str
            The key for the time series.
        value : float
            The value to add (a float enables aggregation).
        timestamp: int (optional)
            The timestamp for the value in milliseconds.
        ttl: int (optional)
            Time to live for the time series in milliseconds.
        """
        key = self.__format_keys(key)
        now = (
            round(datetime.now().timestamp() * 1_000)
            if timestamp is None
            else timestamp
        )
        try:
            print("Adding", key, value, now)
            self.client.ts().add(key, now, value)
        except redis.exceptions.ResponseError as e:
            # If the time series doesn't exist, create it and retry
            if "ERR TSDB" in str(e):
                # TODO: if you have any issues: update the time to live by changing the retention_msecs parameter.
                print("Creating time series", key)
                self.create_time_series(key)

                self.client.ts().add(key, now, value)
                print("Adding", key, value, now)
            elif "DUPLICATE_POLICY is set to BLOCK mode" in str(e):
                # Handle the error caused by DUPLICATE_POLICY being set to BLOCK mode
                print("Duplicate policy error for key:", key)
                # Optionally, take further action here (e.g., log, retry, or skip)
            else:
                raise

    def create_time_series(self, key: str):
        """
        Create a new time series with the specified key.

        Parameters
        ----------
        key : str
            The key for the time series.
        """
        key = self.__format_keys(key)
        try:
            print("Creating time series", key)
            self.client.ts().create(key)
        except redis.exceptions.ResponseError as e:
            if "ERR TSDB" in str(e):
                print("Time series already exists", key)
            else:
                raise

    def get_all_keys(self):
        """
        Get all keys in the time series.

        Returns
        -------
        List
            List of keys in the time series.
        """
        return self.client.keys("ts:*")

    def query(
        self,
        key: str,
        offset: timedelta | int,
        resolution: typing.Literal["seconds", "minutes", "hours", "days", "weeks"],
    ) -> list[tuple[int, float]]:
        """
        Query the time series for a specific time range and resolution.

        Parameters
        ----------
        key : str
            The key for the time series.
        offset : timedelta | int
            The time delta from now to query or an integer representing milliseconds.
        resolution : "seconds", "minutes", "hours", "days", "weeks"
            The aggregation resolution (seconds, minutes, hours, days, weeks).

        Returns
        -------
        List
            List of aggregated time series data as tuples of (timestamp, value).
        """
        key = self.__format_keys(key)
        resolution_mapping = {
            "seconds": 1_000,  # Milliseconds
            "minutes": 60_000,  # Milliseconds
            "hours": 3_600_000,  # Milliseconds
            "days": 86_400_000,  # Milliseconds
            "weeks": 604_800_000,  # Milliseconds
        }

        if resolution not in resolution_mapping:
            raise ValueError(
                f"Invalid resolution '{resolution}'. Use one of: {list(resolution_mapping.keys())}"
            )

        # Calculate the time range
        now = round(datetime.now().timestamp() * 1_000)  # Redis expects milliseconds

        if isinstance(offset, int):
            # offset is already milliseconds
            start_time = now - offset
        elif isinstance(offset, timedelta):
            start_time = now - round(offset.total_seconds() * 1_000)
        else:
            raise TypeError(
                "offset must be a timedelta or an int representing milliseconds"
            )

        aggregation = resolution_mapping[resolution]

        try:
            print("Querying", key, start_time, now, aggregation)
            result: list[tuple[int, float]] = self.client.ts().range(
                key,
                start_time,
                now,
                aggregation_type="avg",
                bucket_size_msec=aggregation,
            )
        except redis.exceptions.ResponseError as e:
            if "TSDB" in str(e):
                # If the time series doesn't exist, create it and retry
                print("Creating time series", key)
                self.create_time_series(key)
                return []  # No data to return yet
            else:
                raise

        return result

    def join(
        self,
        keys: list[str],
        offset: typing.Optional[timedelta] = None,
        resolution: (
            typing.Literal["seconds", "minutes", "hours", "days", "weeks"] | None
        ) = None,
    ) -> list[schema.RedisTimeSeriesResponse]:
        """
        Join multiple time series on the same time range and fetch the latest row.

        Parameters
        ----------
        keys : list
            List of keys to join.
        offset : timedelta, optional
            The time range to join on. by default it is 8 hours.
        resolution : str
            The aggregation resolution ("seconds", "minutes", "hours", "days", "weeks").

        Returns
        -------
        List[RedisTimeSeriesResponse]
            List of joined time series data or the latest row data.
        """
        keys = self.__format_keys(keys)
        now = round(datetime.now().timestamp() * 1_000)

        offset = offset if offset else timedelta(hours=8)
        resolution = resolution if resolution else "seconds"

        # If range is provided, fetch data over the time range
        start_time = now - round(offset.total_seconds() * 1_000)
        try:
            print("Joining", keys, start_time, now)
            result = []
            for key in keys:
                data = self.query(key, offset, resolution)
                if data:
                    # Get the latest data point
                    result.append(
                        schema.RedisTimeSeriesResponse(
                            key=key, timestamp=data[-1][0], value=data[-1][1]
                        )
                    )
            return result
        except redis.exceptions.ResponseError as e:
            if "ERR TSDB" in str(e):
                # If the time series doesn't exist, create it and retry
                for key in keys:
                    self.client.ts().create(key)
                return []  # No data to return yet
            else:
                raise

    def delete_rows(
        self,
        key: str,
        timestamp: typing.Optional[int] = None,
        range: typing.Optional[timedelta] = None,
        older_than: typing.Optional[int] = None,
    ):
        """
        Delete rows from the time series.

        Parameters
        ----------
        key : str
            The key for the time series.
        timestamp: int (optional)
            The timestamp for the value in milliseconds.
        range: timedelta (optional)
            The time range to delete.
        older_than: int (optional)
            Delete all rows older than this timestamp (in milliseconds).

        Note
        ----
        - Either timestamp, range, or older_than must be provided.
        - If both range and older_than are provided, range will be used.
        """
        key = self.__format_keys(key)
        if range is not None:
            now = round(datetime.now().timestamp() * 1_000)
            start_time = now - round(range.total_seconds() * 1_000)
            self.client.ts().delete(key, start_time, now)
        elif older_than is not None:
            # Delete all rows older than the cutoff timestamp
            self.client.ts().delete(key, 0, older_than)
        elif timestamp is not None:
            self.client.ts().delete(key, timestamp, timestamp)
        else:
            raise ValueError("Either timestamp, range, or older_than must be provided.")

    def delete(self, key: str):
        """
        Delete a time series.

        Parameters
        ----------
        key : str
            The key for the time series.
        """
        key = self.__format_keys(key)
        self.client.delete(key)


class RedisNoSQLAdapter(ports.INoSQLDB):
    def __init__(self):
        self.client = redis.Redis(
            host=configs.RedisConfigsCreds.REDIS_HOST.value,
            port=int((configs.RedisConfigsCreds.REDIS_PORT.value or 6379)),
            password=configs.RedisConfigsCreds.REDIS_PASSWORD.value,
        )

    def put(self, key: str, value: dict[str, typing.Any]) -> bool:

        try:
            flattened_content = {k: json.dumps(v) for k, v in value.items()}
            self.client.hset(key, mapping=flattened_content)  # type: ignore
            return True
        except Exception as error:
            print("Error in put_resource:", error)
            return False

    def get(self, key: str) -> dict[str, typing.Any]:
        try:
            data: dict[bytes, bytes] = self.client.hgetall(key)  # type: ignore
            if not data:
                return dict()

            return {k.decode("utf-8"): json.loads(v) for k, v in data.items()}
        except Exception as error:
            print("Error in get_resource:", error)
            return dict()

    def delete(self, key: str) -> bool:
        try:
            self.client.delete(key)
            return True
        except Exception as error:
            print("Error in delete_resource:", error)
            return False


class RedisTopicResourceAdapter:
    """
    Adapter for Redis that stores resources under composite keys of the form
    "topic:resourceId" using Redis hashes.

    The adapter provides simple CRUD operations where each resource is a hash
    and each field value is JSON-encoded for consistency.

    Examples
    --------
    >>> adapter = RedisTopicResourceAdapter()
    >>> adapter.put_resource("production", "resource123", {"k": "v"})
    True
    >>> adapter.get_resource("production", "resource123")
    {'k': 'v'}
    >>> adapter.get_resources("production")  # doctest: +ELLIPSIS
    [...]
    >>> adapter.delete_resource("production", "resource123")
    True
    >>> adapter.close()
    None
    """

    def __init__(self) -> None:
        self.client = redis.Redis(
            host=configs.RedisConfigsCreds.REDIS_HOST.value,
            port=int((configs.RedisConfigsCreds.REDIS_PORT.value or 6379)),
            password=configs.RedisConfigsCreds.REDIS_PASSWORD.value,
            decode_responses=True,
        )

    async def _resolve(self, value):
        return await value if inspect.isawaitable(value) else value

    def put_resource(
        self, topic: str, resource_id: str, content: dict[str, typing.Any]
    ) -> bool:
        """
        Put a resource into Redis using topic as the primary key and resource_id as the secondary key.

        Parameters
        ----------
        topic : str
            The primary key, e.g., "production".
        resource_id : str
            The secondary key, e.g., "resource123".
        content : dict[str, Any]
            The content to store as a hash under the composite key.

        Returns
        -------
        bool
            True if successfully stored, otherwise False.
        """
        key = f"{topic}:{resource_id}"
        flattened_content = {k: json.dumps(v) for k, v in content.items()}
        print("PUT", key, content)
        try:
            self.client.hset(key, mapping=flattened_content)
            return True
        except Exception as error:
            print("Error in put_resource:", error)
            return False

    async def get_resource(
        self, topic: str, resource_id: str
    ) -> typing.Optional[dict[str, typing.Any]]:
        """
        Get a resource from Redis using topic and resource_id as the composite key.

        Parameters
        ----------
        topic : str
            The primary key, e.g., "production".
        resource_id : str
            The secondary key, e.g., "resource123".

        Returns
        -------
        dict[str, Any] or None
            The resource if found, otherwise None.
        """
        key = f"{topic}:{resource_id}"
        try:
            raw = self.client.hgetall(key)
            data : dict[str, typing.Any] = await self._resolve(raw)
            if not data:
                return None
            parsed: dict[str, typing.Any] = {}
            for k, v in data.items():
                try:
                    parsed[k] = json.loads(v)
                except Exception:
                    parsed[k] = v
            return parsed
        except Exception as error:
            print("Error in get_resource:", error)
            return None

    async def get_resources(self, topic: str) -> list[dict[str, typing.Any]]:
        """
        Get all resources for a specific topic by scanning for keys with the prefix "topic:".

        Parameters
        ----------
        topic : str
            The primary key/prefix, e.g., "production".

        Returns
        -------
        list[dict[str, Any]]
            The list of resources under the topic.
        """
        pattern = f"{topic}:*"
        try:
            raw_keys = self.client.keys(pattern)
            keys = await self._resolve(raw_keys)
            if len(keys) == 0:
                return []

            resources: list[dict[str, typing.Any]] = []
            for key in keys:
                raw_hash = self.client.hgetall(key)
                data: dict[str, typing.Any] = await self._resolve(raw_hash)
                if data:
                    parsed: dict[str, typing.Any] = {}
                    for k, v in data.items():
                        try:
                            parsed[k] = json.loads(v)
                        except Exception:
                            parsed[k] = v
                    resources.append(parsed)
            return resources
        except Exception as error:
            print("Error in get_resources:", error)
            return []

    def delete_resource(self, topic: str, resource_id: str) -> bool:
        """
        Delete a specific resource using topic and resource_id.

        Parameters
        ----------
        topic : str
            The primary key, e.g., "production".
        resource_id : str
            The secondary key, e.g., "resource123".

        Returns
        -------
        bool
            True if successfully deleted, otherwise False.
        """
        key = f"{topic}:{resource_id}"
        try:
            self.client.delete(key)
            return True
        except Exception as error:
            print("Error in delete_resource:", error)
            return False

    def close(self) -> None:
        """
        Close the connection to Redis.

        Returns
        -------
        None
        """
        try:
            self.client.close()
        except Exception as error:
            print("Error closing Redis client:", error)
        return None

class PrefectWorkflowEngineAdapter:
    """
    This class is used to create workflows and tasks using Prefect.
    for more information on Prefect see https://docs.prefect.io/core/

    Parameters
    ----------
    debug_mode : bool
        If True, the task execution sequence will be logged to stdout.
    register_runs : bool
        - If True, the task runs will be registered in the Prefect server.
            - This is useful if you want to view task dependencies in the Prefect UI. (@see `update_run_context`)
            - Note: This will require you to add `orchestration.update_run_context()` at the top of the workflows update the task run to register, otherwise you will get a 409 error.
        - If False, you will not see the task runs in the Prefect UI, however, you can still see the logs within the tasks
        by piping them to the orchestrator using `orchestrator.log_message(task.name, "message!")` and within the workflow
        you can print them using `orchestrator.print_task_messages()`

    notify_user_on_crash : bool
        If True, the user will be notified via email when a task fails.
    user_email : str
        The email address of the user to notify when a task fails.
        This will only be used if notify_user_on_crash is True.

    Example
    -------
    ```python
    from modelOS_spec.use_cases.use_cases import PrefectWorkflowEngineAdapter

    orchestrator = PrefectWorkflowEngineAdapter()

    @orchestrator.task("Stream Sensor Data")
    def stream_data():
        return 10

    @orchestrator.task("Process Sensor Data", task_dependencies=dict(data=stream_data))
    def process_data(data: int):
        return data * 10

    @orchestrator.task("Record Sensor Data", task_dependencies=dict(data=stream_data))
    def record_data(data: int):
        print("Recording data", data)

    @orchestrator.task("Filter Sensor Data", task_dependencies=dict(data=process_data))
    def filter_data(data: int, n: int):
        if data > n:
            return data
        else:
            return None

    @orchestrator.workflow("Sensor Data Processing")
    def process_sensor_data(n: int =50):
        orchestrator.update_run_context()

        # Listen to data streamed from sensors
        data = stream_data()

        # Record the data
        record_data(data)

        # Process the data
        processed_data = process_data(data)

        # Filter the data
        filtered_data = filter_data(processed_data, n=n)

        # Display the filtered data
        print("Filtered Data", filtered_data)


    if __name__ == "__main__":
        # Run the workflow locally during development
        process_sensor_data()

        # Deploy the workflow when ready
        orchestration.deploy(
            flow=process_sensor_data,
            repo_url="https://github.com/kesler20/modelOS_spec.git",
            flow_path=os.path.join(base_dir,"src", "modelOS_spec", "infrastructure", "adapters.py:main"),
            docker_image_name="wizapp40/process_sensor_data",
            docker_image_tag="latest",
            docker_file_path="Dockerfile",
            parameters=dict(n=10),
        )
        ```
    """

    # TODO: add support for event triggered workflows
    def __init__(
        self,
        debug_mode: bool = False,
        register_runs: bool = True,
        notify_user_on_crash: bool = True,
        user_email: str = "uchekesla@gmail.com",
    ) -> None:
        self.debug_mode = debug_mode
        self.current_flow_run_id = uuid.uuid4()
        self.task_run_results: typing.List[schema.TaskRunRecord] = []
        self.register_runs = register_runs
        self.notify_user_on_crash = notify_user_on_crash
        self.user_email = user_email
        self.task_message_queue: list[dict[str, typing.Any]] = []

    def __log_task(self, func):
        def wrapper(*args, **kwargs):
            logger = get_run_logger()
            logger.log(
                level=logging.WARNING,
                msg=f"Task {func.__name__} called with args: {args} kwargs: {kwargs}",
            )
            result = func(*args, **kwargs)
            logger.log(
                level=logging.WARNING, msg=f"Task {func.__name__} returned: {result}"
            )
            return result

        return wrapper

    def __format_deployment_name(self, flow_name: str, version: str) -> str:
        """Format the deployment name to be used in Prefect."""
        return f"{flow_name}:{version}"

    def __register_task_run(
        self,
        current_task: Task[..., typing.Any],
        task_run: TaskRun,
        state: State[typing.Any],
        upstream_tasks: typing.List[schema.UpstreamTask] = [],
    ):
        task_inputs = task_run.task_inputs
        for upstream_task in upstream_tasks:
            upstream_task_was_recorded = any(
                list(
                    filter(
                        lambda record: record.task_name  # type: ignore
                        == upstream_task.upstream_task.name,
                        self.task_run_results,
                    )
                )
            )

            if upstream_task_was_recorded:
                task_run_recorded = list(
                    filter(
                        lambda record: record.task_name
                        == upstream_task.upstream_task.name,
                        self.task_run_results,
                    )
                )[0].task_run

                task_inputs[upstream_task.param_name].append(
                    TaskRunResult(id=task_run_recorded.id)
                )

        async def create_task_run():

            async with get_client() as client:
                task_run_created = await client.create_task_run(
                    flow_run_id=self.current_flow_run_id,
                    name=current_task.name,
                    task=current_task,
                    state=state,
                    dynamic_key=task_run.dynamic_key,  # Ensure a unique dynamic key
                    task_inputs=task_inputs,
                )

                self.task_run_results.append(
                    schema.TaskRunRecord(
                        task_name=current_task.name, task_run=task_run_created
                    )
                )

        # Run the async function
        import asyncio

        asyncio.run(create_task_run())

    def get_logger(self):
        from prefect import get_run_logger

        return get_run_logger

    def log_message(self, task_name: str, *message):
        self.task_message_queue.append(dict(task_name=task_name, message=message))

    def print_task_messages(self):
        for message in self.task_message_queue:
            print(f"{message['task_name']} ☑️", *message["message"])
            self.task_message_queue.remove(message)

    def task(
        self,
        name: str,
        version: float = 1.0,
        task_dependencies: typing.Optional[dict[str, Task[..., typing.Any]]] = None,
        on_failure: None | typing.List[typing.Callable[..., typing.Any]] = None,
        on_completion: None | typing.List[typing.Callable[..., typing.Any]] = None,
        description: None | str = None,
        run_name: None | str = None,
        retry_condition_fn: None | typing.Callable[..., bool] = None,
    ):
        """Note: ensure that the function is decorating has only serialisable parameters

        Example
        -------
        To create a dependency between two tasks that do not exchange data,
        but one needs to wait for the other to finish,
        use the special wait_for keyword argument:
        ```python
        @step
        def task_1():
            pass

        @step
        def task_2():
            pass

        @workflow
        def my_flow():
            x = task_1()

            # task 2 will wait for task_1 to complete
            y = task_2(wait_for=[x])
        """
        from prefect import task

        ## Setup upstream tasks if the task_dependencies is not None
        upstream_tasks = []
        if task_dependencies is not None:
            upstream_tasks = [
                schema.UpstreamTask(
                    param_name=key,
                    upstream_task=value,
                )
                for key, value in task_dependencies.items()
            ]

        ## Register flow runs if the register_runs is True
        if self.register_runs:

            def on_completion_callback(current_task, task_run, state):
                self.__register_task_run(
                    current_task,
                    task_run,
                    state,
                    upstream_tasks,
                )

            if on_completion is None:
                on_completion = [on_completion_callback]
            else:
                on_completion.append(on_completion_callback)

        ## Add logging to the task if debug_mode is True
        if self.debug_mode:

            def decorator(func):
                decorated_task: Task[..., typing.Any] = task(
                    name=name,
                    description=description,
                    task_run_name=(
                        f"{name} run @{datetime.now()}"
                        if run_name is None
                        else run_name
                    ),
                    on_failure=on_failure,
                    on_completion=on_completion,
                    retry_condition_fn=retry_condition_fn,
                    version=f"v{version}",
                    log_prints=True,
                )(self.__log_task(func))
                return decorated_task

            return decorator

        # Modify task to send notification if notify_user_on_crash is True
        if self.notify_user_on_crash:

            def send_error_notification(
                task: Task[..., typing.Any], task_run: TaskRun, state: State[typing.Any]
            ):
                # Send an email notification with the exception details
                self.send_email_notification(
                    f"Your job {task.name} entered {state.name} State",
                    f"""See https://{configs.PrefectConfigsCreds.PREFECT_API_URL.value}/task-runs/{task_run.id}
Version: {task.version}
Run Name: {task_run.name}
                """,
                )

            on_failure = [] if on_failure is None else on_failure
            on_failure.append(send_error_notification)

        return task(
            name=name,
            description=description,
            task_run_name=(
                f"{name} run @{datetime.now()}" if run_name is None else run_name
            ),
            on_failure=on_failure,
            on_completion=on_completion,
            retry_condition_fn=retry_condition_fn,
            version=f"v{version}",
            log_prints=True,
        )

    def get_deployment(self, flow_name: str, flow_version: str) -> typing.Any:
        deployment_name = self.__format_deployment_name(flow_name, flow_version)

        async def get_deployment(deployment_name: str):
            async with get_client() as client:
                deployment = await client.read_deployment_by_name(deployment_name)
                print(deployment)
                return deployment.id

        return asyncio.run(get_deployment(deployment_name))

    def update_run_context(self):
        """This method is used to update the run context of the current flow run.
        Call this function within a flow before calling any tasks, when you want to update the context in order to register task runs and upstream tasks.

        Example
        -------
        ```python
        @orchestration.task(name="Test Task")
        def test_task():
            print("Test task running")
            return 10

        @orchestration.task(name="Publish data", task_dependencies=dict(data=test_task))
        def fancy_print(topic: str, message: str):
            print(f"Publishing {message} to {topic}")
            orchestrator.update_run_context()

        @orchestration.workflow(name="Test Workflow", version="1")
        def my_workflow(name: str = "World"):
            while True:
                try:
                    # Update the run context.
                    orchestrator.update_run_context()

                    # Call the task with the updated context.
                    data = test_task()

                    # application running in the loop
                    fancy_print("testing", data)
                    time.sleep(5)
                except Exception as e:
                    print(f"Error: {e}")
                    pass

        if __name__ == "__main__":
            # Run the workflow locally during development
            my_workflow()
        ```
        """
        from prefect.context import get_run_context

        run_context = get_run_context()
        if isinstance(run_context, FlowRunContext):
            flow_run_context = run_context.flow_run
            if flow_run_context is not None:
                self.current_flow_run_id = flow_run_context.id  # type: ignore

    def workflow(
        self,
        name: str,
        version: float = 1.0,
        description: None | str = None,
        run_name: None | str = None,
        validate_parameters=True,
        on_completion: None | typing.List[typing.Callable[..., typing.Any]] = None,
    ):
        """Note: ensure that the function is decorating has only serialisable parameters.
        you can deploy this using the `serve` method.
        """
        from prefect import flow
        from datetime import datetime

        return flow(
            name=name,
            version=f"v{version}",
            log_prints=True,
            description=description,
            validate_parameters=validate_parameters,
            flow_run_name=(
                f"{name} run @{datetime.now()}" if run_name is None else run_name
            ),
            on_completion=on_completion,
        )

    def visualise(self, flow: Flow[..., typing.Any]):
        async def visualise():
            await flow.visualize()

        asyncio.run(visualise())

    def delete_existing_deployment(self, deployment_name: str):
        async def delete_deployment(deployment_name: str):
            client = get_client()
            deployment = await client.read_deployment_by_name(deployment_name)
            await client.delete_deployment(deployment.id)

        asyncio.run(delete_deployment(deployment_name))

    def create_github_credentials(self, user_name, token):
        from prefect_github import GitHubCredentials

        creds = GitHubCredentials(
            name=f"{user_name}-admin-creds",
            token=token,
        )
        creds.save(f"{user_name}-admin-creds")
        print(f"Credentials {user_name}-admin-creds added successfully✅!")

    def deploy(
        self,
        workflow: Flow[..., typing.Any],
        github_repo_name: str,
        flow_path: str,
        docker_image_name: str,
        docker_image_tag: str,
        docker_file_path: str,
        schedule: typing.Optional[timedelta] = None,
        additional_job_variables: None | dict[str, str] = None,
        parameters: None | typing.Dict[str, typing.Any] = None,
    ):
        """Example of how to deploy a flow to a GitHub repository.

        Parameter
        ---------
        workflow : None | Flow[..., typing.Any]
            The flow to deploy.
        github_repo_name : str
            The name of the GitHub repository the code is hosted in.
        flow_path : str
            The path to the flow file in the repository.
            for example "src/modelOS_spec/infrastructure/adapters.py:main"
        docker_image_name : str
            The name of the Docker image to build and push to the repository.
            for example "wizapp40/test_workflow"
        docker_image_tag : str
            The tag of the Docker image to build and push to the repository.
            for example "latest"
        docker_file_path : str
            The path to the Dockerfile in the repository.
            for example "Dockerfile"
        schedule : timedelta
            The schedule for the deployment. If None, the flow will be deployed without a schedule.
            Defaults to None.
        parameters : None | dict[str, typing.Any]
            The parameters to pass to the flow. If None, the flow will be deployed without parameters.

        Raises
        ------
        ValueError
            If neither `workflow` nor `services` is provided.

        Note
        ----
        Before running this method:
        - Here is an example Dockerfile that you can use https://github.com/kesler20/modelOS_spec/blob/master/Dockerfile.
        - Also make sure that the docker engine is running on your machine.
        - make sure you have created a GitHub credentials block in Prefect Cloud with the name "{username}-admin-creds"
        - make sure that you have a GITHUB repository with a master branch

        Example
        -------
        ```python

        orchestration.deploy(
            workflow=test_workflow,
            repo_url="https://github.com/kesler20/modelOS_spec.git",
            flow_path=os.path.join("src", "modelOS_spec", "infrastructure", "adapters.py"),
            docker_image_name="wizapp40/test_workflow",
            docker_image_tag="latest",
            docker_file_path="Dockerfile",
            parameters=dict(n=10),
        )
        ```
        """
        repo_url = f"https://github.com/{configs.GithubConfigsCreds.GITHUB_USERNAME.value}/{github_repo_name}.git"

        from prefect.runner.storage import GitRepository
        from prefect_github import GitHubCredentials
        from prefect.deployments.runner import DockerImage  # type: ignore

        try:
            credentials = GitHubCredentials.load(
                f"{configs.GithubConfigsCreds.GITHUB_USERNAME.value}-admin-creds"
            )
        except ValueError:
            GitHubCredentials(token=configs.GithubConfigsCreds.PAT.value).save(
                name=f"{configs.GithubConfigsCreds.GITHUB_USERNAME.value}-admin-creds",
                overwrite=True,
            )
            credentials = GitHubCredentials.load(
                f"{configs.GithubConfigsCreds.GITHUB_USERNAME.value}-admin-creds"
            )

        source = GitRepository(url=repo_url, branch="master", credentials=credentials)

        print(flow_path)
        workflow.from_source(
            source=source,
            entrypoint=flow_path,
        ).deploy(  # type: ignore
            name=workflow.name + " Deployment",
            work_pool_name="default",
            interval=schedule,
            image=DockerImage(
                name=docker_image_name,
                tag=docker_image_tag,
                dockerfile=docker_file_path,
            ),
            push=True,
            parameters=parameters,
            job_variables=dict(
                env=dict(
                    ENTRYPOINT=flow_path.replace(":run", ""),
                    **(additional_job_variables or {}),
                )
            ),
        )
        print(f"Deployed {workflow.name} to {workflow.name} Deployment")

    def send_email_notification(self, subject: str, message: str):
        from prefect import flow

        # from prefect_email import EmailServerCredentials, email_send_message

        @flow(name="Send Email Notifications", version="v1")  # type: ignore
        def send_notification(subject: str, message: str, email_to: str) -> None:
            try:
                gmail_client = GmailApi()
                gmail_client.send_email(
                    message=message,
                    subject=subject,
                    recipient=email_to,
                )
                print(f"Sent email to {email_to} with subject: {subject}")
            except Exception as e:
                print(f"Failed to send email: {e}")
                RedisNoSQLAdapter().put(
                    f"error_logs:email_notification_service:{round(datetime.now().timestamp() * 1_000)}",
                    dict(
                        error=str(e),
                    ),
                )

        send_notification(subject=subject, message=message, email_to=self.user_email)


class FileIOAdapter:
    """
    A class for reading, writing and grabbing files.

    Parameters
    ----------
    filename : Path
        The path to the file to be manipulated.
    relative_path : Tuple[str]
        string arguments which correspond to the relative path of a file
        if the length of this tuple is none zero, the first argument will also be used to make
        a path using `os.path.join(filename, *relative_path)`

    Example
    -------
    ```python
    >>> lines = FileIOAdapter("path/to/python/file").readlines()
    >>> lines = FileIOAdapter("path", "to", "python","file").readlines()
    ```

    """

    def __init__(self, filename: typing.Union[Path, str], *relative_path) -> None:
        if type(filename) == str:
            filename = Path(filename)

        if len(relative_path) > 0:
            filename = Path(os.path.join(filename, *relative_path))

        self.filename = filename.as_posix()  # type: ignore

    def __repr__(self) -> str:
        return f"""
File(
    file_path={self.filename},
    filename={os.path.basename(self.filename)},
    exists={self.exists()}
)
        """

    def size(self) -> int:
        """Return the size of the file in bytes."""
        return os.path.getsize(self.filename)

    def exists(self) -> bool:
        """Returns True if the filename path passed to the constructor exists."""
        return os.path.exists(self.filename)

    def is_file(self) -> bool:
        """Returns True if the current path is a file."""
        return os.path.isfile(self.filename)

    def extend_filename(self, extension: str):
        """Extend the filename with the given extension.

        Parameters
        ----------
        extension : str
            The extension to be added to the filename.

        Returns
        -------
        FileIOAdapter
            The current instance with the updated filename.
        """
        self.filename = os.path.join(self.filename, extension)
        return self

    def copy(self) -> "FileIOAdapter":
        """Create a copy of the current FileIOAdapter instance.

        Returns
        -------
        FileIOAdapter
            A new instance of FileIOAdapter with the same filename.
        """
        return FileIOAdapter(self.filename)

    def read(self) -> str:
        """
        Read the contents of the file.

        Returns
        -------
        str
            The contents of the file as a string.
        """
        with open(self.filename, "r") as file:
            content = file.read()
        return content

    def read_as_utf8(self) -> str:
        """
        Read the contents of the file with UTF-8 encoding.

        Returns
        -------
        str
            The contents of the file as a string.
        """
        with open(self.filename, "r", encoding="utf-8") as file:
            content = file.read()
        return content

    def append(self, content: str) -> None:
        """
        Append content to the file.

        Parameters
        ----------
        content : str
            The content to be appended to the file.
        Note
        ----
        - If the directory of the file does not exist, it will be created.
        """
        # check that the dirname exists and create it if it doesn't
        os.makedirs(os.path.dirname(self.filename), exist_ok=True)
        with open(self.filename, "a") as file:
            file.write(content + "\n")

    def append_as_utf8(self, content: str) -> None:
        """
        Append content to the file with UTF-8 encoding.

        Parameters
        ----------
        content : str
            The content to be appended to the file.
        Note
        ----
        - If the directory of the file does not exist, it will be created.
        """
        # check that the dirname exists and create it if it doesn't
        os.makedirs(os.path.dirname(self.filename), exist_ok=True)
        with open(self.filename, "a", encoding="utf-8") as file:
            file.write(content + "\n")

    def append_after_line(self, line_number: int, new_content: str) -> None:
        """
        Append new_content after a specific line in the file.

        Parameters
        ----------
        line_number : int
            The line number after which the new_content will be appended.
        new_content : str
            The new_content to be appended to the file.
        Note
        ----
        - If the directory of the file does not exist, it will be created.
        """
        # check that the dirname exists and create it if it doesn't
        os.makedirs(os.path.dirname(self.filename), exist_ok=True)
        with open(self.filename, "r") as file:
            existing_content: typing.List[str] = file.readlines()
            existing_content.insert(line_number + 1, new_content)

        with open(self.filename, "w") as file:
            file.writelines(new_content)

    def append_after_example(self, example: str, new_content: str) -> None:
        """
        Append new_content after a line in the file that matches a specific example.

        Parameters
        ----------
        example : str
            A string that is present in the line after which the new_content will be appended.
        new_content : str
            The new_content to be appended to the file.
        Note
        ----
        - If the directory of the file does not exist, it will be created.
        """
        # check that the dirname exists and create it if it doesn't
        os.makedirs(os.path.dirname(self.filename), exist_ok=True)
        with open(self.filename, "r") as file:
            existing_content = file.readlines()

        for i, line in enumerate(existing_content):
            if example in line:
                existing_content.insert(i + 1, new_content)

        with open(self.filename, "w") as file:
            file.writelines(existing_content)

    def append_after_example_utf8(self, example: str, new_content: str) -> None:
        """
        Append new_content after a line in the file that matches a specific example.

        Parameters
        ----------
        example : str
            A string that is present in the line after which the new_content will be appended.
        new_content : str
            The new_content to be appended to the file.
        Note
        ----
        - If the directory of the file does not exist, it will be created.
        """
        # check that the dirname exists and create it if it doesn't
        os.makedirs(os.path.dirname(self.filename), exist_ok=True)
        with open(self.filename, "r", encoding="utf-8") as file:
            existing_content = file.readlines()

        for i, line in enumerate(existing_content):
            if example in line:
                existing_content.insert(i + 1, new_content)

        with open(self.filename, "w", encoding="utf-8") as file:
            file.writelines(existing_content)

    def write_as_utf8(self, content: str) -> None:
        """
        Write content to the file with UTF-8 encoding, overwriting the existing content.

        Parameters
        ----------
        content : str
            The content to be written to the file.

        Note
        ----
        - If the directory of the file does not exist, it will be created.
        """
        # check that the dirname exists and create it if it doesn't
        os.makedirs(os.path.dirname(self.filename), exist_ok=True)
        with open(self.filename, "w", encoding="utf-8") as file:
            file.write(content)

    def write(self, content: str) -> None:
        """
        Write content to the file, overwriting the existing content.

        Parameters
        ----------
        content : str
            The content to be written to the file.

        Note
        ----
        - If the directory of the file does not exist, it will be created.
        """
        # check that the dirname exists and create it if it doesn't
        os.makedirs(os.path.dirname(self.filename), exist_ok=True)
        with open(self.filename, "w") as file:
            file.write(content)

    def readlines_as_utf8(self) -> typing.List[str]:
        """
        Read the lines of the file with UTF-8 encoding.

        Returns
        -------
        list[str]
            The lines of the file as a list of strings.
        """
        with open(self.filename, "r", encoding="utf-8") as file:
            content: typing.List[str] = file.readlines()
        return content

    def update_line(self, line_number: int, new_content: str) -> None:
        """
        Update a specific line in the file.

        Parameters
        ----------
        line_number : int
            The line number to be updated.
        new_content : str
            The new content to be written to the specified line.
        """
        with open(self.filename, "r") as file:
            content = file.readlines()

        content[line_number] = new_content

        with open(self.filename, "w") as file:
            file.writelines(content)

    def update_line_by_example(self, example: str, new_content: str) -> None:
        """
        Update a line in the file that matches a specific example.

        Parameters
        ----------
        example : str
            A string that is present in the line to be updated.
        new_content : str
            The new content to be written to the specified line.
        """
        with open(self.filename, "r") as file:
            content = file.readlines()

        for i, line in enumerate(content):
            if example in line:
                content[i] = new_content

        with open(self.filename, "w") as file:
            file.writelines(content)

    def readlines(self) -> typing.List[str]:
        """
        Read the lines of the file.

        Returns
        -------
        list[str]
            The lines of the file as a list of strings.
        """
        with open(self.filename, "r") as file:
            content = file.readlines()
        return content

    def get_json(self) -> typing.Dict[typing.Any, typing.Any]:
        """
        Read the contents of a JSON file.

        Returns
        -------
        dict
            The contents of the JSON file as a dictionary.
        """
        with open(self.filename, "r") as json_file:
            content: typing.Dict[typing.Any, typing.Any] = json.loads(json_file.read())
        return content

    def write_json(
        self,
        content: typing.Union[typing.Dict[str, typing.Any], typing.List[typing.Any]],
    ) -> None:
        """
        Write the contents to a JSON file.

        Parameters
        ----------
        content : dict or list
            The content to be written to the JSON file.
        Note
        ----
        - If the directory of the file does not exist, it will be created.
        """
        # check that the dirname exists and create it if it doesn't
        os.makedirs(os.path.dirname(self.filename), exist_ok=True)
        with open(self.filename, "w") as json_file:
            json_file.write(json.dumps(content, indent=2))

    def writeline(self, content: str) -> None:
        """
        Write a single line to the file, overwriting the existing content.

        Parameters
        ----------
        content : str
            The content to be written as a single line to the file.
        Note
        ----
        - If the directory of the file does not exist, it will be created.
        """
        # check that the dirname exists and create it if it doesn't
        os.makedirs(os.path.dirname(self.filename), exist_ok=True)
        with open(self.filename, "w") as file:
            file.write(f"{content}\n")

    def writelines(self, content: typing.List[str]) -> None:
        """
        Write multiple lines to the file, overwriting the existing content.

        Parameters
        ----------
        content : list[str]
            A list of strings to be written as lines to the file.
        Note
        ----
        - If the directory of the file does not exist, it will be created.
        """
        # check that the dirname exists and create it if it doesn't
        os.makedirs(os.path.dirname(self.filename), exist_ok=True)
        with open(self.filename, "w") as file:
            file.writelines([f"{line}" for line in content])

    def read_line_by_condition(
        self, condition: typing.Callable[[str], bool]
    ) -> typing.List[str]:
        """
        Read lines from the file that meet a specific condition.

        Parameters
        ----------
        condition : Callable
            A function that takes a line as input and returns a boolean value.
            If True, the line will be included in the output list.

        Returns
        -------
        list[str]
            A list of lines from the file that meet the specified condition.
        """
        with open(self.filename, "r") as file:
            content: typing.List[str] = file.readlines()

        return list(filter(condition, content))

    def rename_file(self, new_name: str) -> None:
        """
        Rename the file.

        Parameters
        ----------
        new_name : str
            The new name of the file.
        """
        os.rename(self.filename, os.path.join(os.path.dirname(self.filename), new_name))

    def delete(self) -> None:
        """
        Delete the file.

        Returns
        -------
        None
        """
        os.remove(self.filename)


class FileNoSQLAdapter(ports.INoSQLDB):
    def __init__(
        self, base_dir: typing.Optional[str] = None, path: typing.Optional[str] = None
    ):
        self.base_dir = (
            os.path.join(os.path.dirname(__file__), "@nosql_db", path or "")
            if base_dir is None
            else os.path.join(base_dir, path or "")
        )
        os.makedirs(self.base_dir, exist_ok=True)

    def __get_file_path(self, key: str) -> str:
        return os.path.join(self.base_dir, f"{key}.json")

    def put(
        self, key: str, value: typing.Any, ttl: typing.Optional[int] = None
    ) -> typing.Any:
        file_path = self.__get_file_path(key)
        file_path = file_path.replace(":", os.sep)
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, "w") as f:
            json.dump(value, f, indent=4)
        return value

    def get(self, key: str) -> typing.Any:
        file_path = self.__get_file_path(key)
        file_path = file_path.replace(":", os.sep)
        if not os.path.exists(file_path):
            return None
        with open(file_path, "r") as f:
            data = json.load(f)
        return data

    def delete(self, key: str) -> typing.Any:
        file_path = self.__get_file_path(key)
        file_path = file_path.replace(":", os.sep)
        if os.path.exists(file_path):
            os.remove(file_path)
            return True
        return False


class S3ObjectStorageAdapter(ports.IObjectStorage):
    def __init__(self, S3_BUCKET_NAME: typing.Optional[str] = None) -> None:
        self.bucket_name = (
            S3_BUCKET_NAME
            or configs.AwsConfigsCreds.DATA_LAKE_NAME.value
            or "process-data-lake"
        )
        self.s3_resource = boto3.resource(
            "s3",
            aws_access_key_id=configs.AwsConfigsCreds.AWS_ACCESS_KEY_ID.value,
            aws_secret_access_key=configs.AwsConfigsCreds.AWS_SECRET_ACCESS_KEY.value,
            region_name=configs.AwsConfigsCreds.AWS_REGION.value,
        )
        self.bucket = self.s3_resource.Bucket(self.bucket_name)

    def write_object(self, resource_locator: str, content: typing.Any):
        if isinstance(content, (dict, list)):
            content = json.dumps(content).encode("utf-8")
        elif isinstance(content, str):
            content = content.encode("utf-8")
        elif isinstance(content, bytes):
            pass
        else:
            raise TypeError("Unsupported content type for S3 storage")

        self.bucket.put_object(Key=resource_locator, Body=content)

    def read_object(self, resource_locator: str) -> typing.Optional[typing.Any]:
        try:
            obj = self.s3_resource.Object(self.bucket_name, resource_locator)
            content = obj.get()["Body"].read().decode("utf-8")
            try:
                return json.loads(content)
            except json.JSONDecodeError:
                return content  # If not JSON, return raw string
        except self.s3_resource.meta.client.exceptions.NoSuchKey:
            return None

    def delete_object(self, resource_locator: str):
        self.s3_resource.Object(self.bucket_name, resource_locator).delete()


class MinIOObjectStorageAdapter(ports.IObjectStorage):
    """
    Drop-in replacement for S3ObjectStorageAdapter that talks to MinIO.
    """

    def __init__(self) -> None:
        endpoint = configs.MinioConfigsCreds.MINIO_PUBLIC_ENDPOINT.value
        access_key = configs.MinioConfigsCreds.MINIO_ROOT_USER.value
        secret_key = configs.MinioConfigsCreds.MINIO_ROOT_PASSWORD.value
        self.bucket_name = configs.MinioConfigsCreds.MINIO_BUCKET.value

        if not access_key or not secret_key:
            raise ValueError("MINIO_ROOT_USER and MINIO_ROOT_PASSWORD must be set")

        # Use boto3 against MinIO (S3-compatible)
        self.s3_resource = boto3.resource(
            "s3",
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            endpoint_url=endpoint,
            region_name="eu-west-2",  # MinIO ignores region; keep a default
            config=BotoConfig(
                signature_version="s3v4", s3={"addressing_style": "path"}
            ),
        )
        self.bucket = self.s3_resource.Bucket(self.bucket_name)

        # Ensure bucket exists
        try:
            self.s3_resource.meta.client.head_bucket(Bucket=self.bucket_name)
        except Exception:
            self.s3_resource.create_bucket(Bucket=self.bucket_name)

    def write_object(self, resource_locator: str, content: typing.Any):
        if isinstance(content, (dict, list)):
            content = json.dumps(content).encode("utf-8")
        elif isinstance(content, str):
            content = content.encode("utf-8")
        elif isinstance(content, bytes):
            pass
        else:
            raise TypeError("Unsupported content type for object storage")
        self.bucket.put_object(Key=resource_locator, Body=content)

    def read_object(self, resource_locator: str) -> typing.Optional[typing.Any]:
        try:
            obj = self.s3_resource.Object(self.bucket_name, resource_locator)
            content = obj.get()["Body"].read().decode("utf-8")
            try:
                return json.loads(content)
            except json.JSONDecodeError:
                return content  # raw string
        except self.s3_resource.meta.client.exceptions.NoSuchKey:
            return None

    def delete_object(self, resource_locator: str):
        self.s3_resource.Object(self.bucket_name, resource_locator).delete()


class MLflowExperimentTrackingAdapter:

    def __init__(
        self,
        artifact_location: str | None = None,
        tracking_uri: str | None = None,
        artifact_repository: ports.IObjectStorage = MinIOObjectStorageAdapter(),
    ) -> None:
        # if the user provides a different artifact location and tracking server is up to them to launch the mlflow server
        self.artifact_location = (
            artifact_location
            or configs.MlflowConfigsCreds.MLFLOW_ARTIFACTS_BUCKET.value
        )
        self.artifact_repository = artifact_repository
        self.tracking_uri = (
            tracking_uri or configs.MlflowConfigsCreds.MLFLOW_TRACKING_URI.value
        )
        mlflow.set_tracking_uri(self.tracking_uri)
        self.experiment_id: typing.Optional[str] = None

    def __log_data_artifacts(
        self, data_artifacts: typing.List[entities.DataArtifact]
    ) -> None:
        for data_artifact in data_artifacts:
            with tempfile.TemporaryDirectory() as tmpdirname:
                data_set = mlflow.data.from_pandas(data_artifact.data)  # type: ignore

                data_artifact.data.to_csv(
                    tmpdirname + f"/{data_artifact.artifact_name}.csv", index=False
                )

                mlflow.log_input(data_set)

                mlflow.log_artifact(
                    tmpdirname + f"/{data_artifact.artifact_name}.csv",
                    artifact_path="Data",
                )

    def __save_as_pickle(self, model, path):
        import pickle

        with open(path, "wb") as f:
            pickle.dump(model, f)

    def __get_current_commit_hash(self, repo_path="."):
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repo_path,
            stdout=subprocess.PIPE,
            text=True,
        )
        return result.stdout.strip()

    def __log_custom_model(
        self,
        input_example: pd.DataFrame,
        output_example: pd.DataFrame | None,
        model_params: dict[str, typing.Any],
        model: entities.PredictiveModel,
    ) -> None:
        # log the model parameters
        for key, value in model_params.items():
            mlflow.log_param(key, value)

        # log the model with input example
        import mlflow.pyfunc as pyfunc
        from mlflow.pyfunc import PythonModel  # type: ignore

        # 5. Log Model with Signature, Input Example, and Custom Python Model Wrapper
        class CustomModelWrapper(PythonModel):
            def __init__(self, custom_model: entities.PredictiveModel):
                self.custom_model = custom_model

            def predict(
                self,
                context,
                model_input,
                params: typing.Dict[str, typing.Any] | None = None,
            ):
                return self.custom_model.predict(model_input)

        # Define the model signature
        from mlflow.models.signature import infer_signature

        # Log the custom model with metadata
        pyfunc.log_model(
            artifact_path="model",
            python_model=CustomModelWrapper(model),
            input_example=input_example,
            signature=infer_signature(
                input_example,
                output_example,
            ),
        )

        # Save the model as a pickle file
        with tempfile.TemporaryDirectory() as tmpdirname:
            self.__save_as_pickle(model, tmpdirname + "/model.pkl")
            mlflow.log_artifact(tmpdirname + "/model.pkl", artifact_path="Model")

    def __log_ml_model(
        self,
        input_example: pd.DataFrame,
        output_example: pd.DataFrame,
        model: entities.PredictiveModel,
        model_type: entities.ModelTypes,
    ) -> None:

        from mlflow.models import infer_signature

        if model_type == "sklearn":
            import mlflow.sklearn as mlflow_sklearn

            mlflow_sklearn.log_model(
                model,
                "model",
                input_example=input_example,
                signature=infer_signature(
                    input_example,
                    output_example,
                ),
            )

        elif model_type == "xgboost":
            import mlflow.xgboost as mlflow_xgboost

            mlflow_xgboost.log_model(
                model,
                "model",
                input_example=input_example,
                signature=infer_signature(
                    input_example,
                    output_example,
                ),
            )

        elif model_type == "lightgbm":
            import mlflow.lightgbm as mlflow_lightgbm

            mlflow_lightgbm.log_model(
                model,
                "model",
                input_example=input_example,
                signature=infer_signature(
                    input_example,
                    output_example,
                ),
            )

        elif model_type == "catboost":
            import mlflow.catboost as mlflow_catboost

            mlflow_catboost.log_model(
                model,
                "model",
                input_example=input_example,
                signature=infer_signature(
                    input_example,
                    output_example,
                ),
            )

        elif model_type == "tensorflow":
            import mlflow.tensorflow as mlflow_tensorflow

            mlflow_tensorflow.log_model(
                model,
                "model",
                input_example=input_example,
                signature=infer_signature(
                    input_example,
                    output_example,
                ),
            )

        elif model_type == "keras":
            import mlflow.keras as mlflow_keras

            mlflow_keras.log_model(
                model,
                "model",
                input_example=input_example,
                signature=infer_signature(
                    input_example,
                    output_example,
                ),
            )

        elif model_type == "pytorch":
            import mlflow.pytorch as mlflow_pytorch

            mlflow_pytorch.log_model(
                model,
                "model",
                input_example=input_example,
                signature=infer_signature(
                    input_example,
                    output_example,
                ),
            )

        elif model_type == "spark":
            import mlflow.spark as mlflow_spark

            mlflow_spark.log_model(
                model,
                "model",
                input_example=input_example,
                signature=infer_signature(
                    input_example,
                    output_example,
                ),
            )

        elif model_type == "fastai":
            import mlflow.fastai as mlflow_fastai  # type: ignore

            mlflow_fastai.log_model(
                model,
                "model",
                input_example=input_example,
                signature=infer_signature(
                    input_example,
                    output_example,
                ),
            )

        elif model_type == "statsmodels":
            import mlflow.statsmodels as mlflow_statsmodels

            mlflow_statsmodels.log_model(
                model,
                "model",
                input_example=input_example,
                signature=infer_signature(
                    input_example,
                    output_example,
                ),
            )

        elif model_type == "h2o":
            import mlflow.h2o as mlflow_h2o

            mlflow_h2o.log_model(
                model,
                "model",
                input_example=input_example,
                signature=infer_signature(
                    input_example,
                    output_example,
                ),
            )

        elif model_type == "onnx":
            import mlflow.onnx as mlflow_onnx

            mlflow_onnx.log_model(
                model,
                "model",
                input_example=input_example,
                signature=infer_signature(
                    input_example,
                    output_example,
                ),
            )

        elif model_type == "prophet":
            import mlflow.prophet as mlflow_prophet

            mlflow_prophet.log_model(
                model,
                "model",
                input_example=input_example,
                signature=infer_signature(
                    input_example,
                    output_example,
                ),
            )

        elif model_type == "spacy":
            import mlflow.spacy as mlflow_spacy

            mlflow_spacy.log_model(
                model,
                "model",
                input_example=input_example,
                signature=infer_signature(
                    input_example,
                    output_example,
                ),
            )

        elif model_type == "pmdarima":
            import mlflow.pmdarima as mlflow_pmdarima

            mlflow_pmdarima.log_model(
                model,
                "model",
                input_example=input_example,
                signature=infer_signature(
                    input_example,
                    output_example,
                ),
            )

        elif model_type == "diviner":
            import mlflow.diviner as mlflow_diviner

            mlflow_diviner.log_model(
                model,
                "model",
                input_example=input_example,
                signature=infer_signature(
                    input_example,
                    output_example,
                ),
            )

        else:
            raise ValueError(f"Model type {model_type} not supported")

    def __expression_to_dict(self, expression: str) -> dict[str, float]:
        import re

        # Remove spaces from the expression
        expression = expression.replace(" ", "")

        # Split the expression into terms using regex
        terms = re.split(r"(?=[+-])", expression)

        # Initialize an empty dictionary to store the result
        result = {}

        # Iterate over each term
        for term in terms:
            # Split the term into coefficient and variable
            match = re.match(r"([+-]?\d*\.?\d*)\*?(\w+)", term)
            if match:
                coefficient = match.group(1)
                variable = match.group(2)

                # Convert coefficient to float
                coefficient = float(coefficient) if coefficient else 1.0

                # Add to the dictionary
                result[variable] = coefficient

        return result

    def __get_model_type(self, model_type: str) -> entities.ModelTypes:
        model_type_parsed: entities.ModelTypes = (
            (
                json.loads(model_type)[0]
                .get("flavors", {})
                .get("python_function", {})
                .get("loader_module", "")
            )
            .replace("mlflow.", "")
            .replace(".model", "")
        )
        return model_type_parsed

    def __get_example_data_set(
        self, artifact_uri: str, example_type: typing.Literal["input", "output"]
    ) -> typing.Any:
        data_set_example = None
        data_set_name = (
            "input_example.csv" if example_type == "input" else "output_example.csv"
        )
        # Use the MinIO bucket configured (where artifacts live)
        bucket_name = configs.MinioConfigsCreds.MINIO_BUCKET.value
        data = self.artifact_repository.read_object(
            artifact_uri.replace(f"s3://{bucket_name}/", "") + f"/Data/{data_set_name}"
        )

        if data is None:
            raise ValueError(f"Data set {data_set_name} not found")

        if isinstance(data, bytes):
            data = data.decode("utf-8")

        with tempfile.TemporaryDirectory() as temp_dir:
            with open(os.path.join(temp_dir, data_set_name), "w") as f:
                f.write(data)
            data_set_example = pd.read_csv(os.path.join(temp_dir, data_set_name))

        return data_set_example

    def calculate_kpi(
        self,
        metrics: typing.Dict[str, typing.Any],
        objective_function: typing.Optional[typing.Dict[str, float]] = None,
        custom_objective_function: typing.Optional[
            typing.Callable[[typing.Dict[str, typing.Any]], float]
        ] = None,
    ) -> float:

        kpi = 0.0
        if custom_objective_function is None:

            if objective_function is None:
                raise ValueError(
                    "Objective function or custom objective function must be provided"
                )

            kpi = sum(
                list(value * metrics[key] for key, value in objective_function.items())
            )
            mlflow.set_tag(
                "objective_function",
                "kpi ~ "
                + " ".join(
                    [f"{value}*{key}" for key, value in objective_function.items()]
                ),
            )
        else:
            kpi = custom_objective_function(**metrics)  # type: ignore

        mlflow.log_metric("kpi", kpi)

        return kpi

    def load_run(self, run_id: str) -> entities.RunMetadata:
        run = mlflow.get_run(run_id)

        params = run.data.params
        del params["artifact_location"]
        del params["commit_hash"]

        run_metadata = entities.RunMetadata(
            run_id=run.info.run_id,
            run_name=run.info.run_name,
            metrics=run.data.metrics,
            kpi=run.data.metrics.get("kpi", 0.0),
            run_timestamp=run.info.start_time,
            run_duration=run.info.end_time - run.info.start_time,
            artifact_location=run.info.artifact_uri,
            input_example=self.__get_example_data_set(run.info.artifact_uri, "input"),
            output_example=self.__get_example_data_set(run.info.artifact_uri, "output"),
            source_code_path=run.data.tags.get("mlflow.source.name", None),
            commit_hash=run.data.tags.get("mlflow.source.git.commit", None),
            run_author=run.data.tags.get("mlflow.user", None),
            params=params,
            model_type=self.__get_model_type(
                run.data.tags.get("mlflow.log-model.history", "{}")
            ),
            objective_function=self.__expression_to_dict(
                run.data.tags.get("objective_function", "").replace("kpi ~ ", "")
            ),
        )

        return run_metadata

    def evaluate_model(
        self,
        model: entities.PredictiveModel,
        X_train: np.ndarray[typing.Any, typing.Any],
        y_train: np.ndarray[typing.Any, typing.Any],
        X_test: np.ndarray[typing.Any, typing.Any],
        y_test: np.ndarray[typing.Any, typing.Any],
    ) -> dict[str, dict[str, typing.Any]]:
        y_train_pred = model.predict(X_train)
        y_test_pred = model.predict(X_test)

        r2_train = r2_score(y_train, y_train_pred)
        r2_test = r2_score(y_test, y_test_pred)

        mae_train = mean_absolute_error(y_train, y_train_pred)
        mae_test = mean_absolute_error(y_test, y_test_pred)

        rmse_train = np.sqrt(mean_squared_error(y_train, y_train_pred))
        rmse_test = np.sqrt(mean_squared_error(y_test, y_test_pred))

        mse_train = mean_squared_error(y_train, y_train_pred)
        mse_test = mean_squared_error(y_test, y_test_pred)

        return {
            "r2": {"train": r2_train, "test": r2_test},
            "mae": {"train": mae_train, "test": mae_test},
            "rmse": {"train": rmse_train, "test": rmse_test},
            "mse": {"train": mse_train, "test": mse_test},
        }

    def start_experiment(self, experiment_name: str) -> None:
        experiment = mlflow.get_experiment_by_name(experiment_name)

        if experiment is None:
            print(f"Creating experiment: {experiment_name}")
            self.experiment_id = mlflow.create_experiment(
                experiment_name, artifact_location=self.artifact_location
            )
        else:
            self.experiment_id = experiment.experiment_id  # type: ignore

        mlflow.set_experiment(experiment_id=self.experiment_id)

    def execute_run(self, run: entities.Run) -> entities.RunEvaluation:
        mlflow.autolog(log_input_examples=True)

        with mlflow.start_run(
            run_name=run.run_name, experiment_id=self.experiment_id
        ) as mlflow_run:

            mlflow.log_param(
                "artifact_location",
                f"{configs.MinioConfigsCreds.MINIO_BROWSER_REDIRECT_URL.value}/browser/{configs.MlflowConfigsCreds.MLFLOW_ARTIFACTS_BUCKET_NAME.value}/mlartifacts%2F{mlflow_run.info.run_id}%2F",
            )
            data_artifacts = [] if run.data_artifacts is None else run.data_artifacts
            data_artifacts.append(
                entities.DataArtifact(
                    data=run.input_example, artifact_name="input_example"
                )
            )
            self.__log_data_artifacts(data_artifacts)
            mlflow.log_param("commit_hash", self.__get_current_commit_hash())

            metrics, model = run.evaluate(**run.params)  # type: ignore

            output_example = None
            try:
                output_example = model.predict(run.input_example)
                data_artifacts.append(
                    entities.DataArtifact(
                        data=output_example, artifact_name="output_example"
                    )
                )
            except Exception as e:
                print(f"Error using input example: {e}")

            if metrics is not None:
                for key, value in metrics.items():
                    if isinstance(value, pd.DataFrame):
                        self.__log_data_artifacts(
                            [entities.DataArtifact(data=value, artifact_name=key)]
                        )
                    if isinstance(value, list):
                        self.__log_data_artifacts(
                            [
                                entities.DataArtifact(
                                    data=pd.DataFrame(value), artifact_name=key
                                )
                            ]
                        )

                    try:
                        mlflow.log_metric(key, value)
                    except Exception as e:
                        print(f"Error logging metric {key}: {e}")

            kpi = self.calculate_kpi(
                objective_function=run.objective_function,
                custom_objective_function=run.custom_objective_function,
                metrics=metrics,
            )

            if run.model_type == "pyfunc":
                self.__log_custom_model(
                    input_example=run.input_example,
                    output_example=output_example,
                    model_params=run.params,
                    model=model,
                )
            else:
                self.__log_ml_model(
                    input_example=run.input_example,
                    output_example=output_example,
                    model=model,
                    model_type=run.model_type,
                )

            # actual source code file
            if run.source_code_path:
                with open(run.source_code_path, "r") as f:
                    code = f.read()
                    mlflow.log_text(code, run.source_code_path)

            return entities.RunEvaluation(
                run_id=mlflow_run.info.run_id,
                run_name=run.run_name,
                metrics=metrics,
                kpi=kpi,
            )


class MosquittoMQTTClientAdapter(ports.IMQTTClient):
    """A simple MQTT client adapter backed by Paho (Mosquitto).

    Parameters
    ----------
    client_id : str | None
        The client ID to be used for the connection, if no client ID is passed this will be generated.
    show_logs : bool
        If True, the client will print published messages to stdout.
    clean_session : bool
        ```txt
        - If True, the client will create a new session for each connection.
        - If False, the client will use the same session for each connection
        - Note: this will allow you to receive retained messages that were published while the client was disconnected using the same client ID.
        ```
    last_will_message : dict[str, typing.Any] | None
        The last will message to be sent when the client disconnects.
        `{ "topic": str, "payload": Any }`
        Note: this will only be sent if the client disconnects unexpectedly (without calling client.disconnect()).

    Example
    -------

    ```python
    import time
    import paho.mqtt.client as mqtt
    from modelOS_spec.infrastructure.adapters import MosquittoMQTTClientAdapter

    def cb(client, userdata, message: mqtt.MQTTMessage):
        print(
            f"[{message.topic}] {message.payload.decode()} @ {message.timestamp} with retain={message.retain} and qos={message.qos}"
        )

    client = MosquittoMQTTClientAdapter(
        client_id="my-test-client-id",
        show_logs=True,
        last_will_message=dict(topic="system/status", payload="offline")
    ).connect()

    client.subscribe_to_topic("test/topic", cb, qos=1)
    time.sleep(1)
    client.publish_data("test/topic", "Hello MQTT this is new", qos=1)

    time.sleep(5)
    client.unsubscribe_and_disconnect()
    """

    def __init__(
        self,
        client_id: str | None = None,
        transport: typing.Literal["tcp", "websockets"] = "tcp",
        keepalive: int = 60,
        show_logs: bool = True,
        clean_session: bool = False,
        last_will_message: dict[str, typing.Any] | None = None,
    ) -> None:
        self.broker = configs.MqttMosquittoConfigsCreds.MQTT_MOSQUITTO_BROKER.value
        self.port = int(
            configs.MqttMosquittoConfigsCreds.MQTT_MOSQUITTO_PORT.value or 1883
        )
        self.keepalive = keepalive
        self.show_logs = show_logs
        self.__clientID = self.__generate_clientID() if client_id is None else client_id
        # Paho client
        self.__client = mqtt.Client(
            client_id=self.__clientID,
            clean_session=clean_session,
            transport=transport,
        )
        self.__client.username_pw_set(
            configs.MqttMosquittoConfigsCreds.MQTT_MOSQUITTO_USERNAME.value,
            configs.MqttMosquittoConfigsCreds.MQTT_MOSQUITTO_PASSWORD.value,
        )
        if last_will_message is not None:
            self.__set_last_will_testament(
                topic=last_will_message["topic"],
                payload=last_will_message["payload"],
                qos=int(last_will_message.get("qos", 1)),
                retain=bool(last_will_message.get("retain", True)),
            )
        self.__topics_subscribed_to: list[str] = []

        # Default callbacks
        self.__client.on_connect = self.__on_connect

    # Properties
    @property
    def clientID(self) -> str:
        return self.__clientID

    @property
    def client(self) -> mqtt.Client:
        return self.__client

    @property
    def topics_subscribed_to(self) -> list[str]:
        return self.__topics_subscribed_to

    # Private helpers
    def __generate_clientID(self, length: int = 8) -> str:
        import random, string

        return "".join(random.choices(string.ascii_uppercase, k=length))

    def __set_last_will_testament(
        self,
        topic: str,
        payload: typing.Any,
        qos: int = 1,
        retain: bool = True,
    ) -> None:
        if isinstance(payload, dict):
            payload = json.dumps(payload)
        if isinstance(payload, str):
            payload = payload.encode("utf-8")
        elif not isinstance(payload, (bytes, bytearray)):
            payload = str(payload).encode("utf-8")

        self.__client.will_set(topic=topic, payload=payload, qos=qos, retain=retain)
        if self.show_logs:
            print("Setting LWT for topic:", topic)

    def __on_connect(self, client: mqtt.Client, userdata, flags, rc):
        if self.show_logs:
            print(f"Connected with reason code {rc} (clientID={self.clientID})")

    def connect(self) -> "MosquittoMQTTClientAdapter":
        try:
            self.__client.connect(self.broker, self.port, self.keepalive)
            self.__client.loop_start()
            if self.show_logs:
                print("Connected to broker.", self.broker, self.port)
        except Exception as e:
            print(f"Connection failed: {e}")
            raise
        return self

    def unsubscribe_from_topic(self, topic: str) -> list[str]:
        if topic in self.__topics_subscribed_to:
            try:
                self.__client.message_callback_remove(topic)
            except Exception:
                pass
            self.__client.unsubscribe(topic)
            self.__topics_subscribed_to.remove(topic)
            if self.show_logs:
                print("Unsubscribed from topic:", topic)
        return self.__topics_subscribed_to

    def unsubscribe_and_disconnect(self) -> None:
        # Unsubscribe from all topics
        for topic in list(self.__topics_subscribed_to):
            self.unsubscribe_from_topic(topic)
        # Stop loop and disconnect
        try:
            self.__client.loop_stop()
        finally:
            self.__client.disconnect()
        if self.show_logs:
            print("Disconnected from broker. (clientID=", self.clientID, ")")

    def publish_data(
        self,
        topic: str,
        payload: typing.Any,
        qos: typing.Optional[int] = schema.QualityofService.AT_MOST_ONCE.value,
        retain: bool = False,
    ) -> bool:
        if isinstance(payload, dict):
            payload = json.dumps(payload)
        if isinstance(payload, str):
            payload = payload.encode("utf-8")
        elif not isinstance(payload, (bytes, bytearray)):
            payload = str(payload).encode("utf-8")

        if self.show_logs:
            try_preview = payload.decode("utf-8")
        else:
            try_preview = None

        result = self.__client.publish(topic, payload, qos=qos, retain=retain)
        if result.rc != mqtt.MQTT_ERR_SUCCESS:
            print(f"Publish failed: {result.rc}")
            return False
        if self.show_logs:
            print(
                "publish", topic, try_preview if try_preview is not None else "<bytes>"
            )
        return True

    def subscribe_to_topic(
        self,
        topic: str,
        custom_callback: typing.Callable[[mqtt.Client, typing.Any, typing.Any], None],
        qos: typing.Optional[int] = 1,
    ) -> bool:
        """Subscribe and attach a callback per-topic.

        custom_callback signature:
            def cb(client, userdata, message_dict): ...
        where message_dict = {topic, payload: bytes, qos, retain, timestamp}
        """
        if self.show_logs:
            print("subscribe", topic)

        def _paho_handler(client: mqtt.Client, userdata, msg: mqtt.MQTTMessage):
            try:
                custom_callback(client, userdata, msg)
            except Exception as e:
                print(f"Error in custom callback for topic '{topic}': {e}")

        res = self.__client.subscribe(topic, qos)
        if res[0] != mqtt.MQTT_ERR_SUCCESS:
            print(f"Subscribe failed: {res[0]}")
            return False

        self.__client.message_callback_add(topic, _paho_handler)
        self.__topics_subscribed_to.append(topic)
        return True
