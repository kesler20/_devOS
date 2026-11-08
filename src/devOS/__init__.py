import inspect
import sys
import typing

CommandLeaf = typing.Callable[..., object]
CommandNode: typing.TypeAlias = dict[str, "CommandNode | CommandLeaf"]

SENSITIVE_FUNCTION_NAMES = {"set_credential", "set_global_secret"}


def print_message(*args):
    if "--debug" in sys.argv or "--explain" in sys.argv or "--help" in sys.argv:
        print(*args)


def print_error(*args):
    print(*args, file=sys.stderr)


def execute_function(leaf_node: CommandLeaf, *args):
    print_message("executing function:", leaf_node)
    arguments_are_sensitive = leaf_node.__name__ in SENSITIVE_FUNCTION_NAMES
    displayed_arguments = "[redacted]" if arguments_are_sensitive else args
    print_message("with args:", displayed_arguments)
    try:
        leaf_node(*args)
    except Exception as e:
        print_error("Error:", e)
        if isinstance(e, TypeError):
            signature = str(inspect.signature(leaf_node))
            print_error(f"Usage: {leaf_node.__name__}{signature}")
        raise SystemExit(1) from None


def show_options(
    current_node: CommandNode,
    traversed_path: str,
):
    options = [key for key in current_node.keys() if key != "leaf node"]
    if options:
        for key in options:
            print_error(f"{traversed_path} {key}".strip())
        return
    function_to_explain = current_node.get("leaf node")
    if callable(function_to_explain):
        signature = str(inspect.signature(function_to_explain))
        print_error(f"Usage: {function_to_explain.__name__}{signature}")


def handle_errors(
    error_message: str,
    traversed_path: str,
    path: str,
    current_node: CommandNode,
):
    if error_message == "No such path found":
        print_error(
            traversed_path + " " + path,
            "?",
        )
        print_error("try one of the following:")
        show_options(current_node, traversed_path)

    elif error_message == "Help flag found.":
        print_error(traversed_path + " " + path)
        print_error("try one of the following:")
        show_options(current_node, traversed_path)

    else:
        print_error(traversed_path, "?")
        print_error("No error message found for:", error_message)


def load_command_mapper() -> CommandNode:
    import devOS.user_input_map as user_input_map

    return typing.cast(CommandNode, user_input_map.mapper)


def explain_function(
    current_node: CommandNode,
):
    function_to_explain = current_node.get(
        "leaf node", lambda: print_message("No leaf node found")
    )
    if not callable(function_to_explain):
        return
    print_message(function_to_explain.__name__)
    print_message("Signature:", str(inspect.signature(function_to_explain)))
    print_message(function_to_explain.__doc__)
    return


def traverse_command_mapper(
    user_command: typing.List[str],
    command_mapper: CommandNode | None = None,
):
    if command_mapper is None:
        command_mapper = load_command_mapper()
    if not user_command:
        print_error("No command provided.")
        print_error("try one of the following:")
        show_options(command_mapper, "")
        return

    traversed_path = ""

    # Traverse the user command.
    for path_index, path in enumerate(user_command):
        # The traversed path is used in error messages.
        traversed_path = (traversed_path + " " + path).strip()

        # Traverse the command mapper dictionary with the user command.
        current_node: CommandNode | CommandLeaf | str = command_mapper.get(
            path, "No such path found"
        )

        # If the command is a string, it means that the path is not found.
        if isinstance(current_node, str):
            # Check for help flag in params.
            if "--help" in user_command[len(user_command) - 1]:
                current_node = "Help flag found."
                handle_errors(current_node, traversed_path, path, command_mapper)
                return

            # Check for explanation flag in params early to avoid extra checks in the loop.
            if "--explain" in user_command[len(user_command) - 1]:
                explain_function(command_mapper)
                return

            # Check if leaf node is the only key in the dictionary.
            command_mapper_has_a_leaf_node = "leaf node" in command_mapper.keys()

            # If the command mapper has a leaf node, execute the function.
            if command_mapper_has_a_leaf_node:
                function_to_execute = command_mapper.get(
                    "leaf node", lambda: print_message("No leaf node found")
                )
                if not callable(function_to_execute):
                    raise ValueError("Command leaf must be callable")
                execute_function(function_to_execute, *user_command[path_index:])
                break

            else:
                handle_errors(current_node, traversed_path, path, command_mapper)
                break

        else:
            if callable(current_node):
                execute_function(current_node, *user_command[path_index + 1 :])
                break
            is_last_path_ein_user_command = path_index == len(user_command) - 1
            if is_last_path_ein_user_command:
                function_to_execute = current_node.get(
                    "leaf node", lambda: print_message("No leaf node found")
                )
                if not callable(function_to_execute):
                    raise ValueError("Command leaf must be callable")
                execute_function(function_to_execute, *user_command[path_index + 1 :])
                break

        # Update the command mapper to the current node.
        command_mapper = current_node


def main():
    if sys.argv[1:2] == ["ui"]:
        from devOS import run_server

        raise SystemExit(run_server.main(sys.argv[2:]))

    if sys.argv[1:2] == ["build"] and sys.argv[2:3] != ["context"]:
        from devOS import resource_cli

        raise SystemExit(resource_cli.main(sys.argv[2:]))

    if sys.argv[1:2] == ["schema"]:
        from devOS import relational_cli

        raise SystemExit(relational_cli.main(sys.argv[2:]))

    import devOS.credential_cli as credential_cli

    if credential_cli.handles(sys.argv[1:]):
        raise SystemExit(credential_cli.main(sys.argv[1:]))
    # Windows consoles default to a legacy codec (cp1252) that can't encode
    # the emoji this CLI prints in commit/push messages; force UTF-8 so those
    # prints don't crash the command that already succeeded.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

    # Scaffold works before a Git repository or project configuration exists.
    if sys.argv[1:2] == ["scaffold"]:
        import devOS.scaffold_cli as scaffold_cli

        raise SystemExit(scaffold_cli.main(sys.argv[2:]))

    # Existing commands retain their mapper and project setup.
    traverse_command_mapper(sys.argv[1:])


if __name__ == "__main__":
    main()
