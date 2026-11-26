/** In-memory stub catalog — a few fake orders covering common edges. */

export type Order = {
  order_id: string;
  customer_id: string;
  status: string;
  total: number;
  currency: string;
  items: Array<{ sku: string; name: string; qty: number; price: number }>;
  shipped_at?: string | null;
  delivered_at?: string | null;
  carrier_status?: string;
  tracking?: string;
  return_window_days: number;
  already_refunded: boolean;
  prior_refund_id?: string;
  note?: string;
};

export type Customer = {
  customer_id: string;
  name: string;
  email: string;
  recent_order_ids: string[];
};

export const CUSTOMERS: Record<string, Customer> = {
  "CUS-1": {
    customer_id: "CUS-1",
    name: "Alex Rivera",
    email: "alex@example.com",
    recent_order_ids: ["ORD-1001", "ORD-1003"],
  },
  "CUS-2": {
    customer_id: "CUS-2",
    name: "Jordan Lee",
    email: "jordan@example.com",
    recent_order_ids: ["ORD-1002"],
  },
  "CUS-GUEST": {
    customer_id: "CUS-GUEST",
    name: "Guest Checkout",
    email: "guest@example.com",
    recent_order_ids: ["ORD-1004"],
  },
};

export const ORDERS: Record<string, Order> = {
  "ORD-1001": {
    order_id: "ORD-1001",
    customer_id: "CUS-1",
    status: "delivered",
    total: 49.99,
    currency: "USD",
    items: [{ sku: "MUG-01", name: "Ceramic Mug", qty: 1, price: 49.99 }],
    shipped_at: "2026-11-10T12:00:00Z",
    delivered_at: "2026-11-14T18:00:00Z",
    return_window_days: 30,
    already_refunded: false,
  },
  "ORD-1002": {
    order_id: "ORD-1002",
    customer_id: "CUS-2",
    status: "in_transit",
    total: 129.0,
    currency: "USD",
    items: [{ sku: "BAG-02", name: "Tote Bag", qty: 2, price: 64.5 }],
    shipped_at: "2026-11-20T09:00:00Z",
    delivered_at: null,
    carrier_status: "Out for delivery",
    tracking: "1Z999AA10123456784",
    return_window_days: 30,
    already_refunded: false,
  },
  "ORD-1003": {
    order_id: "ORD-1003",
    customer_id: "CUS-1",
    status: "delivered",
    total: 899.0,
    currency: "USD",
    items: [{ sku: "WATCH-9", name: "High-value Watch", qty: 1, price: 899.0 }],
    shipped_at: "2026-09-01T12:00:00Z",
    delivered_at: "2026-09-05T12:00:00Z",
    return_window_days: 30,
    already_refunded: false,
    note: "outside return window (stub)",
  },
  "ORD-1004": {
    order_id: "ORD-1004",
    customer_id: "CUS-GUEST",
    status: "delivered",
    total: 24.0,
    currency: "USD",
    items: [{ sku: "SOCK-3", name: "Socks", qty: 3, price: 8.0 }],
    shipped_at: "2026-11-01T12:00:00Z",
    delivered_at: "2026-11-04T12:00:00Z",
    return_window_days: 30,
    already_refunded: true,
    prior_refund_id: "REF-9",
  },
};

export const REFUNDS: Record<string, Record<string, unknown>> = {};

export function getOrder(orderId: string): Order | null {
  const order = ORDERS[orderId];
  return order ? structuredClone(order) : null;
}

export function getCustomer(customerId: string): Customer | null {
  const customer = CUSTOMERS[customerId];
  return customer ? structuredClone(customer) : null;
}

export function checkRefundEligibility(orderId: string) {
  const order = getOrder(orderId);
  if (!order) {
    return { eligible: false, reason: `Order ${orderId} not found`, max_amount: 0 };
  }
  if (order.already_refunded) {
    return {
      eligible: false,
      reason: "Order already refunded",
      max_amount: 0,
      prior_refund_id: order.prior_refund_id,
    };
  }
  if (order.status === "in_transit") {
    return {
      eligible: false,
      reason: "Order still in transit; wait until delivered",
      max_amount: 0,
    };
  }
  if (order.note === "outside return window (stub)") {
    return {
      eligible: false,
      reason: "Outside return window",
      max_amount: 0,
    };
  }
  return {
    eligible: true,
    reason: "Within return window and not previously refunded",
    max_amount: order.total,
    order_id: orderId,
  };
}
