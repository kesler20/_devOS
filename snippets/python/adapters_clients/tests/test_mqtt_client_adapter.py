from adapters_clients.aws.mqtt_client_adapter import (
    AWSIoTMQTTClientAdapter,
    AWSIoTMQTTConfig,
)
from adapters_clients.mqtt.client_adapters import (
    MQTTClientAdapter,
    MosquittoMQTTClientAdapter,
    MosquittoMQTTConfig,
)


class FakeMQTTClient:
    def __init__(self) -> None:
        self.published = []
        self.subscribed = []
        self.unsubscribed = []
        self.disconnected = False

    def publish(self, topic, payload, qos):
        self.published.append((topic, payload, qos))

    def subscribe(self, topic, qos, callback):
        self.subscribed.append((topic, qos, callback))
        return True

    def unsubscribe(self, topic):
        self.unsubscribed.append(topic)

    def disconnect(self):
        self.disconnected = True


class FakeAWSIoTClient(FakeMQTTClient):
    def __init__(self) -> None:
        super().__init__()
        self.endpoint = None
        self.credentials = None
        self.connected_keep_alive = None

    def configureEndpoint(self, endpoint, port):
        self.endpoint = (endpoint, port)

    def configureCredentials(self, root_ca_path, private_key_path, certificate_path):
        self.credentials = (root_ca_path, private_key_path, certificate_path)

    def connect(self, keepAliveIntervalSecond):
        self.connected_keep_alive = keepAliveIntervalSecond


class FakePublishResult:
    def __init__(self, rc):
        self.rc = rc


class FakeMosquittoClient:
    def __init__(self) -> None:
        self.username = None
        self.connected = None
        self.loop_started = False
        self.loop_stopped = False
        self.published = []
        self.callbacks = []
        self.subscribed = []
        self.unsubscribed = []
        self.disconnected = False
        self.removed_callbacks = []
        self.last_will = None

    def username_pw_set(self, username, password):
        self.username = (username, password)

    def will_set(self, topic, payload, qos, retain):
        self.last_will = (topic, payload, qos, retain)

    def connect(self, broker, port, keep_alive):
        self.connected = (broker, port, keep_alive)

    def loop_start(self):
        self.loop_started = True

    def publish(self, topic, payload, qos):
        self.published.append((topic, payload, qos))
        return FakePublishResult(0)

    def message_callback_add(self, topic, callback):
        self.callbacks.append((topic, callback))

    def subscribe(self, topic, qos):
        self.subscribed.append((topic, qos))
        return (0, 1)

    def unsubscribe(self, topic):
        self.unsubscribed.append(topic)

    def message_callback_remove(self, topic):
        self.removed_callbacks.append(topic)

    def loop_stop(self):
        self.loop_stopped = True

    def disconnect(self):
        self.disconnected = True


def test_publish_serializes_dict_payload() -> None:
    fake_client = FakeMQTTClient()
    adapter = MQTTClientAdapter(fake_client, client_id="client")

    assert adapter.publish_data("topic/data", {"value": 1}, qos=1) is True
    assert fake_client.published == [("topic/data", '{"value": 1}', 1)]


def test_subscribe_unsubscribe_and_disconnect() -> None:
    fake_client = FakeMQTTClient()
    adapter = MQTTClientAdapter(fake_client, client_id="client")

    assert adapter.subscribe_to_topic("topic/control", lambda *_: None) is True
    assert adapter.topics_subscribed_to == ["topic/control"]

    assert adapter.unsubscribe_from_topic("topic/control") == []
    assert fake_client.unsubscribed == ["topic/control"]

    adapter.subscribe_to_topic("topic/again", lambda *_: None)
    adapter.disconnect()
    assert fake_client.disconnected is True
    assert fake_client.unsubscribed[-1] == "topic/again"


def test_aws_iot_mqtt_adapter_connects_with_tls_config() -> None:
    fake_client = FakeAWSIoTClient()
    adapter = AWSIoTMQTTClientAdapter(
        fake_client,
        AWSIoTMQTTConfig(
            endpoint="endpoint.iot",
            root_ca_path="root.pem",
            private_key_path="private.key",
            certificate_path="cert.pem",
        ),
        client_id="aws-client",
    )

    assert adapter.connect() is adapter
    assert fake_client.endpoint == ("endpoint.iot", 8883)
    assert fake_client.credentials == ("root.pem", "private.key", "cert.pem")
    assert fake_client.connected_keep_alive == 10


def test_aws_iot_mqtt_adapter_publish_subscribe_and_disconnect() -> None:
    fake_client = FakeAWSIoTClient()
    adapter = AWSIoTMQTTClientAdapter(
        fake_client,
        AWSIoTMQTTConfig("endpoint.iot", "root.pem", "private.key", "cert.pem"),
    )

    assert adapter.publish_data("aws/topic", {"value": 1}, qos=1) is True
    assert fake_client.published == [("aws/topic", '{"value": 1}', 1)]
    assert adapter.subscribe_to_topic("aws/topic", lambda *_: None) is True
    adapter.disconnect()
    assert fake_client.disconnected is True


def test_mosquitto_mqtt_adapter_connects_with_credentials() -> None:
    fake_client = FakeMosquittoClient()
    adapter = MosquittoMQTTClientAdapter(
        fake_client,
        MosquittoMQTTConfig(
            broker="localhost",
            username="user",
            password="password",
        ),
        client_id="mosquitto-client",
    )

    assert adapter.connect() is adapter
    assert fake_client.username == ("user", "password")
    assert fake_client.connected == ("localhost", 1883, 60)
    assert fake_client.loop_started is True


def test_mosquitto_mqtt_adapter_sets_last_will() -> None:
    fake_client = FakeMosquittoClient()

    MosquittoMQTTClientAdapter(
        fake_client,
        MosquittoMQTTConfig(
            broker="localhost",
            last_will_message={
                "topic": "system/status",
                "payload": {"status": "offline"},
                "qos": 1,
                "retain": True,
            },
        ),
    )

    assert fake_client.last_will == (
        "system/status",
        b'{"status": "offline"}',
        1,
        True,
    )


def test_mosquitto_mqtt_adapter_publish_subscribe_and_disconnect() -> None:
    fake_client = FakeMosquittoClient()
    adapter = MosquittoMQTTClientAdapter(
        fake_client,
        MosquittoMQTTConfig(broker="localhost"),
    )

    assert adapter.publish_data("mosquitto/topic", {"value": 1}, qos=1) is True
    assert fake_client.published == [("mosquitto/topic", b'{"value": 1}', 1)]
    assert adapter.subscribe_to_topic("mosquitto/topic", lambda *_: None) is True
    adapter.disconnect()
    assert fake_client.removed_callbacks == ["mosquitto/topic"]
    assert fake_client.loop_stopped is True
    assert fake_client.disconnected is True
