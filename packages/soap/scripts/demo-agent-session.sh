#!/usr/bin/env bash
# 模拟一个外部 Agent 在 SOAP 环境中的完整交互session
# 先启动 soap-view（默认 8765），然后在另一终端运行此脚本
# 在 soap-view 浏览器中可实时看到事件日志和地图变化
set -euo pipefail
API="http://127.0.0.1:8765/api/act"
AGENT="openclaw_explorer_1"

echo "═══ SOAP Agent Session Demo ═══"
echo "Agent: $AGENT"
echo ""

act() {
  local desc="$1"
  shift
  echo "▸ $desc"
  curl -s -X POST "$API" -H "Content-Type: application/json" -d "$1" | python3 -m json.tool
  echo ""
  sleep 1
}

act "1. OBSERVE 中庭区域 — 了解周围有什么" \
  "{\"agent_id\":\"$AGENT\",\"verb\":\"OBSERVE\",\"target_id\":\"atrium\"}"

act "2. OBSERVE 喷泉 — 确认位置" \
  "{\"agent_id\":\"$AGENT\",\"verb\":\"OBSERVE\",\"target_id\":\"fountain_center\"}"

act "3. OBSERVE NPC 商人 Lin — 查看状态" \
  "{\"agent_id\":\"$AGENT\",\"verb\":\"OBSERVE\",\"target_id\":\"npc_merchant_lin\"}"

act "4. MANIPULATE 和 Lin 说话 — 触发对话" \
  "{\"agent_id\":\"$AGENT\",\"verb\":\"MANIPULATE\",\"target_id\":\"npc_merchant_lin\",\"params\":{\"action\":\"speak\",\"message\":\"你好，今天有什么好物推荐？\"}}"

act "5. NAVIGATE Lin 走到咖啡店 — 移动 NPC" \
  "{\"agent_id\":\"$AGENT\",\"verb\":\"NAVIGATE\",\"target_id\":\"npc_merchant_lin\",\"params\":{\"target_uri\":\"soap://mall_01/cafe_201/counter\"}}"

act "6. OBSERVE 咖啡师 Chen" \
  "{\"agent_id\":\"$AGENT\",\"verb\":\"OBSERVE\",\"target_id\":\"npc_barista_chen\"}"

act "7. MANIPULATE 让 Chen 做咖啡" \
  "{\"agent_id\":\"$AGENT\",\"verb\":\"MANIPULATE\",\"target_id\":\"npc_barista_chen\",\"params\":{\"action\":\"make_coffee\"}}"

act "8. MANIPULATE 和 Chen 聊天 — 要一杯拿铁" \
  "{\"agent_id\":\"$AGENT\",\"verb\":\"MANIPULATE\",\"target_id\":\"npc_barista_chen\",\"params\":{\"action\":\"speak\",\"message\":\"来杯拿铁吧\"}}"

act "9. OBSERVE 怪物 — 查看战斗状态" \
  "{\"agent_id\":\"$AGENT\",\"verb\":\"OBSERVE\",\"target_id\":\"game_monster_01\"}"

act "10. MANIPULATE 攻击怪物（伤害 50）" \
  "{\"agent_id\":\"$AGENT\",\"verb\":\"MANIPULATE\",\"target_id\":\"game_monster_01\",\"params\":{\"action\":\"attack_target\",\"damage\":50}}"

act "11. MANIPULATE 再次攻击（伤害 80）— 应该击杀" \
  "{\"agent_id\":\"$AGENT\",\"verb\":\"MANIPULATE\",\"target_id\":\"game_monster_01\",\"params\":{\"action\":\"attack_target\",\"damage\":80}}"

act "12. NAVIGATE 配送机器人到 102 店铺" \
  "{\"agent_id\":\"$AGENT\",\"verb\":\"NAVIGATE\",\"target_id\":\"robot_unit_d\",\"params\":{\"target_uri\":\"soap://mall_01/store_102/entrance\"}}"

act "13. MANIPULATE 扫码进入数字孪生" \
  "{\"agent_id\":\"$AGENT\",\"verb\":\"MANIPULATE\",\"target_id\":\"store_102_front\",\"params\":{\"action\":\"scan_qr\"}}"

echo "═══ Session 完成 ═══"
echo "刷新 soap-view 查看完整事件日志和地图变化"
echo "或 curl http://127.0.0.1:8765/api/events"
