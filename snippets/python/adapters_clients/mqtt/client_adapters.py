from __future__ import annotations

import json
import random
import string
from dataclasses import dataclass
from typing import Any, Callable


@dataclass(frozen=True)
class MosquittoMQTTConfig:
    """Configuration for a Mosquitto/Paho MQTT connection.

    Parameters
    ----------
    broker
        Broker hostname.
    port
        Broker port.
    username
        Optional username.
    password
        Optional password.
    transport
        Paho transport, usually ``"tcp"`` or ``"websockets"``.
    clean_session
        Whether Paho should create a clean broker session.
    last_will_message
        Optional last-will payload with ``topic``, ``payload``, optional
        ``qos``, and optional ``retain`` keys.
    keep_alive_seconds
        Keep-alive interval used when connecting.
    """

    broker: str
    port: int = 1883
    username: str | None = None
    password: str | None = None
    transport: str = "tcp"
    clean_session: bool = False
    last_will_message: dict[str, Any] | None = None
    keep_alive_seconds: int = 60


class MQTTClientAdapter:
    """Wrap an MQTT client with publish and subscription helpers.

    Parameters
    ----------
    client
        MQTT client object with ``publish``, ``subscribe``, ``unsubscribe``, and
        ``disconnect`` methods.
    client_id
        Optional client ID. If omitted, a random uppercase ID is generated.
    """

    def __init__(self, client: Any, client_id: str | None = None) -> None:
        self.__client = client
        self.__client_id = client_id or self.generate_client_id()
        self.__topics_subscribed_to: list[str] = []

    @property
    def client_id(self) -> str:
        """Return the MQTT client ID.

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

    @staticmethod
    def generate_client_id(length: int = 8) -> str:
        """Generate a random uppercase MQTT client ID.

        Parameters
        ----------
        length
            Number of characters.

        Returns
        -------
        str
            Generated client ID.
        """

        if length <= 0:
            raise ValueError("length must be positive.")
        return "".join(random.choices(string.ascii_uppercase, k=length))

    def publish_data(
        self, topic: str, payload: dict[str, Any] | str, qos: int = 0
    ) -> bool:
        """Publish a payload to a topic.

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
        """Subscribe to a topic.

        Parameters
        ----------
        topic
            MQTT topic.
        callback
            Callback invoked by the MQTT client.
        qos
            Quality of service.

        Returns
        -------
        bool
            ``True`` when the client reports a successful subscription.
        """

        if not topic:
            return False
        subscribed = bool(self.__client.subscribe(topic, qos, callback))
        if subscribed:
            self.__topics_subscribed_to.append(topic)
        return subscribed

    def unsubscribe_from_topic(self, topic: str) -> list[str]:
        """Unsubscribe from one topic.

        Parameters
        ----------
        topic
            MQTT topic.

        Returns
        -------
        list[str]
            Remaining subscription list.
        """

        if topic in self.__topics_subscribed_to:
            self.__topics_subscribed_to.remove(topic)
        self.__client.unsubscribe(topic)
        return self.topics_subscribed_to

    def disconnect(self) -> None:
        """Unsubscribe from all topics and disconnect.

        Side Effects
        ------------
        Calls ``unsubscribe`` once per tracked topic and then ``disconnect``.
        """

        for topic in list(self.__topics_subscribed_to):
            self.unsubscribe_from_topic(topic)
        self.__client.disconnect()


class MosquittoMQTTClientAdapter:
    """MQTT adapter for a Paho/Mosquitto client.

    Parameters
    ----------
    client
        Paho-compatible client with ``username_pw_set``, ``connect``,
        ``loop_start``, ``publish``, ``subscribe``, ``message_callback_add``,
        ``message_callback_remove``, ``unsubscribe``, ``loop_stop``, and
        ``disconnect``.
    config
        Mosquitto broker connection configuration.
    client_id
        Optional client ID. If omitted, a random uppercase ID is generated.
    """

    def __init__(
        self,
        client: Any,
        config: MosquittoMQTTConfig,
        client_id: str | None = None,
    ) -> None:
        self.__client = client
        self.__config = config
        self.__client_id = client_id or MQTTClientAdapter.generate_client_id()
        self.__topics_subscribed_to: list[str] = []
        self.__configure_client()

    def __configure_client(self) -> None:
        if self.__config.username is not None:
            self.__client.username_pw_set(
                self.__config.username,
                self.__config.password,
            )
        if self.__config.last_will_message is not None:
            self.__set_last_will_testament(self.__config.last_will_message)

    def __set_last_will_testament(self, message: dict[str, Any]) -> None:
        payload = self.__serialize_payload(message["payload"])
        self.__client.will_set(
            topic=message["topic"],
            payload=payload,
            qos=int(message.get("qos", 1)),
            retain=bool(message.get("retain", True)),
        )

    def __serialize_payload(self, payload: dict[str, Any] | str | bytes) -> bytes:
        if isinstance(payload, dict):
            return json.dumps(payload).encode("utf-8")
        if isinstance(payload, str):
            return payload.encode("utf-8")
        return payload

    @property
    def client_id(self) -> str:
        """Return the Mosquitto MQTT client ID.

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

    def connect(self) -> "MosquittoMQTTClientAdapter":
        """Connect to a Mosquitto broker.

        Returns
        -------
        MosquittoMQTTClientAdapter
            This adapter for chaining.
        """

        self.__client.connect(
            self.__config.broker,
            self.__config.port,
            self.__config.keep_alive_seconds,
        )
        self.__client.loop_start()
        return self

    def publish_data(
        self,
        topic: str,
        payload: dict[str, Any] | str,
        qos: int = 0,
    ) -> bool:
        """Publish data to Mosquitto MQTT.

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
            ``True`` when Paho reports success.
        """

        if not topic:
            return False
        serialized_payload = self.__serialize_payload(payload)
        result = self.__client.publish(topic, serialized_payload, qos=qos)
        return getattr(result, "rc", 0) == 0

    def subscribe_to_topic(
        self,
        topic: str,
        callback: Callable[[Any, Any, Any], None],
        qos: int = 1,
    ) -> bool:
        """Subscribe to a Mosquitto MQTT topic.

        Parameters
        ----------
        topic
            MQTT topic.
        callback
            Callback invoked by Paho.
        qos
            Quality of service.

        Returns
        -------
        bool
            ``True`` when Paho reports success.
        """

        if not topic:
            return False
        self.__client.message_callback_add(topic, callback)
        result = self.__client.subscribe(topic, qos=qos)
        result_code = (
            result[0] if isinstance(result, tuple) else getattr(result, "rc", 0)
        )
        subscribed = result_code == 0
        if subscribed:
            self.__topics_subscribed_to.append(topic)
        return subscribed

    def unsubscribe_from_topic(self, topic: str) -> list[str]:
        """Unsubscribe from one Mosquitto MQTT topic.

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
        if hasattr(self.__client, "message_callback_remove"):
            self.__client.message_callback_remove(topic)
        self.__client.unsubscribe(topic)
        return self.topics_subscribed_to

    def disconnect(self) -> None:
        """Unsubscribe from tracked topics, stop the loop, and disconnect."""

        for topic in list(self.__topics_subscribed_to):
            self.unsubscribe_from_topic(topic)
        self.__client.loop_stop()
        self.__client.disconnect()

    def unsubscribe_and_disconnect(self) -> None:
        """Unsubscribe from all topics and disconnect the Paho loop."""

        self.disconnect()
