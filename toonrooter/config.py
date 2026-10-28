from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Config:
    serial_port: Path = Path("/dev/serial0")

    def __post_init__(self) -> None:
        if not self.serial_port.is_absolute():
            raise ValueError("Serial port must be an absolute path")
