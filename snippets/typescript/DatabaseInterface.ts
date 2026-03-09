import axios from "axios";

/**
 * DatabaseInterface class
 * @class
 * @classdesc DatabaseInterface class is a class that is used to interact with the database.
 * @param { string } URL - The URL of the database.
 * @returns { void }
 * @example
 * const db = new DatabaseInterface("http://localhost:3000");
 * const response = db.CREATE("users",{ name: "John Doe" });
 * console.log(response);
 * @example
 * const db = new DatabaseInterface("http://localhost:3000");
 * const response = db.READ("users","John Doe");
 * console.log(response);
 * @example
 * const db = new DatabaseInterface("http://localhost:3000");
 * const response = db.UPDATE("users",{ name: "John Doe" });
 * console.log(response);
 * @example
 *
 * const db = new DatabaseInterface("http://localhost:3000");
 * const response = db.DELETE("users","John Doe");
 * console.log(response);
 **/
export default class DatabaseInterface {
  url: string | undefined;

  constructor(URL?: string | undefined) {
    this.url = URL || "http://localhost:3000";
  }

  /**
   * Creates a new resource in the database
   * @returns {Promise<{ result: TResponse | undefined, error: string | undefined }>}
   */
  CREATE = async <TRequest, TResponse>(
    resourceEndpoint: string,
    resource: TRequest
  ): Promise<{ result: TResponse | undefined; error: string | undefined }> => {
    try {
      const response = await axios.post<TRequest, { data: TResponse}>(
        `${this.url}/${resourceEndpoint}`,
        resource
      );
      return { result: response.data, error: undefined };
    } catch (e: any) {
      return { result: undefined, error: e };
    }
  };

  /**
   * @returns {Promise<{ result: TResponse | undefined, error: string | undefined }>}
   */
  READ = async <TResponse>(
    resourceEndpoint: string
  ): Promise<{ result: TResponse | undefined; error: string | undefined }> => {
    try {
      const response = await axios.get<TResponse>(`${this.url}/${resourceEndpoint}`);
      return { result: response.data, error: undefined };
    } catch (error: any) {
      return { result: undefined, error };
    }
  };

  /**
   * @returns {Promise<{ result: TResponse | undefined, error: string | undefined }>}
   */
  UPDATE = async <TRequest, TResponse>(
    resourceEndpoint: string,
    resource: TRequest
  ): Promise<{ result: TResponse | undefined; error: string | undefined }> => {
    try {
      const response = await axios.patch<TRequest, { data: TResponse }>(
        `${this.url}/${resourceEndpoint}`,
        resource
      );
      return { result: response.data, error: undefined };
    } catch (error: any) {
      return { result: undefined, error};
    }
  };

  /**
   * @returns {Promise<{ result: TResponse | undefined, error: string | undefined }>}
   */
  DELETE = async <TResponse>(
    resourceEndpoint: string
  ): Promise<{ result: TResponse | undefined; error: string | undefined }> => {
    try {
      const response = await axios.delete<TResponse>(
        `${this.url}/${resourceEndpoint}`
      );
      return { result: response.data, error: undefined };
    } catch (error: any) {
      return { result: undefined, error };
    }
  };

  /**
   * Streams a resource from the database using SSE (EventSource)
   * Usage:
   *   const stream = db.CREATE_STREAM("recommendations/stream", payload);
   *   stream.onData(chunk => { ... });
   *   stream.close();
   */
  CREATE_STREAM = <TRequest>(resourceEndpoint: string, resource: TRequest) => {
    // Compose the full URL
    const url = `${this.url}/${resourceEndpoint}`;

    // We'll use fetch with ReadableStream for POST streaming (SSE)
    let controller: AbortController | null = new AbortController();

    let listeners: Array<(chunk: string) => void> = [];

    // Start the stream
    const start = async () => {
      const response = await fetch(url, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Accept: "text/event-stream",
        },
        body: JSON.stringify(resource),
        signal: controller?.signal,
      });

      if (!response.body) return;

      const reader = response.body.getReader();
      const decoder = new TextDecoder("utf-8");
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });

        // Parse SSE events
        let lines = buffer.split("\n");
        buffer = lines.pop() || "";
        for (const line of lines) {
          if (line.startsWith("data:")) {
            const chunk = line.replace(/^data:\s*/, "");
            listeners.forEach((cb) => cb(chunk));
          }
        }
      }
    };

    // Start the stream in background
    start();

    return {
      onData: (cb: (chunk: string) => void) => {
        listeners.push(cb);
      },
      close: () => {
        if (controller) {
          controller.abort();
          controller = null;
        }
      },
    };
  };
}
