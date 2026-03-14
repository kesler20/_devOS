import Redis from "ioredis";
import redisTsDbCredentials from "../../credentials/redisTsDbCredentials";

export type ResolutionType = "second" | "minute" | "hour" | "day" | "week";

/**
 * Adapter for Redis Time Series database
 * @class
 * @export
 * @version 1.0.0
 * @example
 * ```typescript
 * const tsClient = new RedisTimeSeriesClient();
 *
 * // Create a key with a retention time of 1 hour (3600000 ms)
 * await tsClient.createKey('temperature', 3600000);
 *
 * // Store some data points
 * await tsClient.store('temperature', Date.now(), 22.5);
 *
 * // Query data from the past 1 hour with 1-minute aggregation
 * const data = await tsClient.query('temperature', 3600000, 'minutes');
 * console.log('Aggregated Data (1-minute resolution):', data);
 *
 * // Query data from the past 10 seconds without aggregation
 * const rawData = await tsClient.query('temperature', 10000, 'seconds');
 * console.log('Raw Data (no aggregation):', rawData);
 *
 * // Delete old data from the past 1 hour
 * await tsClient.delete('temperature', Date.now() - 3600000, Date.now() - 1800000);
 *
 * await tsClient.close();
 * ```
 */
export class RedisTimeSeriesAdapter {
  private client: Redis;

  constructor() {
    this.client = new Redis({
      host: redisTsDbCredentials.socket.host,
      port: redisTsDbCredentials.socket.port,
      password: redisTsDbCredentials.password,
    });
  }

  /**
   * Store time series data (TS.ADD)
   * @param key - The name of the time series.
   * @param timestamp - Timestamp for the data point (in milliseconds).
   * @param value - The value to store.
   */
  async store(key: string, timestamp: number, value: number): Promise<void> {
    console.log("Set", key, timestamp, value);
    await this.client.call("TS.ADD", key, timestamp, value);
  }

  /**
   * Query time series data (TS.RANGE) with optional aggregation
   * @param key - The name of the time series.
   * @param offset - How far back to retrieve data (in seconds).
   * @param resolution - Aggregation resolution (seconds, minutes, hours).
   *
   */
  async query(
    key: string,
    offset: number, // in seconds
    resolution: ResolutionType,
  ): Promise<[number, number][]> {
    const now = Date.now(); // ms
    const from = now - offset * 1000;

    console.log("Get", key, from, resolution);

    const bucketSize = this.getBucketSize(resolution);
    if (!bucketSize) throw new Error("Invalid resolution passed");

    const raw = (await this.client.call(
      "TS.RANGE",
      key,
      from,
      now,
      "AGGREGATION",
      "avg",
      bucketSize,
    )) as [string, string][];

    return raw.map(([ts, value]) => [Number(ts), Number(value)]);
  }

  // Helper function to get bucket size in milliseconds based on the resolution
  private getBucketSize(resolution: ResolutionType): number | null {
    switch (resolution) {
      case "second":
        return 1_000; // 1 second in milliseconds
      case "minute":
        return 60 * 1_000; // 1 minute in milliseconds
      case "hour":
        return 60 * 60 * 1_000; // 1 hour in milliseconds
      case "day":
        return 24 * 60 * 60 * 1_000; // 1 day in milliseconds
      case "week":
        return 7 * 24 * 60 * 60 * 1_000; // 1 week in milliseconds
      default:
        return null; // No aggregation if resolution is not specified
    }
  }

  /**
   * Delete time series data (TS.DEL)
   * @param key - The name of the time series.
   * @param from - The starting timestamp (in milliseconds).
   * @param to - The ending timestamp (in milliseconds).
   */
  async delete(key: string, from: number, to: number): Promise<void> {
    console.log("Delete", key, from, to);
    await this.client.call("TS.DEL", key, from, to);
  }

  /**
   * Create time series key (TS.CREATE) with optional retention time
   * @param key - The name of the time series.
   * @param retentionTime - retention time for the series (in milliseconds).
   */
  async createKey(key: string, retentionTime: number): Promise<void> {
    await this.client.call("TS.CREATE", key, "RETENTION", retentionTime.toString());
  }

  // Close Redis connection
  async close(): Promise<void> {
    await this.client.quit();
  }
}

// const queryRedis = async () => {
//   const tsDb = new RedisTimeSeriesAdapter();
//   const response = await tsDb.query(
//     "ts:production/D73/device/AKTA_PCC Emulator/1.0/outputs/uv_elution/uv280",
//     10 * 60*60,
//     "minute"
//   );
//   console.log(response.map((res, index) => {
//     return {
//       index,
//       timeStamp: new Date(res[0]).toTimeString(),
//       value: res[1]
//     }
//   }))
//   tsDb.close();
// };

// queryRedis().then(() => console.log("done"));
