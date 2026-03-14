import mqtt from "mqtt";
import { generateRandomId } from "../utils";

export default class MQTTApi {
  clientId: string;
  client: any;
  brokerPort: number;
  mqttUsername: string;
  mqttPassword: string;

  constructor() {
    // Mosquitto MQTT Broker
    this.brokerPort = 36859;
    this.mqttUsername = "admin";
    this.mqttPassword = "mypassword";
    this.clientId = generateRandomId(20);
    this.client = this.connectClient();
    this.client.on("error", (e: any) => {
      console.log("Connection error: ", e);
    });
  }

  /**
   * Connect to Mosquitto via WSS using username/password
   */
  private connectClient() {
    return mqtt.connect(this.getEndpoint(), {
      username: this.mqttUsername,
      password: this.mqttPassword,
      clientId: this.clientId,
      clean: true,
      reconnectPeriod: 2000,
      keepalive: 60,
    });
  }

  /**
   * Build WSS endpoint for Mosquitto (WebSocket path /mqtt)
   */
  private getEndpoint() {
    return "wss://eclipse-mqtt-broker-production.up.railway.app/mqtt";
  }

  /**
   * this function subscribe the client to the provided topic,
   * the function should be called within the on connect callback and
   *
   * @param {*} topic - a topic is a channel where data can be streamed too and consumed by various clients
   * @param {*} callBack - a callback is a function which will be executed when the client subscribe
   */
  subscribeClient(topic: string, callBack: CallableFunction) {
    this.client.subscribe(topic, (err: any) => {
      if (!err) {
        console.log("subscribed", topic);
        callBack();
      } else {
        console.log(err);
      }
    });
    return this;
  }

  /**
   * This function runs when the messageBus is connected to the web socket which occurs when the class is instantiated
   * @see the connectClient() method
   * keep this function within a ``useEffect`` or a ``componentDidMount()`` to avoid connection timeout errors
   *
   * @param {*} callBack - a callback is a function which will be executed when the client connect
   * specify most of the logic of the client within this block
   */
  onConnect(callBack: CallableFunction) {
    this.client.on("connect", () => {
      callBack();
    });
  }

  /**
   * This function runs the callback when a new message arrives,
   * the message event listener of the MQTT object returns the topic and the message that are received automatically
   * however this is taken care of within the wrapper function therefore the callback should have:
   *
   * ```javascript
   * const onMessageCallBack(message) {
   *   messageProcessingLogic()
   * }
   * ```
   * call this function wihtin the onConnect callback,
   * after the client is subscribed i.e.
   *
   * ```javascript
   * onConnect(() => {
   *   onSubscribe()
   *   onMessage(onMessageCallback)
   *  }
   * )
   * ```
   *
   * @param {*} callBack - this is a function which is called when a new message arrives
   * to a topic which the client is listening too
   */
  onMessage(callbackTopic: string, callBack: CallableFunction) {
    this.client.on("message", (topic: string, message: any) => {
      if (callbackTopic.endsWith("#")) {
        const baseTopic = callbackTopic.slice(0, -1); // Remove the '#' wildcard
        if (topic.startsWith(baseTopic)) {
          let decodedMessage = message.toString();
          callBack(decodedMessage, topic);
        }
      } else if (topic === callbackTopic) {
        let decodedMessage = message.toString();
        callBack(decodedMessage, topic);
      }
    });
  }

  /**
   * This function publishes messages to the Broker <AWS>,the quality of service is kept as 0 to avoid timeouts
   *
   * @param {*} topic - the topic which the client will publish the message to
   * @param {*} payload - the payload that the client needs to publish
   */
  publishMessage(topic: string, payload: Object) {
    this.client.publish(topic, JSON.stringify(payload), { qos: 0 }, (error: any) => {
      console.log(topic);
      console.dir(payload, { depth: Infinity });
      if (error) {
        console.log(error);
      }
    });
  }

  unsubscribeClient(topic: string) {
    this.client.unsubscribe(topic, () => {
      console.log("unsubscribed", topic);
    });
    return this;
  }

  disconnectClient() {
    this.client.end();
  }
}
