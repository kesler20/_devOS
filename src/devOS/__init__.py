import inspect
import sys
import typing


def print_message(*args):
    if "--debug" in sys.argv or "--explain" in sys.argv or "--help" in sys.argv:
        print(*args)


def print_error(*args):
    print(*args, file=sys.stderr)


def execute_function(leaf_node: typing.Callable[..., typing.Any], *args):
    print_message("executing function:", leaf_node)
    print_message("with args:", args)
    try:
        leaf_node(*args)
    except Exception as e:
        print_error("Error:", e)
        if isinstance(e, TypeError):
            signature = str(inspect.signature(leaf_node))
            print_error(f"Usage: {leaf_node.__name__}{signature}")


def record_traversed_path(traversed_path: str, path: str) -> str:
    return traversed_path + " " + path


def clean_traversed_path(traversed_path: str) -> str:
    clean_traversed_path = list(
        filter(
            lambda item: item in get_all_keys_from_mapper(load_command_mapper()),
            traversed_path.split(" "),
        )
    )
    return " ".join(clean_traversed_path)


def show_options(
    current_node: typing.Dict[str, typing.Any],
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
    current_node: typing.Dict[str, typing.Any],
):
    traversed_path = clean_traversed_path(traversed_path)
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


def load_command_mapper() -> typing.Dict[str, typing.Any]:
    from devOS.user_input_map import mapper

    return mapper  # type: ignore


def get_all_keys_from_mapper(
    main_dict: typing.Dict[str, typing.Any]
) -> typing.List[str]:
    mapper_keys = []

    def get_all_keys(main_dict):
        if not isinstance(main_dict, dict):
            return

        for key in main_dict.keys():
            mapper_keys.append(key)
            if isinstance(main_dict[key], dict):
                get_all_keys(main_dict[key])

    get_all_keys(main_dict)
    return mapper_keys


def explain_function(
    current_node: typing.Dict[str, typing.Any],
):
    function_to_explain = current_node.get(
        "leaf node", lambda: print_message("No leaf node found")
    )
    print_message(function_to_explain.__name__)
    print_message("Signature:", str(inspect.signature(function_to_explain)))
    print_message(function_to_explain.__doc__)
    return


def traverse_command_mapper(
    user_command: typing.List[str],
    command_mapper: typing.Dict[str, typing.Any] = load_command_mapper(),
):
    if not user_command:
        print_error("No command provided.")
        print_error("try one of the following:")
        show_options(command_mapper, "")
        return

    traversed_path = ""

    # Traverse the user command.
    for path_index, path in enumerate(user_command):
        # The traversed path is used in error messages.
        traversed_path = record_traversed_path(traversed_path, path)

        # Traverse the command mapper dictionary with the user command.
        current_node: typing.Union[
            str,
            typing.Dict[str, typing.Any],
            typing.Dict[str, typing.Callable[..., typing.Any]],
        ] = command_mapper.get(path, "No such path found")

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
                execute_function(function_to_execute, *user_command[path_index:])
                break

            else:
                handle_errors(current_node, traversed_path, path, command_mapper)
                break

        else:
            is_last_path_ein_user_command = path_index == len(user_command) - 1
            if is_last_path_ein_user_command:
                function_to_execute = current_node.get(
                    "leaf node", lambda: print_message("No leaf node found")
                )
                execute_function(function_to_execute, *user_command[path_index + 1 :])
                break

        # Update the command mapper to the current node.
        command_mapper = current_node  # type: ignore


def main():
    # Run the CLI.
    traverse_command_mapper(sys.argv[1:])


if __name__ == "__main__":
    main()
