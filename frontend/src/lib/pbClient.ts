import { create, toBinary, fromBinary } from "@bufbuild/protobuf";
import type { Message, GenMessage } from "@bufbuild/protobuf";

const BASE_URL = "http://192.168.1.100:8000";

export async function request<T extends Message, R extends Message>(
  path: string,
  method: "GET" | "POST",
  responseSchema: GenMessage<R>,
  requestSchema?: GenMessage<T>,
  data?: any
): Promise<R> {
  const url = new URL(path, BASE_URL);
  
  const headers: HeadersInit = {
    "Accept": "application/x-protobuf",
  };

  let body: BodyInit | undefined = undefined;

  if (method === "POST" && requestSchema) {
    headers["Content-Type"] = "application/x-protobuf";
    const msg = create(requestSchema, data);
    body = toBinary(requestSchema, msg);
  } else if (method === "GET" && data) {
    // Handle query parameters for GET requests if data is provided
    Object.keys(data).forEach(key => {
      if (data[key] !== undefined && data[key] !== null) {
        url.searchParams.append(key, String(data[key]));
      }
    });
  }

  const response = await fetch(url.toString(), {
    method,
    headers,
    body,
  });

  if (!response.ok) {
    throw new Error(`HTTP error! status: ${response.status}`);
  }

  const arrayBuffer = await response.arrayBuffer();
  return fromBinary(responseSchema, new Uint8Array(arrayBuffer));
}
