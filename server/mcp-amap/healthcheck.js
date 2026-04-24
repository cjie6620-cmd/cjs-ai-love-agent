const MCP_URL = process.env.AMAP_MCP_URL || "http://127.0.0.1:3100/mcp";
const PROTOCOL_VERSION = "2025-03-26";

function buildHeaders(sessionId) {
  const headers = {
    Accept: "application/json, text/event-stream",
    "Content-Type": "application/json",
    "MCP-Protocol-Version": PROTOCOL_VERSION,
  };
  if (sessionId) {
    headers["Mcp-Session-Id"] = sessionId;
  }
  return headers;
}

async function sendRpc(payload, sessionId) {
  const response = await fetch(MCP_URL, {
    method: "POST",
    headers: buildHeaders(sessionId),
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    throw new Error(`HTTP ${response.status}`);
  }

  const rawBody = await response.text();
  const body = rawBody ? JSON.parse(rawBody) : null;
  return {
    body,
    sessionId: response.headers.get("mcp-session-id") || sessionId,
  };
}

async function main() {
  const initializeId = "health-init";
  const initResponse = await sendRpc([
    {
      jsonrpc: "2.0",
      id: initializeId,
      method: "initialize",
      params: {
        protocolVersion: PROTOCOL_VERSION,
        capabilities: {},
        clientInfo: {
          name: "docker-healthcheck",
          version: "1.0.0",
        },
      },
    },
  ]);

  if (!initResponse.sessionId) {
    throw new Error("missing session id");
  }

  const initPayload = Array.isArray(initResponse.body) ? initResponse.body[0] : initResponse.body;
  if (!initPayload?.result?.protocolVersion) {
    throw new Error("initialize failed");
  }

  await sendRpc(
    [
      {
        jsonrpc: "2.0",
        method: "notifications/initialized",
      },
    ],
    initResponse.sessionId,
  );

  const listResponse = await sendRpc(
    [
      {
        jsonrpc: "2.0",
        id: "health-tools",
        method: "tools/list",
        params: {},
      },
    ],
    initResponse.sessionId,
  );

  const listPayload = Array.isArray(listResponse.body) ? listResponse.body[0] : listResponse.body;
  const tools = listPayload?.result?.tools;
  if (!Array.isArray(tools) || tools.length === 0) {
    throw new Error("tool list is empty");
  }

  await fetch(MCP_URL, {
    method: "DELETE",
    headers: buildHeaders(initResponse.sessionId),
  });
}

main().catch((error) => {
  console.error("Amap MCP healthcheck failed:", error);
  process.exit(1);
});
