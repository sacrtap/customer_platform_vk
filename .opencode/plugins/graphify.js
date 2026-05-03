/**
 * Graphify OpenCode Plugin — 智能触发版
 *
 * 仅在检测到多模块架构查询意图时注入提醒，避免对日常命令产生干扰。
 *
 * 触发条件（全部满足）：
 *   1. graphify-out/graph.json 存在
 *   2. 命令是探索类命令（grep/rg/find/ls/cat/head/tail/tree）
 *   3. 命令中同时出现 2 个及以上业务模块关键词
 *   4. 每条会话只触发一次
 */
import { existsSync, readFileSync } from "fs";
import { join } from "path";

// 业务模块关键词列表
const MODULE_KEYWORDS = [
  "auth", "customer", "settlement", "profile", "analysis",
  "invoice", "balance", "permission", "role", "user",
  "price_policy", "tier", "label", "health", "payment",
  "account", "order", "product", "api", "service",
  "repository", "model", "schema", "migration",
];

// 探索类命令前缀
const EXPLORATION_COMMANDS = [
  "grep", "rg", "find", "ls", "cat", "head", "tail", "tree",
];

/**
 * 从 GRAPH_REPORT.md 中提取 god nodes 摘要
 */
function extractGodNodesSummary(directory) {
  const reportPath = join(directory, "graphify-out", "GRAPH_REPORT.md");
  if (!existsSync(reportPath)) return null;

  try {
    const content = readFileSync(reportPath, "utf-8");
    // 尝试提取 god nodes 部分（通常在报告前部）
    const godSection = content.match(/god.?nodes?[\s\S]{0,500}/i);
    if (godSection) {
      // 提取提及的模块/类名（大写或 PascalCase 单词）
      const names = godSection[0].match(/[A-Z][a-zA-Z]+(?:[A-Z][a-zA-Z]+)*/g);
      if (names && names.length > 0) {
        return [...new Set(names)].slice(0, 5).join(", ");
      }
    }
    return null;
  } catch {
    return null;
  }
}

/**
 * 检查命令是否为探索类命令
 */
function isExplorationCommand(cmd) {
  const trimmed = cmd.trim();
  return EXPLORATION_COMMANDS.some((prefix) =>
    trimmed.startsWith(prefix) || trimmed.startsWith("sudo " + prefix)
  );
}

/**
 * 检查命令中是否包含 2 个及以上业务模块关键词
 */
function countModuleKeywords(cmd) {
  const lower = cmd.toLowerCase();
  return MODULE_KEYWORDS.filter((kw) => lower.includes(kw)).length;
}

export const GraphifyPlugin = async ({ directory }) => {
  let reminded = false;
  let godNodesSummary = null;

  // 启动时尝试读取图谱摘要
  if (existsSync(join(directory, "graphify-out", "graph.json"))) {
    godNodesSummary = extractGodNodesSummary(directory);
  }

  return {
    "tool.execute.before": async (input, output) => {
      if (reminded) return;

      // 图谱不存在时不触发
      if (!existsSync(join(directory, "graphify-out", "graph.json"))) return;

      if (input.tool === "bash") {
        const command = output.args.command || "";

        // 检查是否满足智能触发条件
        if (!isExplorationCommand(command)) return;
        if (countModuleKeywords(command) < 2) return;

        // 构建提醒消息
        const coreModules = godNodesSummary
          ? `核心模块: ${godNodesSummary}`
          : "知识图谱已就绪";

        const reminder =
          `[graphify] 检测到多模块查询意图，知识图谱可用\n` +
          `${coreModules}\n` +
          `建议使用 graphify_query_graph 工具追踪模块间依赖关系\n`;

        output.args.command = `echo "${reminder}" && ${command}`;
        reminded = true;
      }
    },
  };
};
