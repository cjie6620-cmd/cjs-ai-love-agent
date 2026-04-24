import { randomUUID } from "node:crypto";
import process from "node:process";

import * as z from "zod/v4";
import { createMcpExpressApp } from "@modelcontextprotocol/sdk/server/express.js";
import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StreamableHTTPServerTransport } from "@modelcontextprotocol/sdk/server/streamableHttp.js";
import { isInitializeRequest } from "@modelcontextprotocol/sdk/types.js";

const HOST = process.env.MCP_HOST || "0.0.0.0";
const PORT = Number(process.env.MCP_PORT || 3100);
const REQUEST_TIMEOUT_MS = Number(process.env.AMAP_REQUEST_TIMEOUT_MS || 10000);
const AMAP_API_KEY = process.env.AMAP_MAPS_API_KEY?.trim();

if (!AMAP_API_KEY) {
  console.error("AMAP_MAPS_API_KEY environment variable is required.");
  process.exit(1);
}

const sessionContexts = new Map();

function buildToolResult(payload) {
  return {
    content: [
      {
        type: "text",
        text: JSON.stringify(payload, null, 2),
      },
    ],
    structuredContent: payload,
  };
}

function buildToolError(message) {
  return {
    content: [
      {
        type: "text",
        text: message,
      },
    ],
    isError: true,
  };
}

function formatError(error) {
  return error instanceof Error ? error.message : String(error);
}

async function fetchAmapJson(path, params = {}) {
  const url = new URL(path, "https://restapi.amap.com");
  url.searchParams.set("key", AMAP_API_KEY);
  url.searchParams.set("source", "ai_love_mcp");

  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null || value === "") {
      continue;
    }
    url.searchParams.set(key, String(value));
  }

  const response = await fetch(url, {
    signal: AbortSignal.timeout(REQUEST_TIMEOUT_MS),
  });
  if (!response.ok) {
    throw new Error(`HTTP ${response.status}`);
  }

  return response.json();
}

function extractAmapError(data) {
  return String(
    data?.info ||
      data?.errmsg ||
      data?.errdetail ||
      data?.infocode ||
      data?.errcode ||
      "unknown error",
  );
}

function createAmapToolHandler(label, path, buildParams, options = {}) {
  const isSuccess = options.isSuccess || ((data) => String(data?.status) === "1");

  return async (args) => {
    try {
      const data = await fetchAmapJson(path, buildParams(args));
      if (!isSuccess(data)) {
        return buildToolError(`${label} failed: ${extractAmapError(data)}`);
      }
      return buildToolResult(data);
    } catch (error) {
      return buildToolError(`${label} failed: ${formatError(error)}`);
    }
  };
}

function createAmapServer() {
  const server = new McpServer(
    {
      name: "ai-love-amap-mcp",
      version: "1.0.0",
    },
    {
      capabilities: {
        logging: {},
      },
    },
  );

  server.registerTool(
    "maps_regeocode",
    {
      description: "将一个高德经纬度坐标转换为行政区划地址信息",
      inputSchema: {
        location: z.string().describe("经纬度，格式为：经度,纬度"),
      },
    },
    createAmapToolHandler("Reverse geocode", "/v3/geocode/regeo", ({ location }) => ({
      location,
    })),
  );

  server.registerTool(
    "maps_geo",
    {
      description: "将详细的结构化地址转换为经纬度坐标",
      inputSchema: {
        address: z.string().describe("待解析的结构化地址信息"),
        city: z.string().optional().describe("指定查询的城市"),
      },
    },
    createAmapToolHandler("Geocode", "/v3/geocode/geo", ({ address, city }) => ({
      address,
      city,
    })),
  );

  server.registerTool(
    "maps_ip_location",
    {
      description: "根据 IP 地址定位所属地区",
      inputSchema: {
        ip: z.string().describe("待定位的 IP 地址"),
      },
    },
    createAmapToolHandler("IP location", "/v3/ip", ({ ip }) => ({ ip })),
  );

  server.registerTool(
    "maps_weather",
    {
      description: "根据城市名称或者 adcode 查询天气信息",
      inputSchema: {
        city: z.string().describe("城市名称或者 adcode"),
        extensions: z.enum(["base", "all"]).optional().default("all").describe("天气类型"),
      },
    },
    createAmapToolHandler("Weather", "/v3/weather/weatherInfo", ({ city, extensions }) => ({
      city,
      extensions,
    })),
  );

  server.registerTool(
    "maps_bicycling",
    {
      description: "骑行路径规划",
      inputSchema: {
        origin: z.string().describe("出发点经纬度，格式为：经度,纬度"),
        destination: z.string().describe("目的地经纬度，格式为：经度,纬度"),
      },
    },
    createAmapToolHandler(
      "Bicycling direction",
      "/v4/direction/bicycling",
      ({ origin, destination }) => ({ origin, destination }),
      {
        isSuccess: (data) => Number(data?.errcode) === 0,
      },
    ),
  );

  server.registerTool(
    "maps_direction_walking",
    {
      description: "步行路径规划",
      inputSchema: {
        origin: z.string().describe("出发点经纬度，格式为：经度,纬度"),
        destination: z.string().describe("目的地经纬度，格式为：经度,纬度"),
      },
    },
    createAmapToolHandler("Walking direction", "/v3/direction/walking", ({ origin, destination }) => ({
      origin,
      destination,
    })),
  );

  server.registerTool(
    "maps_direction_driving",
    {
      description: "驾车路径规划",
      inputSchema: {
        origin: z.string().describe("出发点经纬度，格式为：经度,纬度"),
        destination: z.string().describe("目的地经纬度，格式为：经度,纬度"),
      },
    },
    createAmapToolHandler("Driving direction", "/v3/direction/driving", ({ origin, destination }) => ({
      origin,
      destination,
    })),
  );

  server.registerTool(
    "maps_direction_transit_integrated",
    {
      description: "公交/地铁等综合公共交通路径规划",
      inputSchema: {
        origin: z.string().describe("出发点经纬度，格式为：经度,纬度"),
        destination: z.string().describe("目的地经纬度，格式为：经度,纬度"),
        city: z.string().describe("公共交通规划起点城市"),
        cityd: z.string().describe("公共交通规划终点城市"),
      },
    },
    createAmapToolHandler(
      "Transit integrated direction",
      "/v3/direction/transit/integrated",
      ({ origin, destination, city, cityd }) => ({
        origin,
        destination,
        city,
        cityd,
      }),
    ),
  );

  server.registerTool(
    "maps_distance",
    {
      description: "距离测量，支持直线/驾车/步行距离",
      inputSchema: {
        origins: z.string().describe("起点经纬度，可用 | 分隔多个坐标"),
        destination: z.string().describe("终点经纬度"),
        type: z.enum(["0", "1", "3"]).optional().default("1").describe("0 直线，1 驾车，3 步行"),
      },
    },
    createAmapToolHandler("Distance", "/v3/distance", ({ origins, destination, type }) => ({
      origins,
      destination,
      type,
    })),
  );

  server.registerTool(
    "maps_text_search",
    {
      description: "POI 关键词搜索",
      inputSchema: {
        keywords: z.string().describe("搜索关键词"),
        city: z.string().optional().describe("查询城市"),
        types: z.string().optional().describe("POI 类型"),
        citylimit: z.string().optional().default("false").describe("是否限制在指定城市内"),
      },
    },
    createAmapToolHandler("Text search", "/v3/place/text", ({ keywords, city, types, citylimit }) => ({
      keywords,
      city,
      types,
      citylimit,
    })),
  );

  server.registerTool(
    "maps_around_search",
    {
      description: "周边 POI 搜索",
      inputSchema: {
        location: z.string().describe("中心点经纬度"),
        radius: z.string().optional().default("1000").describe("搜索半径，单位米"),
        keywords: z.string().optional().describe("搜索关键词"),
        types: z.string().optional().describe("POI 类型"),
      },
    },
    createAmapToolHandler("Around search", "/v3/place/around", ({ location, radius, keywords, types }) => ({
      location,
      radius,
      keywords,
      types,
    })),
  );

  server.registerTool(
    "maps_search_detail",
    {
      description: "查询 POI 详情",
      inputSchema: {
        id: z.string().describe("POI ID"),
      },
    },
    createAmapToolHandler("Search detail", "/v3/place/detail", ({ id }) => ({ id })),
  );

  return server;
}

function buildJsonRpcError(message, code = -32000) {
  return {
    jsonrpc: "2.0",
    error: {
      code,
      message,
    },
    id: null,
  };
}

function getSessionId(req) {
  return req.get("mcp-session-id")?.trim() || "";
}

function isInitializePayload(body) {
  if (Array.isArray(body)) {
    return body.length === 1 && isInitializeRequest(body[0]);
  }
  return isInitializeRequest(body);
}

function createSessionContext() {
  const server = createAmapServer();
  let transport;

  transport = new StreamableHTTPServerTransport({
    sessionIdGenerator: () => randomUUID(),
    enableJsonResponse: true,
    onsessioninitialized: (sessionId) => {
      sessionContexts.set(sessionId, { server, transport });
    },
  });

  transport.onclose = () => {
    const sessionId = transport.sessionId;
    if (sessionId) {
      sessionContexts.delete(sessionId);
    }
  };

  return { server, transport };
}

const app = createMcpExpressApp({ host: HOST });

app.options("/mcp", (_req, res) => {
  res.setHeader("Access-Control-Allow-Origin", "*");
  res.setHeader("Access-Control-Allow-Methods", "POST, DELETE, OPTIONS");
  res.setHeader("Access-Control-Allow-Headers", "Content-Type, Mcp-Session-Id, MCP-Protocol-Version");
  res.status(204).end();
});

app.post("/mcp", async (req, res) => {
  const sessionId = getSessionId(req);
  if (sessionId) {
    const context = sessionContexts.get(sessionId);
    if (!context) {
      res.status(404).json(buildJsonRpcError("Session not found"));
      return;
    }

    try {
      await context.transport.handleRequest(req, res, req.body);
    } catch (error) {
      console.error(`Failed to handle MCP request for session ${sessionId}:`, error);
      if (!res.headersSent) {
        res.status(500).json(buildJsonRpcError("Internal server error", -32603));
      }
    }
    return;
  }

  if (!isInitializePayload(req.body)) {
    res.status(400).json(buildJsonRpcError("Bad Request: initialize request required"));
    return;
  }

  const { server, transport } = createSessionContext();
  try {
    await server.connect(transport);
    await transport.handleRequest(req, res, req.body);
  } catch (error) {
    console.error("Failed to initialize MCP session:", error);
    try {
      await server.close();
    } catch (closeError) {
      console.error("Failed to close MCP server after bootstrap error:", closeError);
      // ignore close error on bootstrap failure
    }
    if (!res.headersSent) {
      res.status(500).json(buildJsonRpcError("Internal server error", -32603));
    }
  }
});

app.get("/mcp", (_req, res) => {
  res.setHeader("Allow", "POST, DELETE, OPTIONS");
  res.status(405).json(buildJsonRpcError("Method not allowed"));
});

app.delete("/mcp", async (req, res) => {
  const sessionId = getSessionId(req);
  if (!sessionId) {
    res.status(400).json(buildJsonRpcError("Bad Request: missing session id"));
    return;
  }

  const context = sessionContexts.get(sessionId);
  if (!context) {
    res.status(404).json(buildJsonRpcError("Session not found"));
    return;
  }

  try {
    await context.transport.handleRequest(req, res);
  } catch (error) {
    console.error(`Failed to close MCP session ${sessionId}:`, error);
    if (!res.headersSent) {
      res.status(500).json(buildJsonRpcError("Internal server error", -32603));
    }
  }
});

const httpServer = app.listen(PORT, HOST, (error) => {
  if (error) {
    console.error("Failed to start Amap MCP server:", error);
    process.exit(1);
  }
  console.log(`Amap MCP server is listening on http://${HOST}:${PORT}/mcp`);
});

let shuttingDown = false;

async function shutdown() {
  if (shuttingDown) {
    return;
  }
  shuttingDown = true;
  console.log("Shutting down Amap MCP server...");

  const closeTasks = Array.from(sessionContexts.values()).map(async ({ transport }) => {
    try {
      await transport.close();
    } catch (error) {
      console.error("Failed to close transport:", error);
    }
  });
  await Promise.all(closeTasks);
  sessionContexts.clear();

  httpServer.close(() => {
    process.exit(0);
  });
}

process.on("SIGINT", shutdown);
process.on("SIGTERM", shutdown);
