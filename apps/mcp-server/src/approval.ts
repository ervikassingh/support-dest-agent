/**
 * Same construction as apps/agent/src/agent/tools/approval.py.
 * shortcut: default secret matches the agent; set APPROVAL_SECRET on both before exposing MCP.
 */
import { createHmac, timingSafeEqual } from "node:crypto";

function secret(): string {
  return process.env.APPROVAL_SECRET || "dev-approval-secret";
}

export function approvalId(orderId: string, amount: number): string {
  const cents = Math.round(amount * 100);
  const mac = createHmac("sha256", secret()).update(`${orderId}:${cents}`).digest("hex");
  return `APR-${mac}`;
}

export function approvalMatches(
  orderId: string,
  amount: number,
  given: string | undefined,
): boolean {
  if (!given?.trim()) return false;
  const expected = Buffer.from(approvalId(orderId, amount));
  const actual = Buffer.from(given.trim());
  if (expected.length !== actual.length) return false;
  return timingSafeEqual(expected, actual);
}
