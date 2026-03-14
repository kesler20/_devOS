export interface NoSQLDbInterface {
  /**
   *
   * @param topic The topic of the resource i.e. "production", "development", etc.
   * @param resourceId The unique identifier of the resource
   * @param content The content of the resource as a key-value pair
   * @returns {boolean} returns true if the resource was successfully put into the database, false otherwise
   */
  putResource(
    topic: string,
    resourceId: string,
    content: { [key: string]: any }
  ): Promise<boolean>;

  /**
   *
   * @param topic The topic of the resource i.e. "production", "development", etc.
   * @param resourceId  The unique identifier of the resource
   * @returns {Promise<any>} returns the resource if it exists, null otherwise
   */
  getResource(topic: string, resourceId: string): Promise<any>;

  /**
   *
   * @param topic The topic of the resource i.e. "production", "development", etc.
   * @returns {Promise<any>} returns the resources if they exist, null otherwise
   */
  getResources(topic: string): Promise<any>;

  /**
   *
   * @param topic The topic of the resource i.e. "production", "development", etc.
   * @param resourceId  The unique identifier of the resource
   * @returns  {Promise<boolean>} returns true if the resource was successfully deleted, false otherwise
   */
  deleteResource(topic: string, resourceId: string): Promise<boolean>;

  /**
   * Close the connection to the NoSQL database
   */
  close(): void;
}
