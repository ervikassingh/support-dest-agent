/**
 * MCP tool server factory.
 *
 * READ: get_order, get_shipping_status, check_refund_eligibility, get_customer
 * WRITE (scoped): issue_refund (requires approval_id), escalate_to_human
 *
 * Shared in-memory store so every HTTP client (this agent or others) sees the same orders.
 */
import { randomUUID } from "node:crypto";
import { McpServer } from "@modelcontextprotocol/server";
import * as z from "zod/v4";
import {
  checkRefundEligibility,
  getCustomer,
  getOrder,
  ORDERS,
  REFUNDS,
} from "./data.js";

function text(payload: unknown) {
  return {
    content: [{ type: "text" as const, text: JSON.stringify(payload, null, 2) }],
  };
}

function err(message: string) {
  return text({ error: message });
}

export function createSupportDeskMcpServer() {
  const server = new McpServer({
    name: "support-desk",
    version: "0.1.0",
  });

  server.registerTool(
    "get_order",
    {
      description: "[read] Order by id: items, totals, status, customer",
      inputSchema: z.object({ order_id: z.string() }),
    },
    async ({ order_id }) => {
      const order = getOrder(order_id);
      return order ? text(order) : err(`Order ${order_id} not found`);
    },
  );

  server.registerTool(
    "get_shipping_status",
    {
      description: "[read] Carrier status and timestamps",
      inputSchema: z.object({ order_id: z.string() }),
    },
    async ({ order_id }) => {
      const order = getOrder(order_id);
      if (!order) return err(`Order ${order_id} not found`);
      return text({
        order_id,
        status: order.status,
        carrier_status: order.carrier_status,
        tracking: order.tracking,
        shipped_at: order.shipped_at,
        delivered_at: order.delivered_at,
      });
    },
  );

  server.registerTool(
    "check_refund_eligibility",
    {
      description: "[read] Window, prior refunds, item eligibility, max amount",
      inputSchema: z.object({ order_id: z.string() }),
    },
    async ({ order_id }) => text(checkRefundEligibility(order_id)),
  );

  server.registerTool(
    "get_customer",
    {
      description: "[read] Customer record and recent orders",
      inputSchema: z.object({ customer_id: z.string() }),
    },
    async ({ customer_id }) => {
      const customer = getCustomer(customer_id);
      return customer ? text(customer) : err(`Customer ${customer_id} not found`);
    },
  );

  server.registerTool(
    "issue_refund",
    {
      description:
        "[write,scoped] Posts the approved amount. Rejects calls with no approval_id.",
      inputSchema: z.object({
        order_id: z.string(),
        amount: z.number(),
        approval_id: z.string().optional(),
        reason: z.string().optional(),
      }),
    },
    async ({ order_id, amount, approval_id, reason }) => {
      if (!approval_id?.trim()) {
        return err(
          "issue_refund refused: missing approval_id. Human approval context is required before this write tool may run.",
        );
      }

      const eligibility = checkRefundEligibility(order_id);
      if (!eligibility.eligible) {
        return err(String(eligibility.reason ?? "Not eligible"));
      }

      const maxAmount = Number(eligibility.max_amount ?? 0);
      if (amount <= 0 || amount > maxAmount) {
        return err(`Amount ${amount} outside eligible max ${maxAmount}`);
      }

      const refundId = `REF-${randomUUID().slice(0, 8)}`;
      const record = {
        refund_id: refundId,
        order_id,
        amount,
        approval_id,
        reason,
        status: "posted",
      };
      REFUNDS[refundId] = record;
      if (ORDERS[order_id]) {
        ORDERS[order_id].already_refunded = true;
        ORDERS[order_id].prior_refund_id = refundId;
      }
      return text(record);
    },
  );

  server.registerTool(
    "escalate_to_human",
    {
      description: "[write] Hands the thread to a person with a short summary",
      inputSchema: z.object({
        thread_id: z.string(),
        summary: z.string(),
      }),
    },
    async ({ thread_id, summary }) =>
      text({
        escalated: true,
        thread_id,
        summary,
        queue: "human-support-stub",
      }),
  );

  return server;
}
