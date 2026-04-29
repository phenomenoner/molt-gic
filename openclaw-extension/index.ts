import type { OpenClawPluginApi } from "openclaw/plugin-sdk/core";
import { createHash } from "node:crypto";

type Config = { enabled?: boolean; routePath?: string };

type SmokePayload = {
  kind?: unknown;
  route?: unknown;
  receipt_id?: unknown;
};

function readBody(req: any): Promise<Buffer> {
  return new Promise((resolve, reject) => {
    const chunks: Buffer[] = [];
    req.on("data", (chunk: Buffer | string) => chunks.push(Buffer.isBuffer(chunk) ? chunk : Buffer.from(chunk)));
    req.on("end", () => resolve(Buffer.concat(chunks)));
    req.on("error", reject);
  });
}

function json(res: any, status: number, payload: unknown) {
  const body = Buffer.from(JSON.stringify(payload));
  res.statusCode = status;
  res.setHeader("content-type", "application/json");
  res.setHeader("content-length", String(body.length));
  res.end(body);
}

function buildReceipt(routePath: string, payload: SmokePayload, rawBody: Buffer) {
  return {
    status: "ok",
    schema: "molt-gic.gateway-hook.receipt.v1",
    route: routePath,
    kind: typeof payload.kind === "string" ? payload.kind : "unknown",
    receipt_id: typeof payload.receipt_id === "string" ? payload.receipt_id : null,
    body_hash: createHash("sha256").update(rawBody).digest("hex"),
    ts: new Date().toISOString(),
  };
}

function buildRpcReceipt(routePath: string, params: Record<string, unknown> | undefined) {
  const payload = {
    kind: typeof params?.kind === "string" ? params.kind : "molt_gic_rpc_smoke",
    route: typeof params?.route === "string" ? params.route : "gateway-rpc",
    receipt_id: typeof params?.receipt_id === "string" ? params.receipt_id : `rpc_${Date.now().toString(36)}`,
  };
  const body = Buffer.from(JSON.stringify(payload));
  return buildReceipt(routePath, payload, body);
}

export default function register(api: OpenClawPluginApi) {
  const cfg = (api.pluginConfig ?? {}) as Config;
  if (cfg.enabled === false) return;
  const routePath = typeof cfg.routePath === "string" && cfg.routePath.startsWith("/") ? cfg.routePath : "/molt-gic/hook";

  api.registerHttpRoute({
    path: routePath,
    auth: "gateway",
    match: "exact",
    replaceExisting: true,
    async handler(req, res) {
      if (req.method !== "POST") {
        json(res, 405, { status: "error", error: "method_not_allowed" });
        return true;
      }
      const body = await readBody(req);
      let payload: SmokePayload = {};
      try {
        payload = body.length ? JSON.parse(body.toString("utf8")) : {};
      } catch {
        json(res, 400, { status: "error", error: "invalid_json" });
        return true;
      }
      json(res, 200, buildReceipt(routePath, payload, body));
      return true;
    },
  });

  api.registerGatewayMethod("moltGic.status", async ({ respond }) => {
    respond(true, {
      status: "ok",
      schema: "molt-gic.gateway-rpc.status.v1",
      route: routePath,
      http_route: true,
      methods: ["moltGic.status", "moltGic.smoke"],
      runtime_config_mutation: "blocked",
    });
  });

  api.registerGatewayMethod("moltGic.smoke", async ({ params, respond }) => {
    respond(true, buildRpcReceipt(routePath, (params ?? {}) as Record<string, unknown>));
  });

  api.logger.info(`molt-gic-openclaw-extension: registered HTTP route ${routePath} and Gateway RPC methods`);
}
