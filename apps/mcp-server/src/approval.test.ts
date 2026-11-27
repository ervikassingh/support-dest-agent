import assert from "node:assert/strict";
import { createHmac } from "node:crypto";
import test from "node:test";
import { approvalId, approvalMatches } from "./approval.js";

test("approval id is the hmac of order and cents", () => {
  const mac = createHmac("sha256", "dev-approval-secret").update("ORD-1001:4999").digest("hex");
  assert.equal(approvalId("ORD-1001", 49.99), `APR-${mac}`);
  assert.equal(approvalMatches("ORD-1001", 49.99, `APR-${mac}`), true);
  assert.equal(approvalMatches("ORD-1001", 49.99, "APR-not-a-real-approval"), false);
  assert.equal(approvalMatches("ORD-1001", 10, `APR-${mac}`), false);
});
