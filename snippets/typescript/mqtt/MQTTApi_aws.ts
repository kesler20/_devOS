import CryptoJS from "crypto-js";
import mqtt from "mqtt";
import { generateRandomId } from "./utils";

export default class MQTTApi {
  clientId: string;
  client: any;
  access_key_id: string;
  secret_key: string;
  iot_endpoint: string;
  region: string;

  constructor() {
    this.access_key_id = "accessKey1";
    this.region = "eu-west-2";
    this.secret_key = "verySecretKey1";
    this.iot_endpoint = "a2gac7ap3hk6n-ats.iot.eu-west-2.amazonaws.com";
    this.clientId = generateRandomId(20);
    this.client = this.connectClient();
    this.client.on("error", (e: any) => {
      console.log("Connection error: ", e);
    });
  }
  /**
   * This function will run when the client is initially instantiated and will connect the client to the
   * broker via a secure connection
   *
   * @returns {*} returns an instance of an MQTT object
   */
  private connectClient() {
    return mqtt.connect(this.getEndpoint());
  }

  /**
   * This function generates the endpoint to connection to AWS from the credentials provided
   *
   * @returns {*} the mqtt web socket endpoint used for streaming connection
   */
  private getEndpoint() {
    const REGION = this.region;

    // your AWS access key ID
    const AWS_ACCESS_KEY_ID = this.access_key_id;

    // your AWS secret access key
    const AWS_SECRET_ACCESS_KEY = this.secret_key;
    const ENDPOINT = this.iot_endpoint;

    const now = new Date();
    const amzdate = now.toISOString().replace(/[:-]|\.\d{3}/g, "");
    const datestamp = now.toISOString().slice(0, 10).replace(/-/g, "");
    const service = "iotdevicegateway";

    const canonicalQuerystring = `X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Credential=${encodeURIComponent(
      AWS_ACCESS_KEY_ID +
        "/" +
        datestamp +
        "/" +
        REGION +
        "/" +
        service +
        "/aws4_request"
    )}&X-Amz-Date=${amzdate}&X-Amz-SignedHeaders=host`;
    const canonicalHeaders = `host:${ENDPOINT}\n`;
    const signedHeaders = "host";
    const payloadHash = CryptoJS.SHA256("").toString(CryptoJS.enc.Hex);
    const canonicalRequest = `GET\n/mqtt\n${canonicalQuerystring}\n${canonicalHeaders}\n${signedHeaders}\n${payloadHash}`;

    const algorithm = "AWS4-HMAC-SHA256";
    const credentialScope = `${datestamp}/${REGION}/${service}/aws4_request`;
    const stringToSign = `${algorithm}\n${amzdate}\n${credentialScope}\n${CryptoJS.SHA256(
      canonicalRequest
    ).toString(CryptoJS.enc.Hex)}`;

    const kDate = CryptoJS.HmacSHA256(datestamp, "AWS4" + AWS_SECRET_ACCESS_KEY);
    const kRegion = CryptoJS.HmacSHA256(REGION, kDate);
    const kService = CryptoJS.HmacSHA256(service, kRegion);
    const kSigning = CryptoJS.HmacSHA256("aws4_request", kService);
    const signature = CryptoJS.HmacSHA256(stringToSign, kSigning).toString(
      CryptoJS.enc.Hex
    );

    return `wss://${ENDPOINT}/mqtt?${canonicalQuerystring}&X-Amz-Signature=${signature}`;
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
