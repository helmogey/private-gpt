from pathlib import Path

from private_gpt.constants import PROJECT_ROOT_PATH
from private_gpt.settings.settings import settings


def _absolute_or_from_project_root(path: str) -> Path:
    path_obj = Path(path)
    if path_obj.is_absolute():
        return path_obj
    return PROJECT_ROOT_PATH / path


models_path: Path = PROJECT_ROOT_PATH / "models"
models_cache_path: Path = models_path / "cache"
docs_path: Path = PROJECT_ROOT_PATH / "docs"
local_data_path: Path = _absolute_or_from_project_root(
    settings().data.local_data_folder
)
