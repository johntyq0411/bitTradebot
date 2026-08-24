#!/usr/bin/env bash
# =============================================================================
# hermes_monitor.sh — Freqtrade Bot Watchdog with Discord Alerts
# =============================================================================
# Polls the Freqtrade REST API every CHECK_INTERVAL seconds.
# Sends Discord webhook alerts on:
#   - Bot unreachable (no heartbeat > 2 consecutive checks)
#   - Open trade drawdown exceeds DRAWDOWN_ALERT_PCT
#   - Bot wallet drops below LOW_BALANCE_USDT
#
# Usage:
#   chmod +x hermes_monitor.sh
#   ./hermes_monitor.sh                         # foreground
#   nohup ./hermes_monitor.sh > monitor.log 2>&1 &   # background daemon
#
# On VPS, run via Hermes agent or add to crontab:
#   @reboot /path/to/hermes_monitor.sh >> /var/log/freqtrade_monitor.log 2>&1
#
# Requirements: curl, jq
# =============================================================================

set -euo pipefail

# ── Configuration ─────────────────────────────────────────────────────────────
FREQTRADE_URL="${FREQTRADE_URL:-http://localhost:8080}"
FREQUI_USER="${FREQUI_USERNAME:-freqtrader}"
FREQUI_PASS="${FREQUI_PASSWORD:-freqtrader}"
DISCORD_WEBHOOK="${DISCORD_WEBHOOK_URL:-}"
CHECK_INTERVAL="${CHECK_INTERVAL:-300}"   # seconds between polls (default: 5 min)
DRAWDOWN_ALERT_PCT="${DRAWDOWN_ALERT_PCT:--5}"  # alert if open trade < -5%
LOW_BALANCE_USDT="${LOW_BALANCE_USDT:-100}"     # alert if wallet < 100 USDT
# ──────────────────────────────────────────────────────────────────────────────

BOT_NAME="MultiFactorBtcBot"
MISS_COUNT=0
MAX_MISS=2  # consecutive missed heartbeats before alert

HERMES_WHATSAPP="${HERMES_WHATSAPP:-false}"   # "true" to also send alerts via WhatsApp
WHATSAPP_RECIPIENT="${WHATSAPP_RECIPIENT:-}"    # phone number WITHOUT + (e.g. 60178257407)
WHATSAPP_SEND_CMD="${WHATSAPP_SEND_CMD:-hermes send --to whatsapp}"

# ── Helpers ───────────────────────────────────────────────────────────────────

log() {
    echo "[$(date -u '+%Y-%m-%dT%H:%M:%SZ')] $*"
}

# Send a Discord embed message
discord_alert() {
    local title="$1"
    local message="$2"
    local color="${3:-16711680}"  # Default: red (0xFF0000)

    if [[ -z "$DISCORD_WEBHOOK" ]]; then
        log "[DISCORD] Webhook not configured — alert suppressed: $title"
        return
    fi

    local payload
    payload=$(cat <<EOF
{
  "embeds": [{
    "title": "🤖 ${BOT_NAME}: ${title}",
    "description": "${message}",
    "color": ${color},
    "footer": {"text": "Freqtrade Monitor • $(date -u '+%Y-%m-%d %H:%M UTC')"}
  }]
}
EOF
)
    curl -s -o /dev/null -X POST \
        -H "Content-Type: application/json" \
        -d "$payload" \
        "$DISCORD_WEBHOOK" && log "[DISCORD] Alert sent: $title" || log "[DISCORD] Failed to send alert"
}

# Send a WhatsApp message via the Hermes CLI (uses the already-paired Baileys session).
# Only sends if HERMES_WHATSAPP=true AND WHATSAPP_RECIPIENT is set AND the send command exists.
whatsapp_alert() {
    local title="$1"
    local message="$2"

    if [[ "$HERMES_WHATSAPP" != "true" || -z "$WHATSAPP_RECIPIENT" ]]; then
        return
    fi
    if ! command -v "${WHATSAPP_SEND_CMD%% *}" &>/dev/null; then
        log "[WHATSAPP] hermes CLI not on PATH — WhatsApp alerts suppressed"
        return
    fi

    local full_msg="🤖 ${BOT_NAME}: ${title}\n\n${message}"
    $WHATSAPP_SEND_CMD "MEDIA:none ${full_msg}" \
        --to "$WHATSAPP_RECIPIENT" >/dev/null 2>&1 && \
        log "[WHATSAPP] Alert sent: $title" || \
        log "[WHATSAPP] Failed to send alert: $title"
}

# Call Freqtrade REST API with one retry on transient failure.
ft_api() {
    local endpoint="$1"
    local response
    response=$(curl -s --max-time 10 \
        -u "${FREQUI_USER}:${FREQUI_PASS}" \
        "${FREQTRADE_URL}/api/v1/${endpoint}" 2>/dev/null) || true
    if [[ -z "$response" ]]; then
        # One retry — transient blip shouldn't count as a miss.
        response=$(curl -s --max-time 10 \
            -u "${FREQUI_USER}:${FREQUI_PASS}" \
            "${FREQTRADE_URL}/api/v1/${endpoint}" 2>/dev/null) || true
    fi
    echo "$response"
}

# ── Startup check ─────────────────────────────────────────────────────────────
if ! command -v jq &>/dev/null; then
    log "[ERROR] jq is required. Install with: apt-get install -y jq"
    exit 1
fi

if [[ -z "$DISCORD_WEBHOOK" ]]; then
    log "[WARN] DISCORD_WEBHOOK_URL not set — alerts will only be logged, not sent to Discord."
fi

log "===== Freqtrade Monitor Started ====="
log "  Bot URL:          ${FREQTRADE_URL}"
log "  Check interval:   ${CHECK_INTERVAL}s"
log "  Drawdown alert:   ${DRAWDOWN_ALERT_PCT}%"
log "  Low balance:      ${LOW_BALANCE_USDT} USDT"
log "  Discord webhook:  ${DISCORD_WEBHOOK:+(configured)}"
log "======================================="

# ── Main Loop ─────────────────────────────────────────────────────────────────
while true; do
    # 1. Heartbeat check
    ping_response=$(ft_api "ping" || echo "")
    if echo "$ping_response" | jq -e '.status == "pong"' &>/dev/null; then
        MISS_COUNT=0
        log "[OK] Bot heartbeat: pong"
    else
        MISS_COUNT=$((MISS_COUNT + 1))
        log "[WARN] Bot missed heartbeat (${MISS_COUNT}/${MAX_MISS})"
        if [[ $MISS_COUNT -ge $MAX_MISS ]]; then
            discord_alert \
                "⚠️ Bot Unreachable" \
                "No response from \`${FREQTRADE_URL}\` for $((MISS_COUNT * CHECK_INTERVAL / 60)) minutes.\nCheck if the Docker container is running.\n\`\`\`bash\ndocker compose ps\ndocker compose logs --tail 50 freqtrade\`\`\`" \
                "16711680"
            if [[ -n "${HERMES_WHATSAPP:+x}" && -n "${WHATSAPP_RECIPIENT:-}" ]]; then
                whatsapp_alert \
                    "⚠️ Bot Unreachable" \
                    "No response from ${FREQTRADE_URL} for $((MISS_COUNT * CHECK_INTERVAL / 60)) min. Check: docker compose ps"
            fi
            MISS_COUNT=0  # Reset after alert to avoid spam
        fi
        sleep "$CHECK_INTERVAL"
        continue
    fi

    # 2. Open trade drawdown check
    status_response=$(ft_api "status" || echo "{}")
    trades_json="[]"
    if echo "$status_response" | jq -e '.trades' &>/dev/null; then
        trades_json=$(echo "$status_response" | jq -c '.trades // []')
    elif echo "$status_response" | jq -e 'type == "array"' &>/dev/null; then
        trades_json="$status_response"
    fi
    if echo "$trades_json" | jq -e 'length > 0' &>/dev/null; then
        while IFS= read -r trade; do
            pair=$(echo "$trade" | jq -r '.pair')
            profit_pct=$(echo "$trade" | jq -r '.profit_pct')
            open_rate=$(echo "$trade" | jq -r '.open_rate')
            current_rate=$(echo "$trade" | jq -r '.current_rate // "N/A"')

            # Compare profit_pct to threshold (bash handles only int; use awk)
            is_below_threshold=$(awk "BEGIN {print ($profit_pct < $DRAWDOWN_ALERT_PCT) ? 1 : 0}")
            if [[ "$is_below_threshold" == "1" ]]; then
                log "[ALERT] Drawdown on ${pair}: ${profit_pct}% (threshold: ${DRAWDOWN_ALERT_PCT}%)"
                discord_alert \
                    "📉 Drawdown Alert: ${pair}" \
                    "Open trade is in significant drawdown.\n\n**Pair:** \`${pair}\`\n**P/L:** \`${profit_pct}%\`\n**Open Rate:** \`${open_rate}\`\n**Current Rate:** \`${current_rate}\`\n\nMonitor and consider manual intervention if the stop hasn't triggered." \
                    "16744272"  # Orange
                if [[ -n "${HERMES_WHATSAPP:+x}" && -n "${WHATSAPP_RECIPIENT:-}" ]]; then
                    whatsapp_alert \
                        "📉 Drawdown: ${pair}" \
                        "P/L: ${profit_pct}% | Open: ${open_rate} | Current: ${current_rate}"
                fi
            else
                log "[OK] ${pair}: ${profit_pct}% (within threshold)"
            fi
        done < <(echo "$trades_json" | jq -c '.[]')
    else
        log "[INFO] No open trades"
    fi

    # 3. Wallet balance check
    balance_response=$(ft_api "balance" || echo "{}")
    if echo "$balance_response" | jq -e '.total' &>/dev/null; then
        total_usdt=$(echo "$balance_response" | jq -r '.total')
        is_low=$(awk "BEGIN {print ($total_usdt < $LOW_BALANCE_USDT) ? 1 : 0}")
        if [[ "$is_low" == "1" ]]; then
            log "[ALERT] Low wallet balance: ${total_usdt} USDT (threshold: ${LOW_BALANCE_USDT})"
            discord_alert \
                "💰 Low Balance Warning" \
                "Bot wallet is critically low.\n\n**Total:** \`${total_usdt} USDT\`\n**Threshold:** \`${LOW_BALANCE_USDT} USDT\`\n\nConsider topping up the paper wallet or checking for unexpected losses." \
                "16744272"
        else
            log "[OK] Wallet balance: ${total_usdt} USDT"
        fi
    fi

    # 4. Daily profit summary (fetch closed-trades summary from the /api/v1/trades endpoint)
    trades_history=$(ft_api "trades" || echo "[]")
    trade_count=$(echo "$trades_history" | jq -r '. | length // 0')
    if [[ "$trade_count" -gt 0 ]]; then
        profit_sum=$(echo "$trades_history" | jq '[.[] | .profit_abs] | add // 0')
        # Profit % is usually computed relative to stake; log absolute P/L from the trades list.
        log "[PROFIT] ${trade_count} total trades; sum profit_abs = ${profit_sum} USDT"
    fi

    log "--- Next check in ${CHECK_INTERVAL}s ---"
    sleep "$CHECK_INTERVAL"
done
