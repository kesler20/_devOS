import React from "react";
import { NoSQLDbServiceResourceType } from "@lib/types";
import axios from "axios";
import toastFactory, {
  MessageSeverity,
} from "./components/notification/ToastMessages";

const dbUrl = import.meta.env.VITE_PROD_BACKEND_URL;

const DB_ARRAY_KEY = "key";

const safeJsonParse = (value: string) => {
  try {
    return JSON.parse(value);
  } catch (error) {
    console.error("Failed to parse JSON value", error);
    return undefined;
  }
};

const prepareResourceContent = (resourceContent: string) => {
  const parsedContent = safeJsonParse(resourceContent);
  if (parsedContent === undefined) {
    return resourceContent;
  }

  const normalizedContent = unwrapLegacyArrayValue(parsedContent);

  if (Array.isArray(normalizedContent)) {
    return JSON.stringify({ [DB_ARRAY_KEY]: normalizedContent });
  }

  if (normalizedContent === undefined) {
    return resourceContent;
  }

  return JSON.stringify(normalizedContent);
};

const unwrapLegacyArrayValue = (value: unknown) => {
  if (
    value &&
    typeof value === "object" &&
    !Array.isArray(value) &&
    Object.prototype.hasOwnProperty.call(value, DB_ARRAY_KEY)
  ) {
    const legacy = (value as Record<string, unknown>)[DB_ARRAY_KEY];
    if (Array.isArray(legacy)) {
      return legacy;
    }
  }
  return value;
};

const normalizeDbReadPayload = (data: unknown) => {
  let parsedData: unknown =
    typeof data === "string" ? safeJsonParse(data) ?? data : data;

  parsedData = unwrapLegacyArrayValue(parsedData);

  if (parsedData === undefined) {
    return undefined;
  }

  if (typeof parsedData === "string") {
    return parsedData;
  }

  return JSON.stringify(parsedData);
};

// ================== //
//                    //
//   CRUD FROM DB     //
//                    //
// ================== //

// @see server.ts
export const createResourceInDb = async <TResponse>(
  resourcePath: string,
  resourceName: string,
  resourceContent: string
) => {
  const payload = prepareResourceContent(resourceContent);
  try {
    const response = await axios.post<
      NoSQLDbServiceResourceType,
      { data: TResponse }
    >(`${dbUrl}/${resourcePath}`, {
      resourceName,
      resourceContent: payload,
    });
    const result = response.data;
    return { result, error: undefined };
  } catch (e: any) {
    return { result: undefined, error: e };
  }
};

export const readResourceInDb = async <TResponse>(
  resourcePath: string,
  resourceName: string
) => {
  try {
    const response = await axios.get<unknown>(
      `${dbUrl}/${resourcePath}/${resourceName}`
    );
    const result = normalizeDbReadPayload(response.data) as TResponse;
    return { result, error: undefined };
  } catch (error: any) {
    return { result: undefined, error };
  }
};

export const deleteResourceInDb = async <TResponse>(
  resourcePath: string,
  resourceName: string
) => {
  try {
    const response = await axios.delete<TResponse>(
      `${dbUrl}/${resourcePath}/${resourceName}`
    );
    const result = response.data;
    return { result, error: undefined };
  } catch (error: any) {
    return { result: undefined, error };
  }
};

export const getResourceFromCache = <T>(key: string): T | undefined => {
  try {
    const item = localStorage.getItem(key);
    if (item) {
      const parsed = JSON.parse(item);
      const result = unwrapLegacyArrayValue(parsed) as T;
      return result;
    }
    return undefined;
  } catch (error) {
    console.error(`Error getting item ${key} from localStorage`, error);
    return undefined;
  }
};

export type ShortCut = {
  shortcut: string[];
  callback: () => void;
};

/**
 * custom hook to handle keyboard shortcuts
 * @param {*} commands
 * @param {*} deps
 * @returns
 * @example
 * const commands = [
 *  {
 *   shortcut: ["Control", "Shift", "S"],
 *  callback: () => {
 *   console.log("Control + Shift + S");
 * },
 * },
 * {
 * shortcut: ["Control", "Shift", "A"],
 * callback: () => {
 * console.log("Control + Shift + A");
 * },
 * },
 * {
 * shortcut: ["Control", "Shift", "D"],
 * callback: () => {
 * console.log("Control + Shift + D");
 * },
 * },
 * ];
 * useKeyboardShortcuts(commands);
 */
export function useKeyboardShortcuts(
  commands: ShortCut[],
  deps: React.DependencyList = []
) {
  React.useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      const pressedKeys = [
        event.ctrlKey ? "Control" : "",
        event.shiftKey ? "Shift" : "",
        event.altKey ? "Alt" : "",
        event.key.toUpperCase(),
      ].filter(Boolean);

      commands.forEach(({ shortcut, callback }) => {
        if (JSON.stringify(pressedKeys) === JSON.stringify(shortcut)) {
          event.preventDefault();
          callback();
        }
      });
    };

    window.addEventListener("keydown", handleKeyDown);

    return () => {
      window.removeEventListener("keydown", handleKeyDown);
    };
  }, [commands, ...deps]);
}

/**
 * custom hook to store values which persist in storage and the state of the context
 * @param {*} defaultValue
 * @param {*} resourcePath
 * @param {*} resourceName
 * @returns
 */
export const useCachedValue = <T>(
  username: string,
  defaultValue: T,
  key: string
): [T, React.Dispatch<React.SetStateAction<T>>] => {
  const validKey = `${username}_${key}`;

  const [value, setValue] = React.useState(() => {
    const storedState = getResourceFromCache(validKey);
    console.log(
      `global state - ${validKey}`,
      storedState === undefined ? defaultValue : (storedState as T)
    );
    return storedState === undefined ? defaultValue : (storedState as T);
  });
  React.useEffect(() => {
    // Persist raw value for generic key/value storage
    try {
      localStorage.setItem(validKey, JSON.stringify(value));
    } catch (error) {
      console.error(`Error setting item ${validKey} in localStorage`, error);
    }
  }, [validKey, value]);
  return [value as T, setValue];
};

export const useStoredValue = <T>(
  username: string,
  defaultValue: T,
  key: string,
  pageLimit?: number
): [T, React.Dispatch<React.SetStateAction<T>>, boolean] => {
  const [value, setValue] = React.useState<T>(defaultValue);
  const [isLoading, setIsLoading] = React.useState<boolean>(true);

  // initial load
  React.useEffect(() => {
    readResourceInDb<string>(username, key).then(({ result, error }) => {
      if (error) {
        console.error(`Error reading ${key} from database`, error);
        toastFactory(`Failed to load ${key} from database`, MessageSeverity.ERROR);
      }
      if (result) {
        const parsed = JSON.parse(result) as T;
        if (pageLimit && Array.isArray(parsed)) {
          const limited = parsed.slice(0, pageLimit) as unknown as T;
          setValue(limited);
        } else {
          setValue(parsed);
        }
      }
      setIsLoading(false);
    });
  }, []);

  // persist on change
  React.useEffect(() => {
    if (isLoading) return;
    const content = JSON.stringify(value);
    createResourceInDb<string>(username, key, content).then(({ result, error }) => {
      if (error) {
        console.error(`Error saving ${key} to database`, error);
        toastFactory(`Failed to save ${key} to database`, MessageSeverity.ERROR);
      }
      if (result) {
        console.log(`Successfully saved ${key} to database`);
      }
    });
  }, [value, isLoading]);

  return [value, setValue, isLoading];
};
