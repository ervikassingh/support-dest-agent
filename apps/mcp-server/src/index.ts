/**
 * Long-lived MCP service (Streamable HTTP).
 * Any MCP client — this repo's agent or others — connects to MCP_URL/mcp.
 */
import { createMcpExpressApp } from "@modelcontextprotocol/express";
import { toNodeHandler } from "@modelcontextprotocol/node";
import { createMcpHandler } from "@modelcontextprotocol/server";
import { createSupportDeskMcpServer } from "./create-server.js";

const port = Number(process.env.PORT ?? 8002);
const host = process.env.HOST ?? "0.0.0.0";

const handler = createMcpHandler(() => createSupportDeskMcpServer());
const node = toNodeHandler(handler);

const app = createMcpExpressApp({
  host,
  allowedHosts: ["localhost", "127.0.0.1", "mcp-server", "mcp"],
});

app.get("/health", (_req, res) => {
  res.json({
    status: "ok",
    service: "mcp-server",
    transport: "streamable-http",
    mcp_path: "/mcp",
  });
});

app.all("/mcp", (req, res) => {
  void node(req, res, req.body);
});

app.listen(port, host, () => {
  console.log(`mcp-server listening on http://${host}:${port}`);
  console.log(`  health  GET  /health`);
  console.log(`  mcp     ALL  /mcp`);
});
