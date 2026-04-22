"""Generic JSONL store primitives used by every memory layer."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable, Iterator, Type, TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


def _find_repo_root() -> Path:
    cur = Path(__file__).resolve().parent
    while cur != cur.parent:
        if (cur / "pyproject.toml").exists():
            return cur
        cur = cur.parent
    return Path.cwd()


def default_memory_root() -> Path:
    return _find_repo_root() / "data" / "memory"


class JsonlStore:
    """Append-only JSONL store for pydantic records. Deterministic, no locks."""

    def __init__(self, path: Path, model: Type[BaseModel]) -> None:
        self.path = Path(path)
        self.model = model
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def append(self, record: BaseModel) -> None:
        if not isinstance(record, self.model):
            raise TypeError(
                f"{self.path.name} expects {self.model.__name__}, got {type(record).__name__}"
            )
        with self.path.open("a", encoding="utf-8") as f:
            f.write(record.model_dump_json() + "\n")

    def extend(self, records: Iterable[BaseModel]) -> None:
        for r in records:
            self.append(r)

    def iter_all(self) -> Iterator[BaseModel]:
        if not self.path.exists():
            return
        with self.path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                yield self.model.model_validate(json.loads(line))

    def all(self) -> list[BaseModel]:
        return list(self.iter_all())
