from __future__ import annotations
from datetime import timedelta
import time
import typing
import time
import os
import re
import subprocess
from pathlib import Path
from devOS.infrastructure.clients.ticktick_client import (
    TickTickClient,
    TickTickTask,
    TickTickTaskList,
)
from git import Repo, InvalidGitRepositoryError
from devOS.infrastructure.configs import TickTickCreds, GitHubAPICreds
from devOS.use_cases.utils.dynamic_array import array
import requests  # type: ignore
from devOS.use_cases.utils.file_io import File
from devOS.domain import entities
from devOS.use_cases.use_cases import OSInterface

_TIME_UNITS = {
    "week": "weeks",
    "weeks": "weeks",
    "day": "days",
    "days": "days",
    "hour": "hours",
    "hours": "hours",
    "minute": "minutes",
    "minutes": "minutes",
    "second": "seconds",
    "seconds": "seconds",
    "millisecond": "milliseconds",
    "milliseconds": "milliseconds",
    "microsecond": "microseconds",
    "microseconds": "microseconds",
}


def _parse_schedule_args(args: typing.Sequence[str]) -> timedelta:
    if len(args) % 2 != 0:
        raise ValueError("Schedule must be provided in number/unit pairs.")

    schedule_kwargs: dict[str, int] = {}
    for index in range(0, len(args), 2):
        value = args[index]
        unit = args[index + 1].lower()
        normalized_unit = _TIME_UNITS.get(unit)
        if normalized_unit is None:
            raise ValueError(f"Unsupported schedule unit: {unit}.")

        try:
            amount = int(value)
        except ValueError as exc:
            raise ValueError(f"Invalid schedule value: {value}.") from exc

        schedule_kwargs[normalized_unit] = (
            schedule_kwargs.get(normalized_unit, 0) + amount
        )

    schedule = timedelta(**schedule_kwargs)
    if schedule.total_seconds() <= 0:
        raise ValueError("Schedule must be greater than zero.")

    return schedule


def _slugify(text: str) -> str:
    slug = text.lower().strip()
    slug = re.sub(r"\[.*?\]", "", slug)
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    slug = slug.strip("-")[:30]  # Limit characters to keep branch names small
    return slug or "task"


class RunAgentsUseCase(OSInterface):
    def __init__(
        self,
        ticktick_client: TickTickClient | None = None,
    ):
        super().__init__(os.getcwd())
        self.ticktick_client = ticktick_client or TickTickClient(
            access_token=TickTickCreds.ACCESS_TOKEN.value
        )

    def __get_repo_name(self):
        try:
            repo = Repo(os.getcwd(), search_parent_directories=True)
            return os.path.basename(repo.working_tree_dir)
        except InvalidGitRepositoryError:
            return ""

    def __get_base_branch(self) -> str:
        try:
            repo = Repo(os.getcwd(), search_parent_directories=True)
            return repo.active_branch.name
        except InvalidGitRepositoryError:
            return "master"

    def __complete_task_in_ticktick(self, task_title: str) -> None:
        work_tasks = (
            array(
                self.ticktick_client.get_tasks_from_task_list(
                    TickTickTaskList.WORK.value
                )
            )
            .validate(TickTickTask)
            .map(lambda t: t.title)
            .build()
        )
        side_work_tasks = (
            array(
                self.ticktick_client.get_tasks_from_task_list(
                    TickTickTaskList.SIDE_PROJECTS.value
                )
            )
            .validate(TickTickTask)
            .map(lambda t: t.title)
            .build()
        )
        if task_title in work_tasks:
            self.ticktick_client.complete_task(TickTickTaskList.WORK.value, task_title)
        elif task_title in side_work_tasks:
            self.ticktick_client.complete_task(
                TickTickTaskList.SIDE_PROJECTS.value, task_title
            )
        else:
            self.log_message(
                f"Task '{task_title}' not found in TickTick lists.", error=True
            )

    def get_ticktick_tasks(self, repo_name: str) -> list[tuple[str, str]]:
        work_tasks = self.ticktick_client.get_tasks_from_task_list(
            TickTickTaskList.WORK.value
        )
        side_work_tasks = self.ticktick_client.get_tasks_from_task_list(
            TickTickTaskList.SIDE_PROJECTS.value
        )
        tasks = work_tasks + side_work_tasks
        if len(tasks) == 0:
            return []
        relevant_tasks = []
        for task in tasks:
            if task.tags is None:
                continue
            else:
                if repo_name.lower() in task.tags[0].lower():
                    relevant_tasks.append((task.title, task.content or ""))

        if len(relevant_tasks) == 0:
            self.log_message(
                f"No tasks found in TickTick for repo: {repo_name}", error=True
            )
        return relevant_tasks

    def launch_codex_agent(self, title: str, prompt: str) -> None:
        owner = GitHubAPICreds.USERNAME.value
        repo = self.__get_repo_name()
        env_id = f"{owner}/{repo}"
        full_prompt = f"{title}\n\n{prompt}\n"

        cmd = ["npx", "codex", "cloud", "exec", "--env", env_id, "-"]

        import subprocess

        self.log_message(" ".join(cmd), is_command=True)
        self.log_message(full_prompt)
        subprocess.run(
            cmd,
            input=full_prompt.encode("utf-8", errors="strict"),
            check=False,
        )

    def launch_github_copilot_agent(self, title: str, prompt: str, base_branch: str):
        owner = GitHubAPICreds.USERNAME.value
        repo = self.__get_repo_name()
        token = GitHubAPICreds.GITHUB_TOKEN.value
        url = f"https://api.github.com/repos/{owner}/{repo}/issues"
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "Authorization": f"Bearer {token}",
        }

        payload = {
            "title": title,
            "body": prompt,
            "assignees": ["copilot-swe-agent[bot]"],
            "agent_assignment": {
                "target_repo": f"{owner}/{repo}",
                "base_branch": base_branch,
                "custom_instructions": "Follow AGENTS.md.",
            },
        }

        response = requests.post(url, headers=headers, json=payload)
        data = response.json()
        print("Response Status:", response.status_code)
        print("Response Data:", data)

    def __create_worktree(self, branch_name: str) -> Path:
        """Create a git worktree on a new branch and return its path.

        The worktree is placed under a ``-worktrees`` sibling directory next to
        the repository root so that it doesn't interfere with the main tree.

        Parameters
        ----------
        branch_name : str
            Name of the new branch to create inside the worktree.

        Returns
        -------
        Path
            Absolute path to the created worktree directory.
        """
        repo = Repo(os.getcwd(), search_parent_directories=True)
        repo_root = Path(repo.working_tree_dir)  # type: ignore[arg-type]
        worktree_base = repo_root.parent / f"{repo_root.name}-worktrees"
        worktree_path = worktree_base / branch_name

        if worktree_path.exists():
            self.log_message(f"Worktree already exists at {worktree_path}, reusing it.")
            return worktree_path

        worktree_base.mkdir(parents=True, exist_ok=True)
        self.log_message(
            f"Creating worktree at {worktree_path} on branch {branch_name}"
        )
        subprocess.run(
            ["git", "worktree", "add", "-b", branch_name, str(worktree_path)],
            cwd=str(repo_root),
            check=True,
        )
        return worktree_path

    def launch_local_agent(self, title: str, prompt: str) -> None:
        """Run a Codex agent locally in headless mode inside a fresh worktree.

        This creates a git worktree so the agent operates on an isolated copy
        of the repository, then invokes ``codex --full-auto`` so it runs
        entirely without user interaction.

        Parameters
        ----------
        title : str
            Task title used to derive the worktree branch name.
        prompt : str
            Prompt body passed to the Codex agent via stdin.
        """
        branch_name = f"agent/{_slugify(title)}"
        worktree_path = self.__create_worktree(branch_name)

        full_prompt = f"{title}\n\n{prompt}\n"
        cmd = ["npx", "codex", "--full-auto", "exec", "-"]

        self.log_message(f"Running local agent in {worktree_path}")
        self.log_message(" ".join(cmd), is_command=True)
        self.log_message(full_prompt)

        subprocess.run(
            cmd,
            cwd=str(worktree_path),
            input=full_prompt.encode("utf-8", errors="strict"),
            check=False,
            shell=True,
        )
        self.log_message(
            f"Local agent finished. Review changes in {worktree_path} "
            f"(branch: {branch_name})."
        )

    def merge_worktree_to_main(self, worktree_name: str) -> None:
        """Merge a worktree branch back to main and clean up the worktree.

        Parameters
        ----------
        worktree_name : str
            Name of the worktree branch to merge (e.g., "agent/add-user-auth").
        """
        repo = Repo(os.getcwd(), search_parent_directories=True)
        repo_root = Path(repo.working_tree_dir)  # type: ignore[arg-type]
        worktree_base = repo_root.parent / f"{repo_root.name}-worktrees"
        worktree_path = worktree_base / worktree_name

        if not worktree_path.exists():
            self.log_message(
                f"Worktree '{worktree_name}' not found at {worktree_path}.",
                error=True,
            )
            return

        self.log_message(f"Committing any changes in worktree {worktree_path}")
        subprocess.run(
            ["git", "add", "-A"],
            cwd=str(worktree_path),
            check=True,
        )

        commit_result = subprocess.run(
            ["git", "commit", "-m", f"Agent work: {worktree_name}"],
            cwd=str(worktree_path),
            capture_output=True,
            text=True,
        )

        if "nothing to commit" not in commit_result.stdout:
            self.log_message(f"Committed changes in worktree")
        else:
            self.log_message(f"No changes to commit in worktree")

        base_branch = self.__get_base_branch()
        self.log_message(
            f"Merging worktree branch '{worktree_name}' to '{base_branch}'"
        )

        subprocess.run(
            ["git", "checkout", base_branch],
            cwd=str(repo_root),
            check=True,
        )
        self.log_message(f"Checked out {base_branch}")

        merge_result = subprocess.run(
            ["git", "merge", worktree_name, "--no-ff", "-m", f"Merge {worktree_name}"],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
        )

        if merge_result.returncode == 0:
            self.log_message(f"Successfully merged {worktree_name} into {base_branch}")
        else:
            self.log_message(f"Merge failed: {merge_result.stderr}", error=True)
            return

        subprocess.run(
            ["git", "worktree", "remove", "--force", str(worktree_path)],
            cwd=str(repo_root),
            check=True,
        )
        self.log_message(f"Removed worktree at {worktree_path}")

        subprocess.run(
            ["git", "branch", "-d", worktree_name],
            cwd=str(repo_root),
            check=False,
        )
        self.log_message(f"Deleted branch {worktree_name}")

    def run_on_schedule(
        self,
        schedule: timedelta,
        callback: typing.Callable[..., None] | None = None,
    ) -> None:
        """Run the agent execution loop on the provided schedule."""
        callback_to_run = self.execute if callback is None else callback
        while True:
            callback_to_run()
            time.sleep(schedule.total_seconds())

    def run_every(self, *args: str) -> None:
        """Run the agent execution loop on a parsed schedule."""
        schedule = _parse_schedule_args(args)
        self.run_on_schedule(schedule)

    def watch(self, watch_list: str, every_key: str, *args: str) -> None:
        """Run the agent execution loop for all the projects in the watch list.

        Parameters
        ----------
        watch_list : str
            List of project tag names to watch. (comma-separated list)
            For example: "project1,project2,project3"
        *args : str
            Schedule arguments in number/unit pairs.
            for example: "1 hour", "30 minutes"

        Example
        -------
        dev agents watch project1,project2 every 1 hour
        """

        def watch_callback():
            for project_tag in watch_list.split(","):
                project_tag = project_tag.strip()
                if not project_tag:
                    continue
                for task_title, task_content in self.get_ticktick_tasks(project_tag):
                    if task_title is None or task_content is None:
                        print(f"No task found for: {project_tag}")
                        return

                    prompt = task_content.strip()
                    if "[codex-local]" in task_title:
                        self.log_message(
                            f"Launching local agent for task: {task_title}"
                        )
                        self.launch_local_agent(task_title, prompt)
                        self.log_message("Setting the task as completed in TickTick.")
                        self.__complete_task_in_ticktick(task_title)

                    elif "[codex]" in task_title:
                        self.log_message(
                            f"Launching Codex agent for task: {task_title}"
                        )
                        self.launch_codex_agent(task_title, prompt)
                        self.log_message("Setting the task as completed in TickTick.")
                        self.__complete_task_in_ticktick(task_title)

                    elif "[gh-copilot]" in task_title:
                        base_branch = self.__get_base_branch()
                        self.log_message(
                            f"Launching GitHub Copilot agent on branch {base_branch}"
                        )
                        self.log_message(f"Task: {task_title}")
                        self.launch_github_copilot_agent(
                            task_title, prompt, base_branch=base_branch
                        )
                        self.log_message("Setting the task as completed in TickTick.")
                        self.__complete_task_in_ticktick(task_title)

                    else:
                        self.log_message(
                            f"Skipping task '{task_title}' as it does not specify a valid agent.",
                            error=True,
                        )

        schedule = _parse_schedule_args(args)
        self.run_on_schedule(schedule, watch_callback)

    def execute(self, repo_to_execute: str | None = None) -> None:
        """Execute the agent tasks now.

        Parameters
        ----------
        repo_to_execute : str
            Name of the repository to get tasks for.

        Example
        -------
        dev agents run now
        dev agents run now my-repo
        """
        repo_name = (
            self.__get_repo_name() if repo_to_execute is None else repo_to_execute
        )

        for task_title, task_content in self.get_ticktick_tasks(repo_name):
            if task_title is None or task_content is None:
                print(f"No task found for: {repo_name}")
                return

            prompt = task_content.strip()
            if "[codex-local]" in task_title:
                self.log_message(f"Launching local agent for task: {task_title}")
                self.launch_local_agent(task_title, prompt)
                self.log_message("Setting the task as completed in TickTick.")
                self.__complete_task_in_ticktick(task_title)

            elif "[codex]" in task_title:
                self.log_message(f"Launching Codex agent for task: {task_title}")
                self.launch_codex_agent(task_title, prompt)
                self.log_message("Setting the task as completed in TickTick.")
                self.__complete_task_in_ticktick(task_title)

            elif "[gh-copilot]" in task_title:
                base_branch = self.__get_base_branch()
                self.log_message(
                    f"Launching GitHub Copilot agent on branch {base_branch}"
                )
                self.log_message(f"Task: {task_title}")
                self.launch_github_copilot_agent(
                    task_title, prompt, base_branch=base_branch
                )
                self.log_message("Setting the task as completed in TickTick.")
                self.__complete_task_in_ticktick(task_title)

            else:
                self.log_message(
                    f"Skipping task '{task_title}' as it does not specify a valid agent.",
                    error=True,
                )


def main():
    use_case = RunAgentsUseCase()
    use_case.execute()


if __name__ == "__main__":
    main()
