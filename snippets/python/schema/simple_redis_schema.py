import typing
import enum
from dataclasses import dataclass
import pydantic

MessageType = typing.TypeVar("MessageType", bound=pydantic.BaseModel)

SchemaType = typing.Union[typing.Dict[str, typing.Any], typing.Type[MessageType]]

Function = typing.Callable[..., typing.Any]

Number = typing.Union[float, int]

NodeParam = typing.Dict[str, typing.List[float]]


class RedisTimeSeriesResponse(pydantic.BaseModel):
    timestamp: int
    value: float
    key: str


# MQTT Message
class QualityofService(enum.Enum):
    AT_MOST_ONCE = 0  # fire and forget
    AT_LEAST_ONCE = 1  # acknowledge
    EXACTLY_ONCE = 2  # no duplicates


@dataclass
class MQTTMessage(pydantic.BaseModel):
    timestamp: int
    state: bool
    dup: bool
    mid: bool
    topic: str
    payload: bytes
    qos: QualityofService
    retain: bool
