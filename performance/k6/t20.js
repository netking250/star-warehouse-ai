import http from "k6/http";
import { check, group, sleep } from "k6";
import { Rate, Trend } from "k6/metrics";

const profile = (__ENV.T20_PROFILE || "SMOKE").toUpperCase();
const baseUrl = (__ENV.BASE_URL || "").replace(/\/$/, "");
const username = __ENV.T20_USERNAME || "";
const password = __ENV.T20_PASSWORD || "";
const tenantId = __ENV.T20_TENANT_ID || "";

const operationFailures = new Rate("t20_operation_failures");
const healthLatency = new Trend("t20_health_latency", true);
const authenticatedReadLatency = new Trend("t20_authenticated_read_latency", true);

const profiles = {
  SMOKE: {
    scenarios: {
      smoke: {
        executor: "constant-vus",
        vus: 1,
        duration: "10s",
      },
    },
  },
  BASELINE: {
    scenarios: {
      baseline: {
        executor: "ramping-vus",
        startVUs: 0,
        stages: [
          { duration: "10s", target: 5 },
          { duration: "20s", target: 5 },
          { duration: "5s", target: 0 },
        ],
        gracefulRampDown: "5s",
      },
    },
  },
  SOAK_SHORT: {
    scenarios: {
      soakShort: {
        executor: "constant-vus",
        vus: 3,
        duration: "2m",
      },
    },
  },
};

if (!Object.prototype.hasOwnProperty.call(profiles, profile)) {
  throw new Error(`Unsupported T20_PROFILE: ${profile}`);
}
if (!baseUrl) {
  throw new Error("BASE_URL is required");
}
if (profile !== "SMOKE" && (!username || !password || !tenantId)) {
  throw new Error("BASELINE and SOAK_SHORT require T20_USERNAME, T20_PASSWORD, and T20_TENANT_ID");
}

export const options = {
  ...profiles[profile],
  discardResponseBodies: true,
  summaryTrendStats: ["avg", "med", "p(90)", "p(95)", "p(99)", "max"],
  thresholds: {
    checks: ["rate>0.99"],
    t20_operation_failures: ["rate<0.01"],
  },
};

export function setup() {
  if (!username) {
    return { token: "" };
  }
  const response = http.post(
    `${baseUrl}/api/v1/login`,
    JSON.stringify({ username, password, tenant_id: tenantId }),
    {
      headers: { "Content-Type": "application/json" },
      tags: { operation: "session_mutation" },
      timeout: "10s",
      responseType: "text",
    },
  );
  const accepted = check(response, {
    "session mutation succeeded": (result) => result.status === 200,
  });
  if (!accepted) {
    throw new Error(`Load fixture login failed with HTTP ${response.status}`);
  }
  return { token: response.json("access_token") };
}

export default function (data) {
  group("health", () => {
    const response = http.get(`${baseUrl}/health`, {
      tags: { operation: "health" },
      timeout: "5s",
    });
    healthLatency.add(response.timings.duration);
    const accepted = check(response, {
      "health returns 200": (result) => result.status === 200,
    });
    operationFailures.add(!accepted);
  });

  if (data.token) {
    group("authenticated read", () => {
      const response = http.get(`${baseUrl}/api/v1/me`, {
        headers: { Authorization: `Bearer ${data.token}` },
        tags: { operation: "authenticated_read" },
        timeout: "10s",
      });
      authenticatedReadLatency.add(response.timings.duration);
      const accepted = check(response, {
        "authenticated read returns 200": (result) => result.status === 200,
      });
      operationFailures.add(!accepted);
    });
  }

  sleep(0.2);
}
