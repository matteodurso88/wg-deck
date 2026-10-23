"""Future backend interface. No privileged implementation in foundation."""

from __future__ import annotations

from typing import Protocol

from .models import ProfileSnapshot


class TunnelBackend(Protocol):
    def list_profiles(self) -> list[ProfileSnapshot]: ...

    def up(self, profile_name: str) -> None: ...

    def down(self, profile_name: str) -> None: ...
