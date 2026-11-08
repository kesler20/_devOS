import dataclasses


@dataclasses.dataclass(frozen=True)
class CredentialMigrationResult:
    redis_verified: list[str]
    redis_unavailable: list[str]
    projects: list[str]
