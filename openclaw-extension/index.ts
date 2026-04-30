import type { OpenClawPluginApi } from "openclaw/plugin-sdk/core";
import { createHash } from "node:crypto";
import fs from "node:fs";
import path from "node:path";

type Config = {
  enabled?: boolean;
  routePath?: string;
  autonomyDigest?: { enabled?: boolean; path?: string };
  enableEvolveApplyCommands?: boolean;
};

type SmokePayload = { kind?: unknown; route?: unknown; receipt_id?: unknown };

type AutonomyDigest = {
  schema: "molt-gic.autonomy.digest.v1";
  status: "ok";
  updated_at: string;
  last_action: string;
  evaluation: string;
  suggested_evolution: string;
  next_safe_action: string;
  apply_policy: string;
  receipts: Array<Record<string, unknown>>;
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

function safeDigestPath(api: OpenClawPluginApi, cfg: Config): string {
  const configured = cfg.autonomyDigest?.path;
  const rel = typeof configured === "string" && configured.trim() ? configured.trim() : "memory/molt-gic-autonomy-digest.json";
  return api.resolvePath(rel);
}

function defaultDigest(): AutonomyDigest {
  return {
    schema: "molt-gic.autonomy.digest.v1",
    status: "ok",
    updated_at: new Date().toISOString(),
    last_action: "none recorded yet",
    evaluation: "no receipt evaluated yet",
    suggested_evolution: "run /molt-gic smoke or moltGic.smoke to seed the loop",
    next_safe_action: "/molt-gic smoke",
    apply_policy: "bounded; runtime config mutation blocked; apply emits receipt",
    receipts: [],
  };
}

function readDigest(digestPath: string): AutonomyDigest {
  try {
    const raw = JSON.parse(fs.readFileSync(digestPath, "utf8"));
    if (raw && raw.schema === "molt-gic.autonomy.digest.v1") return raw as AutonomyDigest;
  } catch {}
  return defaultDigest();
}

function writeDigest(digestPath: string, digest: AutonomyDigest) {
  fs.mkdirSync(path.dirname(digestPath), { recursive: true, mode: 0o700 });
  fs.writeFileSync(digestPath, JSON.stringify(digest, null, 2) + "\n", { encoding: "utf8", mode: 0o600 });
}

function updateDigest(digestPath: string, receipt: Record<string, unknown>, action: string): AutonomyDigest {
  const prev = readDigest(digestPath);
  const receipts = [receipt, ...prev.receipts].slice(0, 8);
  const digest: AutonomyDigest = {
    schema: "molt-gic.autonomy.digest.v1",
    status: "ok",
    updated_at: new Date().toISOString(),
    last_action: action,
    evaluation: `latest receipt status=${String(receipt.status ?? "unknown")}, schema=${String(receipt.schema ?? "unknown")}`,
    suggested_evolution: "if this receipt is expected, propose the next smallest review-only packet; otherwise investigate before apply",
    next_safe_action: "/molt-gic evolve --review-only",
    apply_policy: "direct OpenClaw apply is blocked; use packet-backed CLI apply with confirm; runtime config mutation remains blocked",
    receipts,
  };
  writeDigest(digestPath, digest);
  return digest;
}

function formatDigest(digest: AutonomyDigest): string {
  return [
    "molt-gic passive autonomy digest",
    `updated: ${digest.updated_at}`,
    `last action: ${digest.last_action}`,
    `evaluation: ${digest.evaluation}`,
    `suggested evolution: ${digest.suggested_evolution}`,
    `next safe action: ${digest.next_safe_action}`,
    `apply policy: ${digest.apply_policy}`,
  ].join("\n");
}

function buildEvolveReceipt(routePath: string, params: Record<string, unknown> | undefined) {
  return {
    status: "ok",
    schema: "molt-gic.evolve.receipt.v1",
    route: routePath,
    mode: "review_only",
    packet_policy: "candidate-only",
    receipt_id: typeof params?.receipt_id === "string" ? params.receipt_id : `evolve_${Date.now().toString(36)}`,
    next_safe_action: "evaluate packet before apply",
    ts: new Date().toISOString(),
  };
}

function buildApplyReceipt(routePath: string, params: Record<string, unknown> | undefined) {
  return {
    status: "blocked",
    schema: "molt-gic.apply.receipt.v1",
    route: routePath,
    mode: "packet_backed_apply_required",
    receipt_id: typeof params?.receipt_id === "string" ? params.receipt_id : `apply_${Date.now().toString(36)}`,
    applied: false,
    reason: "packet_backed_adapter_required",
    next_safe_action: "run molt-gic apply local --packet <id> --reviewer <name> --confirm, then smoke and revert if needed",
    runtime_config_mutation: "blocked",
    ts: new Date().toISOString(),
  };
}

export default function register(api: OpenClawPluginApi) {
  const cfg = (api.pluginConfig ?? {}) as Config;
  if (cfg.enabled === false) return;
  const routePath = typeof cfg.routePath === "string" && cfg.routePath.startsWith("/") ? cfg.routePath : "/molt-gic/hook";
  const digestEnabled = cfg.autonomyDigest?.enabled !== false;
  const digestPath = safeDigestPath(api, cfg);
  const evolveApplyEnabled = cfg.enableEvolveApplyCommands !== false;

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
      const receipt = buildReceipt(routePath, payload, body);
      if (digestEnabled) updateDigest(digestPath, receipt, "http smoke");
      json(res, 200, receipt);
      return true;
    },
  });

  api.registerGatewayMethod("moltGic.status", async ({ respond }) => {
    respond(true, {
      status: "ok",
      schema: "molt-gic.gateway-rpc.status.v1",
      route: routePath,
      http_route: true,
      methods: ["moltGic.status", "moltGic.smoke", "moltGic.evolve", "moltGic.apply", "moltGic.autonomyDigest"],
      runtime_config_mutation: "blocked",
      command_surface: "/molt-gic status|smoke|evolve|apply|autonomy|help",
      autonomy_digest: digestEnabled,
      evolve_apply_enabled: evolveApplyEnabled,
    });
  });

  api.registerGatewayMethod("moltGic.smoke", async ({ params, respond }) => {
    const receipt = buildRpcReceipt(routePath, (params ?? {}) as Record<string, unknown>);
    if (digestEnabled) updateDigest(digestPath, receipt, "rpc smoke");
    respond(true, receipt);
  });

  api.registerGatewayMethod("moltGic.evolve", async ({ params, respond }) => {
    const receipt = buildEvolveReceipt(routePath, (params ?? {}) as Record<string, unknown>);
    if (digestEnabled) updateDigest(digestPath, receipt, "rpc evolve");
    respond(true, receipt);
  });

  api.registerGatewayMethod("moltGic.apply", async ({ params, respond }) => {
    const receipt = buildApplyReceipt(routePath, (params ?? {}) as Record<string, unknown>);
    if (digestEnabled) updateDigest(digestPath, receipt, "rpc apply");
    respond(true, receipt);
  });

  api.registerGatewayMethod("moltGic.autonomyDigest", async ({ respond }) => {
    respond(true, readDigest(digestPath));
  });

  try {
    api.on("before_prompt_build" as any, async () => {
      if (!digestEnabled) return {};
      const digest = readDigest(digestPath);
      if (digest.receipts.length === 0) return {};
      return { prependSystemContext: formatDigest(digest) };
    });
  } catch (err) {
    api.logger.warn?.(`molt-gic: passive autonomy digest prompt hook unavailable: ${String(err)}`);
  }

  try {
    api.on("agent_end" as any, async () => {
      if (!digestEnabled) return;
      const receipt = { status: "ok", schema: "molt-gic.agent-end.receipt.v1", ts: new Date().toISOString() };
      updateDigest(digestPath, receipt, "agent_end passive evaluation");
    });
  } catch (err) {
    api.logger.warn?.(`molt-gic: agent_end digest hook unavailable: ${String(err)}`);
  }

  api.registerCommand({
    name: "molt-gic",
    nativeNames: { default: "molt-gic" },
    description: "Inspect, smoke-test, evolve, or apply the bounded molt-gic OpenClaw bridge.",
    acceptsArgs: true,
    requireAuth: true,
    handler: async (ctx) => {
      const action = (ctx.args?.trim().split(/\s+/).filter(Boolean)[0] ?? "status").toLowerCase();
      if (action === "help") {
        return { text: "molt-gic commands: /molt-gic status, smoke, evolve, apply, autonomy. Runtime config mutation remains blocked." };
      }
      if (action === "status") {
        return { text: [
          "molt-gic OpenClaw bridge: ok",
          `HTTP route: ${routePath}`,
          "Gateway RPC: moltGic.status, smoke, evolve, apply, autonomyDigest",
          "Command surface: /molt-gic status, smoke, evolve, apply, autonomy",
          `Passive autonomy digest: ${digestEnabled ? "enabled" : "disabled"}`,
          `Evolve/apply command surface: ${evolveApplyEnabled ? "enabled" : "disabled"}`,
          "Runtime config mutation: blocked",
        ].join("\n") };
      }
      if (action === "smoke") {
        const receipt = buildRpcReceipt(routePath, { route: "command", receipt_id: `cmd_${Date.now().toString(36)}` });
        if (digestEnabled) updateDigest(digestPath, receipt, "command smoke");
        return { text: JSON.stringify({ surface: "command", ...receipt }) };
      }
      if (action === "autonomy") {
        return { text: formatDigest(readDigest(digestPath)) };
      }
      if (action === "evolve") {
        const receipt = buildEvolveReceipt(routePath, { receipt_id: `cmd_evolve_${Date.now().toString(36)}` });
        if (digestEnabled) updateDigest(digestPath, receipt, "command evolve");
        return { text: JSON.stringify({ surface: "command", ...receipt }) };
      }
      if (action === "apply") {
        const receipt = buildApplyReceipt(routePath, { receipt_id: `cmd_apply_${Date.now().toString(36)}` });
        if (digestEnabled) updateDigest(digestPath, receipt, "command apply");
        return { text: JSON.stringify({ surface: "command", ...receipt }) };
      }
      return { text: `Unknown molt-gic action: ${action}. Use /molt-gic help.`, isError: true };
    },
  });

  api.logger.info(`molt-gic-openclaw-extension: registered HTTP route, Gateway RPC, command surface, and passive autonomy digest`);
}
