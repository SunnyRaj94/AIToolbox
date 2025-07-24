import yaml
import os
import re
import json
from pathlib import Path
from dotenv import dotenv_values
import warnings
from typing import Union

warnings.filterwarnings(action="ignore")


def get_ancestor_dir(start_path: Union[str, Path], steps: int) -> Path:
    if not isinstance(steps, int) or steps < 0:
        raise ValueError("Steps must be a non-negative integer.")

    path = Path(start_path).resolve()
    if path.is_file():
        path = path.parent

    # Traverse up the directory tree the specified number of times
    for _ in range(steps):
        # Store the current path before moving to the parent
        original_path = path
        path = path.parent
        # Check if we have gone past the root directory (e.g., '/')
        if path == original_path:
            raise ValueError(
                f"Cannot go up {steps} levels from '{start_path}'. "
                "Traversal went beyond the filesystem root."
            )

    return path


def _load_yaml_file(filepath: str):
    """Loads a single YAML file."""
    if os.path.exists(filepath):
        try:
            with open(filepath, "r") as f:
                return yaml.safe_load(f)
        except yaml.YAMLError as e:
            print(f"Error loading YAML file '{filepath}': {e}")
            return {}
    return {}


def _load_json_file(filepath: str):
    """Loads a single YAML file."""
    if os.path.exists(filepath):
        try:
            with open(filepath, "r") as f:
                return json.load(f)
        except json.JSONDecodeError as e:
            print(f"Error loading JSON file '{filename}': {e}")
    return {}


def _load_env(filepath: str = ".env"):
    """Loads environment variables from a .env file in the configs directory."""
    if os.path.exists(filepath):
        return dotenv_values(filepath)
    else:
        print(f"Warning: .env file '{filename}' not found at '{filepath}'")
        return {}


def _resolve_placeholders(data, original_data: dict):
    """
    Recursively replaces placeholder strings (e.g., '${key}' or '<KEY_NAME>')
    in a dictionary or list using values from the all_replacements dictionary.
    """
    if isinstance(data, dict):
        return {k: _resolve_placeholders(v, original_data) for k, v in data.items()}
    elif isinstance(data, list):
        return [_resolve_placeholders(item, original_data) for item in data]
    elif isinstance(data, str):
        for match in re.findall(r"\$\{(\w+)\}", data):
            replacement_value = original_data.get(match)
            data = data.replace(f"${{{match}}}", f"{replacement_value}")
        return data
    else:
        return data


def get_absolute_path(relative_path: str) -> str:
    """
    Returns the absolute path of a given relative path.
    Works on Linux, macOS, and Windows.
    """
    return os.path.abspath(os.path.expanduser(relative_path))


def go_up_directories(abs_path: str, levels: int = 1) -> str:
    """
    Go up 'levels' directories from the given absolute path.
    """
    path = Path(abs_path).resolve()
    for _ in range(levels):
        path = path.parent
    return str(path)


def recursive_replace(data, old_value, new_value):
    """
    Recursively replace string values in nested dictionaries/lists.
    """
    if isinstance(data, dict):
        return {
            key: recursive_replace(value, old_value, new_value)
            for key, value in data.items()
        }
    elif isinstance(data, list):
        return [recursive_replace(item, old_value, new_value) for item in data]
    elif isinstance(data, str):
        return data.replace(old_value, new_value)
    else:
        return data


def _sanitize_name(filename: str) -> str:
    """Sanitizes a filename to be a valid Python identifier."""
    # Replace hyphens with underscores
    name = filename.replace("-", "_")
    # Remove any character that isn't a letter, number, or underscore
    name = re.sub(r"[^a-zA-Z0-9_]", "", name)
    # Ensure it doesn't start with a number (though unlikely for config files)
    if name and name[0].isdigit():
        name = "_" + name
    return name


def load_file(filename, DIR):
    filepath = os.path.join(DIR, filename)
    loaded_data = None
    # Get the name without extension
    config_name = os.path.splitext(filename)[0]
    # Sanitize name to be a valid Python identifier
    sanitized_config_name = _sanitize_name(config_name)
    if filename.endswith(".env"):
        loaded_data = _load_env(filepath)
        sanitized_config_name = (
            "env" if sanitized_config_name == "" else sanitized_config_name
        )
    # Load YAML files
    elif filename.endswith((".yaml", ".yml")):
        loaded_data = _load_yaml_file(filepath)
    # Load JSON files
    elif filename.endswith((".json")):
        loaded_data = _load_json_file(filepath)
    return loaded_data, sanitized_config_name


def print_directory_structure(
    startpath: str,
    include_extensions: list = None,
    exclude_dirs: list = None,
    show_hidden: bool = False,
    file_prefix: str = "📄 ",
    dir_prefix: str = "📁 ",
):
    """
    Displays the directory structure in a readable, tree-like format.

    Args:
        startpath (str): The path to the root directory of the tree.
        include_extensions (list, optional): A list of file extensions to include (e.g., ['.py']).
                                             If None, all files are shown. Defaults to None.
        exclude_dirs (list, optional): A list of directory names to exclude. Defaults to common ones.
        show_hidden (bool): If True, shows hidden files and directories (those starting with '.').
        file_prefix (str): Emoji or string to prepend to files.
        dir_prefix (str): Emoji or string to prepend to directories.
    """
    if exclude_dirs is None:
        exclude_dirs = ["__pycache__", ".git", ".vscode"]

    try:
        path_obj = Path(startpath)
        if not path_obj.is_dir():
            print(f"Error: '{startpath}' is not a valid directory.")
            return
    except Exception as e:
        print(f"Error validating path: {e}")
        return

    print(f"{dir_prefix}{path_obj.name}/")
    _print_tree_recursive(
        path_obj,
        prefix="",
        include_extensions=include_extensions,
        exclude_dirs=set(exclude_dirs),
        show_hidden=show_hidden,
        file_prefix=file_prefix,
        dir_prefix=dir_prefix,
    )


def _print_tree_recursive(
    dir_path: Path,
    prefix: str,
    include_extensions: list,
    exclude_dirs: set,
    show_hidden: bool,
    file_prefix: str,
    dir_prefix: str,
):
    """Recursive helper function to print the tree."""
    # Get contents, applying filters
    try:
        contents = [
            p
            for p in dir_path.iterdir()
            if (show_hidden or not p.name.startswith("."))
            and p.name not in exclude_dirs
        ]
    except PermissionError:
        print(f"{prefix}└── [Permission Denied]")
        return

    # Separate files and directories
    files = sorted([p for p in contents if p.is_file()])
    dirs = sorted([p for p in contents if p.is_dir()])

    # Apply extension filter
    if include_extensions:
        files = [f for f in files if f.suffix in include_extensions]

    entries = dirs + files

    for i, path in enumerate(entries):
        # Use '└──' for the last item, '├──' for others
        connector = "└── " if i == len(entries) - 1 else "├── "

        if path.is_dir():
            print(f"{prefix}{connector}{dir_prefix}{path.name}/")
            # The prefix for children adds space for the current connector
            child_prefix = prefix + ("    " if i == len(entries) - 1 else "│   ")
            _print_tree_recursive(
                path,
                child_prefix,
                include_extensions,
                exclude_dirs,
                show_hidden,
                file_prefix,
                dir_prefix,
            )
        else:
            print(f"{prefix}{connector}{file_prefix}{path.name}")


def handle_env_path(filedir, filename):
    loaded_data = None
    filepath = os.path.join(filedir, ".env")
    ENV_VARS = ENV_KEYS[:]
    if os.path.exists(filepath):
        loaded_data, sanitized_config_name = load_file(filename, filedir)
    elif os.environ.get("ENV_FILE_DIR"):
        loaded_data, sanitized_config_name = load_file(
            filename, os.environ.get("ENV_FILE_DIR")
        )
    elif ENV_VARS:
        loaded_data = dict((key, os.environ.get(key)) for key in ENV_VARS)
    return loaded_data


ENV_KEYS = [
    "SECRET_KEY",
    "MONGO_URI",
    "MONGO_DB",
    "EMAIL_FROM",
    "WHATSAPP_API_KEY",
]

REPO_ROOT = get_ancestor_dir(__file__, 2)
CONFIGS_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = Path(CONFIGS_DIR).parent.resolve()


replacements = {"<ROOT_PATH>": str(REPO_ROOT)}
__include__ = [(".env", REPO_ROOT), ("configs.yaml", CONFIGS_DIR)]


# Iterate through all files in the configs directory
for values in __include__:
    filename, filedir = values
    if filename == ".env":
        loaded_data = handle_env_path(filedir, filename)
        if loaded_data is not None:
            globals()["env"] = loaded_data
            continue
    filepath = os.path.join(filedir, filename)
    loaded_data, sanitized_config_name = load_file(filename, filedir)
    for key, value in replacements.items():
        loaded_data = recursive_replace(loaded_data, old_value=key, new_value=value)
    loaded_data = _resolve_placeholders(loaded_data, loaded_data)
    globals()[sanitized_config_name] = loaded_data