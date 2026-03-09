import typing
import requests  # type: ignore
import enum
import pydantic
from datetime import timedelta
from dateutil import parser  # type: ignore
import json

# API documentation https://developer.ticktick.com/docs#/openapi


class TickTickPriority(enum.Enum):
    NO_PRIORITY = 0
    LOW_PRIORITY = 1
    MEDIUM_PRIORITY = 3
    HIGH_PRIORITY = 5


ticktick_priority = {
    0: "No Priority",
    1: "Low Priority",
    3: "Medium Priority",
    5: "High Priority",
}


class TickTickSubtask(pydantic.BaseModel):
    id: str
    status: int  # 0 for todo and 1 for completed
    title: str
    sortOrder: int
    isAllDay: bool
    timeZone: str


class TickTickTask(pydantic.BaseModel):
    id: str
    projectId: str
    sortOrder: int
    title: str
    desc: typing.Optional[str] = None
    content: typing.Optional[str] = None
    startDate: typing.Optional[str] = None
    dueDate: typing.Optional[str] = None
    timeZone: str
    isAllDay: bool
    status: int
    priority: int
    items: typing.Optional[typing.List[TickTickSubtask]] = None
    tags: typing.Optional[typing.List[str]] = None
    columnId: typing.Optional[str] = None


class TickTickProject(pydantic.BaseModel):
    id: str
    name: str
    sortOrder: int
    viewMode: typing.Literal["kanban", "list"]
    kind: typing.Literal["TASK", "NOTE"]
    permissions: typing.Literal["write"] | None = None


class TickTickColumn(pydantic.BaseModel):
    id: str
    projectId: str
    name: str
    sortOrder: int


class TickTickTaskList(enum.Enum):
    SIDE_PROJECTS = "🛣️Side Projects"
    WORK = "Work"
    AUTOMATION = "🤖 Automation"
    ACTIVITIES = "♻Activities"
    INBOX = "Inbox"


class TickTickProjectData(pydantic.BaseModel):
    project: typing.Optional[TickTickProject]
    tasks: typing.List[TickTickTask]
    columns: typing.List[TickTickColumn]


def load_access_token():
    from devOS.infrastructure.configs import TickTickCreds

    return TickTickCreds.ACCESS_TOKEN.value


class TickTickClient:
    def __init__(self, access_token: None | str = None):
        self.access_token = access_token if access_token else load_access_token()

    def __get_headers(self) -> typing.Mapping[str, str | bytes] | None:
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.access_token}",
        }

    def get_project_id(self, task_list_title: str) -> typing.Optional[typing.Any]:
        """
        Retrieve the project ID from the name of the task list.

        ## Parameters
        task_list_title: str
            The name of the task list.

        ## Returns
        The ID of the project, or None if the project is not found.

        ## Example
        ```python
        from automation_engine.apis.ticktick_api import get_project_id, TaskList

        project_id = get_project_id("PhD Tasks")
        print(project_id)
        ```
        """
        if task_list_title == TickTickTaskList.INBOX.value:
            return "inbox"

        url = "https://ticktick.com/open/v1/project"

        response = requests.get(url, headers=self.__get_headers())
        if response.status_code != 200:
            print(
                f"Failed to retrieve projects. Status code: {response.status_code}, Response: {response.text}"
            )
            return None

        # print(
        #     f"Get Project ID Response from Project name {task_list_title}: {response.json()}"
        # )
        return list(
            filter(lambda project: project["name"] == task_list_title, response.json())
        )[0]["id"]

    def get_task_list_columns(self) -> typing.Dict[str, typing.Dict[str, str]]:
        """
        Retrieve the column IDs for each task list using the TickTick API.

        Returns
        -------
        Dict[str, Dict[str, str]]
            A dictionary mapping each project (task list) ID to a dictionary of column names and their IDs.
        Example output:
        ```python
        {
            '🤖 automation_engine':
                {
                    '68356a634d009641398c38d4': 'Completed',
                    '68356a5e4d009641398c38cf': 'Under Review',
                    '68356a5a4d009641398c38ca': 'In Progress',
                    '68356a564d009641398c38c4': 'TODO',
                    'projectId': '6834beee75dd7800000001a7'
                },
            'PhD Tasks 📚; : {...},
            ...
        }
        ```
        """
        url = "https://ticktick.com/open/v1/project"
        headers = self.__get_headers()
        if headers is None:
            print("Authorization header is missing. Please authenticate first.")
            return {}

        response = requests.get(url, headers=headers)
        if response.status_code != 200:
            print(
                f"Failed to retrieve projects. Status code: {response.status_code}, Response: {response.text}"
            )
            return {}

        projects = response.json()
        columns_by_project = {}

        for project in projects:
            validated_project = TickTickProject(**project)
            project_id = validated_project.id
            project_name = validated_project.name

            # Fetch columns for this project
            project_data_url = f"https://ticktick.com/open/v1/project/{project_id}/data"
            project_data_resp = requests.get(project_data_url, headers=headers)
            if project_data_resp.status_code != 200:
                print(
                    f"Failed to retrieve columns for project {project_name}. Status code: {project_data_resp.status_code}"
                )
                continue
            project_data = project_data_resp.json()  #
            validated_project_data = TickTickProjectData(**project_data)
            columns = validated_project_data.columns
            columns_by_project[project_name] = {col.id: col.name for col in columns}
            columns_by_project[project_name]["projectId"] = project_id

        # Add the inbox task list
        columns_by_project["Inbox"] = {}
        project_data_url = f"https://ticktick.com/open/v1/project/inbox/data"
        project_data_resp = requests.get(project_data_url, headers=headers)
        if project_data_resp.status_code != 200:
            print(
                f"Failed to retrieve columns for project 'Inbox'. Status code: {project_data_resp.status_code}"
            )
            return columns_by_project
        inbox_project_data: dict[str, typing.Any] = project_data_resp.json()
        validated_project_data = TickTickProjectData(
            project=inbox_project_data.get("project", None),
            tasks=inbox_project_data.get("tasks", []),
            columns=inbox_project_data.get("columns", []),
        )
        columns = validated_project_data.columns
        columns_by_project["Inbox"] = {col.id: col.name for col in columns}
        columns_by_project["Inbox"]["projectId"] = "inbox"

        return columns_by_project

    def create_task(
        self,
        task_title: str,
        task_list_title: str,
        content: typing.Optional[str] = None,
        tags: typing.List[str] = list(),
        isAllDay: typing.Optional[bool] = None,
        subtasks: typing.Optional[typing.List[str]] = None,
        priority: typing.Optional[int] = None,
        start_date: typing.Optional[str] = None,
        due_date: typing.Optional[str] = None,
    ):
        """
        Create a task in the specified list.

        ## Parameters
        task_title: str
        The task to create.
        task_list_title: str
            The title of the task list to create the task in. (use TickTickTaskList enum)
        priority: typing.Optional[int]
            Task priority Value = None : 0, Low:1, Medium:3, High:5
        start_date: typing.Optional[str]
            Start date time in "yyyy-MM-dd'T'HH:mm:ssZ" Example : "2019-11-13T03:00:00+0000"
        time_zone: typing.Optional[str]
            Task timezone Example : "America/Los_Angeles"
        due_date: typing.Optional[str]
            Task due date time in "yyyy-MM-dd'T'HH:mm:ssZ" Example : "2019-11-13T03:00:00+0000"

        ## Example
        ```python
        from automation_engine.apis.ticktick_api import create_task, TaskList

        create_task(
            "Get Groceries",
            "PhD Tasks",
            startDate="2022-01-01T03:00:00+0000",
            timeZone="America/Los_Angeles",
            dueDate="2022-01-02T03:00:00+0000"
        )

        # Output
        ```
        """

        url = "https://ticktick.com/open/v1/task"  # Replace with the actual API URL

        if subtasks is None:
            subtasks = ["Subtask"]

        # Construct the body of the request
        payload = {
            "title": task_title,
            "projectId": self.get_project_id(task_list_title),
            "isAllDay": isAllDay if isAllDay is not None else True,
            "desc": content,
            "content": content,
            "items": [dict(title=subtask) for subtask in subtasks],
            "timeZone": "UTC",
            "tags": tags,
            "priority": priority,
        }

        if start_date:
            payload["startDate"] = start_date

        if due_date:
            # Add one day to the due date
            new_due_date = parser.parse(due_date) + timedelta(days=1)

            payload["dueDate"] = new_due_date.strftime("%Y-%m-%dT%H:%M:%S.%f+0000")

        # Send the request
        response = requests.post(url, json=payload, headers=self.__get_headers())

        # Check if the request was successful
        if response.status_code == 200:
            print("Task created successfully")
            return (
                response.json()
            )  # or `response.text` if the response is not in JSON format
        else:
            print(
                f"Failed to create task. Status code: {response.status_code}, Response: {response.text}"
            )
            return None

    def get_tasks_from_task_list(self, task_list: str) -> typing.List[TickTickTask]:
        """
        Get all tasks from a task_list.

        ## Parameters
        task_list: The name of the task list to retrieve tasks from. Use TickTickTaskList enum.

        ## Returns
        List[TickTickTaskDetails]
        The tasks in the task_list.

        ## Example
        ```python
        from automation_engine.apis.ticktick_api import get_tasks_from_task_list

        tasks = get_tasks_from_task_list("PhD Tasks 📚")
        print(tasks)
        ```
        """
        project_id = self.get_project_id(task_list)
        url = f"https://ticktick.com/open/v1/project/{project_id}/data"

        response = requests.get(url, headers=self.__get_headers())

        if response.status_code != 200:
            print(
                f"Failed to retrieve tasks. Status code: {response.status_code}, Response: {response.text}"
            )
            return []

        return [TickTickTask(**task) for task in response.json().get("tasks")]

    def get_completed_tasks_from_task_list(
        self, task_list: str
    ) -> typing.List[TickTickTask]:
        """
        Get all completed tasks from a task_list.

        ## Parameters
        task_list: The name of the task list to retrieve tasks from. Use TickTickTaskList enum.

        ## Returns
        List[TickTickTaskDetails]
        The completed tasks in the task_list.

        ## Example
        ```python
        from automation_engine.apis.ticktick_api import get_completed_tasks_from_task_list

        tasks = get_completed_tasks_from_task_list("PhD Tasks 📚")
        print(tasks)
        ```
        """
        project_id = self.get_project_id(task_list)
        url = f"https://ticktick.com/open/v1/project/{project_id}/data?status=completed"

        response = requests.get(url, headers=self.__get_headers())

        if response.status_code != 200:
            print(
                f"Failed to retrieve tasks. Status code: {response.status_code}, Response: {response.text}"
            )
            return []

        return [TickTickTask(**task) for task in response.json().get("tasks")]

    def complete_task(self, task_list: str, task_title: str):
        """
        Mark a task as completed.

        ## Parameters
        task_list:
        task_title: str
            The title of the task to mark as completed.

        ## Example
        ```python
        from automation_engine.apis.ticktick_api import complete_task

        complete_task("PhD Tasks 📚", "Get Groceries")
        ```
        """
        task_id = list(
            filter(
                lambda task: task.title == task_title,
                self.get_tasks_from_task_list(task_list),
            )
        )[0].id
        project_id = self.get_project_id(task_list)

        print(f"Completing task '{task_title}' with ID '{task_id}' in project {task_list} with ID '{project_id}'")
        url = f"https://api.ticktick.com/open/v1/project/{project_id}/task/{task_id}/complete"

        response = requests.post(url, headers=self.__get_headers())

        if response.status_code == 200:
            print("Task completed successfully")
        else:
            print(
                f"Failed to complete task. Status code: {response.status_code}, Response: {response.text}"
            )

    def complete_task_by_id(self, project_id: str, task_id: str):
        """
        Mark a task as completed.

        ## Parameters
        project_id: str
            The ID of the project containing the task to mark as completed.
        task_id: str
            The ID of the task to mark as completed.

        ## Example
        ```python
        from automation_engine.apis.ticktick_api import complete_task_by_id

        complete_task_by_id("PhD Tasks 📚", "Get Groceries")
        ```
        """

        url = (
            f"https://ticktick.com/open/v1/project/{project_id}/task/{task_id}/complete"
        )

        response = requests.post(url, headers=self.__get_headers())

        if response.status_code == 200:
            print("Task completed successfully")
        else:
            print(
                f"Failed to complete task. Status code: {response.status_code}, Response: {response.text}"
            )

    def update_task_tag(
        self, task_list: str, task_title: str, new_tags: typing.List[str]
    ):
        """
        Add a tag to a task.

        ## Parameters
        task_list: str
        task_title: str
            The title of the task to add the tag to.
        new_tags: List[str]
            The tags to add to the task.

        ## Example
        ```python
        from automation_engine.apis.ticktick_api import add_tag_to_task

        add_tag_to_task("PhD Tasks 📚", "Get Groceries", "phd")
        ```
        """
        old_task = list(
            filter(
                lambda item: item.title == task_title,
                self.get_tasks_from_task_list(task_list),
            )
        )[0]
        self.delete_task(task_list, task_title)

        try:
            self.create_task(
                task_title=task_title,
                task_list_title=task_list,
                tags=old_task.tags + new_tags if old_task.tags else new_tags,
                content=old_task.content or old_task.desc or "",
                subtasks=[subtask.title for subtask in old_task.items or []],
                priority=old_task.priority,
                isAllDay=old_task.isAllDay,
                due_date=(old_task.dueDate if old_task.dueDate else None),
            )

        except Exception as e:
            print(f"Failed to update task. Error: {e}")
            with (
                open("failed_task.json", "w") as write,
                open("failed_task.json", "r") as read,
            ):
                if read.read():
                    failed_tasks = json.loads(read.read()).get("failed tasks", [])
                else:
                    failed_tasks = []
                failed_tasks.append(old_task.dict())
                write.write(json.dumps({"failed tasks": failed_tasks}))

    def update_task_content(self, task_list: str, task_title: str, new_content: str):
        """
        Update the content of a task.

        ## Parameters
        task_list: str
        task_title: str
            The title of the task to update.
        new_content: str
            The new content of the task.

        ## Example
        ```python
        from automation_engine.apis.ticktick_api import update_task_content

        update_task_content("PhD Tasks 📚", "Get Groceries", "Buy groceries for the week")
        ```
        """
        old_task = list(
            filter(
                lambda item: item.title == task_title,
                self.get_tasks_from_task_list(task_list),
            )
        )[0]
        self.delete_task(task_list, task_title)

        try:
            self.create_task(
                task_title=task_title,
                task_list_title=task_list,
                tags=old_task.tags or [],
                content=new_content,
                subtasks=[subtask.title for subtask in old_task.items or []],
                priority=old_task.priority,
                isAllDay=old_task.isAllDay,
                due_date=(old_task.dueDate if old_task.dueDate else None),
            )
        except Exception as e:
            print(f"Failed to update task. Error: {e}")
            with (
                open("failed_task.json", "w") as write,
                open("failed_task.json", "r") as read,
            ):
                if read.read():
                    failed_tasks = json.loads(read.read()).get("failed tasks", [])
                else:
                    failed_tasks = []
                failed_tasks.append(old_task.dict())
                write.write(json.dumps({"failed tasks": failed_tasks}))

    def delete_task(self, task_list: str, task_title: str):
        """
        Delete a task.

        ## Parameters
        task_list: str
        task_title: str
            The title of the task to delete.

        ## Example
        ```python
        from automation_engine.apis.ticktick_api import delete_task

        delete_task("PhD Tasks 📚", "Get Groceries")
        ```
        """
        task_id = list(
            filter(
                lambda task: task.title == task_title,
                self.get_tasks_from_task_list(task_list),
            )
        )[0].id
        project_id = self.get_project_id(task_list)

        url = f"https://ticktick.com/open/v1/project/{project_id}/task/{task_id}"

        response = requests.delete(url, headers=self.__get_headers())

        if response.status_code == 200:
            print("Task deleted successfully")
        else:
            print(
                f"Failed to delete task. Status code: {response.status_code}, Response: {response.text}"
            )


def main():
    from devOS.infrastructure.configs import TickTickCreds

    client = TickTickClient(access_token=TickTickCreds.ACCESS_TOKEN.value)

    columns = client.get_task_list_columns()
    print(columns)


if __name__ == "__main__":
    main()
