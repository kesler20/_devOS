import { DynamoDBClient } from "@aws-sdk/client-dynamodb";
import {
  PutCommand,
  GetCommand,
  DeleteCommand,
  DynamoDBDocumentClient,
  QueryCommand,
} from "@aws-sdk/lib-dynamodb";
import { NoSQLDbInterface } from "./noSQLDBInterface";
import awsCredentials from "../../credentials/awsCredentials";

/**
 * This class is an adapter for the NoSQL database, it is used to interact with the database
 * and perform CRUD operations on the resources
 *
 * @param tableName {string} the name of the table in the database
 *
 * @returns {boolean} returns true if the resource was successfully put into the database, false otherwise
 *
 * @example
 * ```typescript
 * const db = new NoSQLdbAdapter("main-db");
 *
 * const result = await db.putResource("production", "resourceId", { key: "value" });
 *
 * if (result) {
 *  console.log("Resource put successfully");
 * } else {
 * console.log("Error putting resource");
 * }
 *
 * ```
 */
export default class DynamoDBAdapter implements NoSQLDbInterface {
  private dynamoDb: DynamoDBDocumentClient;
  public tableName: string;
  private AWS_ACCESS_KEY_ID: string;
  private AWS_SECRET_ACCESS_KEY: string;
  private AWS_REGION: string;

  constructor() {
    this.tableName = awsCredentials.tableName;
    this.AWS_ACCESS_KEY_ID = awsCredentials.AWS_ACCESS_KEY_ID;
    this.AWS_SECRET_ACCESS_KEY = awsCredentials.AWS_SECRET_ACCESS_KEY;
    this.AWS_REGION = awsCredentials.AWS_REGION;
    const client = new DynamoDBClient({
      region: this.AWS_REGION,
      credentials: {
        accessKeyId: this.AWS_ACCESS_KEY_ID,
        secretAccessKey: this.AWS_SECRET_ACCESS_KEY,
      },
    });
    this.dynamoDb = DynamoDBDocumentClient.from(client);
  }

  /**
   *
   * @param topic The topic of the resource i.e. "production", "development", etc.
   * @param resourceId The unique identifier of the resource
   * @param content The content of the resource as a key-value pair
   * @returns {boolean} returns true if the resource was successfully put into the database, false otherwise
   */
  async putResource(
    topic: string,
    resourceId: string,
    content: { [key: string]: any }
  ): Promise<boolean> {
    const params = {
      TableName: this.tableName,
      Item: {
        topic: topic,
        resourceID: resourceId,
        ...content,
      },
    };

    try {
      await this.dynamoDb.send(new PutCommand(params));
      return true;
    } catch (error) {
      console.error("Error in putResource:", error);
      return false;
    }
  }

  /**
   *
   * @param topic The topic of the resource i.e. "production", "development", etc.
   * @param resourceId  The unique identifier of the resource
   * @returns {Promise<any>} returns the resource if it exists, null otherwise
   */
  async getResource(topic: string, resourceId: string): Promise<any> {
    const params = {
      TableName: this.tableName,
      Key: {
        topic: topic,
        resourceID: resourceId,
      },
    };

    try {
      const data = await this.dynamoDb.send(new GetCommand(params));
      return data.Item || null;
    } catch (error) {
      console.error("Error in getResource:", error);
      return null;
    }
  }

  /**
   *
   * @param topic The topic of the resource i.e. "production", "development", etc.
   * @returns {Promise<any>} returns the resources if they exist, null otherwise
   */
  async getResources(topic: string): Promise<any> {
    const params = {
      TableName: this.tableName,
      KeyConditionExpression: "#topic = :topic",
      ExpressionAttributeNames: {
        "#topic": "topic",
      },
      ExpressionAttributeValues: {
        ":topic": topic,
      },
    };

    try {
      const data = await this.dynamoDb.send(new QueryCommand(params));
      return data.Items || null;
    } catch (error) {
      console.error("Error in getResources:", error);
      return null;
    }
  }

  /**
   *
   * @param topic The topic of the resource i.e. "production", "development", etc.
   * @param resourceId  The unique identifier of the resource
   * @returns  {Promise<boolean>} returns true if the resource was successfully deleted, false otherwise
   */
  async deleteResource(topic: string, resourceId: string): Promise<boolean> {
    const params = {
      TableName: this.tableName,
      Key: {
        topic: topic,
        resourceID: resourceId,
      },
    };

    try {
      await this.dynamoDb.send(new DeleteCommand(params));
      return true;
    } catch (error) {
      console.error("Error in deleteResource:", error);
      return false;
    }
  }


  close() {
    console.log("Closing connection")
  }
}
