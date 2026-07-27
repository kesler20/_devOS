from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Callable

from adapters_clients.mqtt.client_adapters import MQTTClientAdapter


@dataclass(frozen=True)
class AWSIoTMQTTConfig:
    """Configuration for an AWS IoT MQTT connection.

    Parameters
    ----------
    endpoint
        AWS IoT endpoint hostname.
    root_ca_path
        Root CA certificate path.
    private_key_path
        Private key path.
    certificate_path
        Device certificate path.
    port
        MQTT TLS port.
    keep_alive_seconds
        Keep-alive interval used when connecting.
    """

    endpoint: str
    root_ca_path: str
    private_key_path: str
    certificate_path: str
    port: int = 8883
    keep_alive_seconds: int = 10


class AWSIoTMQTTClientAdapter:
    """MQTT adapter for the AWS IoT Python SDK client.

    Parameters
    ----------
    client
        AWS IoT SDK client with ``configureEndpoint``,
        ``configureCredentials``, ``connect``, ``publish``, ``subscribe``,
        ``unsubscribe``, and ``disconnect``.
    config
        AWS IoT MQTT connection configuration.
    client_id
        Optional client ID. If omitted, a random uppercase ID is generated.
    """

    def __init__(
        self,
        client: Any,
        config: AWSIoTMQTTConfig,
        client_id: str | None = None,
    ) -> None:
        self.__client = client
        self.__config = config
        self.__client_id = client_id or MQTTClientAdapter.generate_client_id()
        self.__topics_subscribed_to: list[str] = []

    @property
    def client_id(self) -> str:
        """Return the AWS IoT MQTT client ID.

        Returns
        -------
        str
            Client ID.
        """

        return self.__client_id

    @property
    def topics_subscribed_to(self) -> list[str]:
        """Return subscribed topics.

        Returns
        -------
        list[str]
            Current subscription list.
        """

        return list(self.__topics_subscribed_to)

    def connect(self) -> "AWSIoTMQTTClientAdapter":
        """Configure TLS credentials and connect to AWS IoT.

        Returns
        -------
        AWSIoTMQTTClientAdapter
            This adapter for chaining.
        """

        self.__client.configureEndpoint(self.__config.endpoint, self.__config.port)
        self.__client.configureCredentials(
            self.__config.root_ca_path,
            self.__config.private_key_path,
            self.__config.certificate_path,
        )
        self.__client.connect(keepAliveIntervalSecond=self.__config.keep_alive_seconds)
        return self

    def publish_data(
        self,
        topic: str,
        payload: dict[str, Any] | str,
        qos: int = 0,
    ) -> bool:
        """Publish data to AWS IoT MQTT.

        Parameters
        ----------
        topic
            MQTT topic.
        payload
            String payload or JSON-compatible dictionary.
        qos
            Quality of service.

        Returns
        -------
        bool
            ``True`` when publish is called.
        """

        if not topic:
            return False
        serialized_payload = (
            json.dumps(payload) if isinstance(payload, dict) else payload
        )
        self.__client.publish(topic, serialized_payload, qos)
        return True

    def subscribe_to_topic(
        self,
        topic: str,
        callback: Callable[[Any, Any, Any], None],
        qos: int = 1,
    ) -> bool:
        """Subscribe to an AWS IoT MQTT topic.

        Parameters
        ----------
        topic
            MQTT topic.
        callback
            Callback invoked by the AWS SDK client.
        qos
            Quality of service.

        Returns
        -------
        bool
            ``True`` when the subscription succeeds.
        """

        if not topic:
            return False
        subscribed = bool(self.__client.subscribe(topic, qos, callback))
        if subscribed:
            self.__topics_subscribed_to.append(topic)
        return subscribed

    def unsubscribe_from_topic(self, topic: str) -> list[str]:
        """Unsubscribe from one AWS IoT MQTT topic.

        Parameters
        ----------
        topic
            MQTT topic.

        Returns
        -------
        list[str]
            Remaining subscriptions.
        """

        if topic in self.__topics_subscribed_to:
            self.__topics_subscribed_to.remove(topic)
        self.__client.unsubscribe(topic)
        return self.topics_subscribed_to

    def disconnect(self) -> None:
        """Unsubscribe from tracked topics and disconnect."""

        for topic in list(self.__topics_subscribed_to):
            self.unsubscribe_from_topic(topic)
        self.__client.disconnect()
