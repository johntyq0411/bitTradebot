#!/usr/bin/env bash
# ============================================================
# Modest-Bohr Research Loop — orchestrate the full strategy
# research lifecycle: baseline → V2 iterations → validation
# → paper trade → deploy.
#
# Run without arguments to see usage/help. Run with a PHASE
# argument to execute that phase (e.g. ./loop.sh baseline).
# ============================================================

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$PROJECT_ROOT"

# --- Colors ---
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# --- Help ---
usage() {
    cat <<EOF
Modest-Bohr Research Loop — systematic strategy research pipeline

Usage: ./loop.sh <PHASE> [OPTIONS]

PHASES (run in order, or jump to a specific phase):

  0  setup        — Verify environment: Docker, data, configs
  1  baseline     — Run simple baselines (EMA crossover, etc.)
                     Output: baseline comparison table
  2  regimes      — Classify market regimes over full data period
                     Output: regime timeline + stats
  3  signal-test  — Test individual signal candidates per regime
                     Output: signal scorecard
  4  v2-test      — Backtest current V2 strategy
                     Output: V2 result + iteration suggestions
  5  walkfwd     — Walk-forward validation of best candidate
                     Output: walk-forward aggregate + fold breakdown
  6  paper-mon   — Paper trading monitor (read live P&L, compare to backtest)
                     Output: live vs backtest comparison
  7  report      — Generate full research report from all artifacts
                     Output: consolidated markdown report

  all            — Run the full pipeline sequentially (phases 0-7)

OPTIONS:
  --whatsapp     Send phase result summary via WhatsApp
  --dry-run      Print commands without executing
  --skip-fail    Continue to next phase even if current phase fails
  --help         Show this help

EXAMPLES:
  ./loop.sh 1                     Run baseline backtests
  ./loop.sh 1 --whatsapp         Run baselines + send WhatsApp update
  ./loop.sh all --skip-fail      Run full pipeline, continue on errors
  ./loop.sh 4                     Backtest latest V2 strategy

ARTIFACTS (auto-saved to docs/ and backtest_results/):
  docs/experiment-log.md         Running experiment log (append-only)
  docs/SPEC_V2.md                Technical design spec
  docs/experiment-log/           Per-experiment directories with:
    - result summary (markdown)
    - backtest JSON export
    - git commit hash
    - timestamp

The loop is designed to minimize back-and-forth:
  - Each phase has predefined inputs/outputs
  - Each phase produces a decision gate (go/no-go/iterate)
  - The --whatsapp flag keeps you informed without needing to ask
  - Git commits are automatic for every artifact

EOF
}

# --- Logging ---
log_info()    { echo -e "${BLUE}[INFO]${NC} $*"; }
log_success() { echo -e "${GREEN}[OK]${NC} $*"; }
log_warn()    { echo -e "${YELLOW}[WARN]${NC} $*"; }
log_error()   { echo -e "${RED}[ERROR]${NC} $*"; }

# --- Timestamp ---
timestamp() { date +"%Y%m%d_%H%M%S"; }
iso_now()   { date +"%Y-%m-%d %H:%M:%S"; }

# --- Git helpers ---
git_commit_artifact() {
    local filepath="$1"
    local message="$2"
    if [ -z "$filepath" ] || [ ! -f "$filepath" ]; then
        log_warn "Git commit skipped: $filepath not found"
        return
    fi
    git add "$filepath" 2>/dev/null || true
    if git diff --cached --quiet 2>/dev/null; then
        log_warn "No changes to commit for $filepath"
    else
        git commit -m "$message" --quiet 2>/dev/null && \
            log_success "Git committed: $filepath" || \
            log_warn "Git commit failed for $filepath (may already be committed)"
    fi
}

git_commit_dir() {
    local dirpath="$1"
    local message="$2"
    if [ ! -d "$dirpath" ]; then
        log_warn "Git commit skipped: $dirpath not found"
        return
    fi
    git add "$dirpath" 2>/dev/null || true
    if git diff --cached --quiet 2>/dev/null; then
        log_warn "No changes to commit for $dirpath"
    else
        git commit -m "$message" --quiet 2>/dev/null && \
            log_success "Git committed: $dirpath" || \
            log_warn "Git commit failed for $dirpath"
    fi
}

# --- WhatsApp helper ---
send_whatsapp() {
    local message_file="$1"
    if [ ! -f "$message_file" ]; then
        log_warn "WhatsApp skipped: message file $message_file not found"
        return
    fi
    if command -v hermes &>/dev/null; then
        hermes send -t whatsapp:60178257407 -f "$message_file" 2>/dev/null && \
            log_success "WhatsApp sent: $message_file" || \
            log_warn "WhatsApp send failed"
    else
        log_warn "hermes CLI not found — skipping WhatsApp"
    fi
}

# ============================================================
# PHASE 0: Setup verification
# ============================================================
phase_setup() {
    local experiment_dir="docs/experiments/PHASE0-setup-$(timestamp)"
    mkdir -p "$experiment_dir"
    local report="$experiment_dir/report.md"
    
    cat > "$report" <<'HEADER'
# Phase 0: Setup Verification

**Date:** {DATE}
**Goal:** Verify all prerequisites are in place before running backtests.

HEADER
    echo "" >> "$report"
    
    local all_ok=true
    
    # Check Docker
    log_info "Checking Docker..."
    if docker compose ps --quiet 2>/dev/null | grep -q .; then
        log_success "Docker containers running"
        echo "**Docker:** ✅ Running" >> "$report"
    else
        log_error "Docker containers not running"
        echo "**Docker:** ❌ Not running" >> "$report"
        all_ok=false
    fi
    
    # Check data
    log_info "Checking data files..."
    if docker compose exec -T freqtrade test -f /freqtrade/user_data/data/binance/BTC_USDT-1h.feather 2>/dev/null; then
        local rows
        rows=$(docker compose exec -T freqtrade python3 -c "
import pandas as pd
df = pd.read_feather('/freqtrade/user_data/data/binance/BTC_USDT-1h.feather')
print(len(df))
" 2>/dev/null || echo "0")
        log_success "1h data: $rows candles"
        echo "**1h Data:** ✅ $rows candles" >> "$report"
    else
        log_error "1h feather data not found"
        echo "**1h Data:** ❌ Missing" >> "$report"
        all_ok=false
    fi
    
    # Check 4h data
    if docker compose exec -T freqtrade test -f /freqtrade/user_data/data/binance/BTC_USDT-4h.feather 2>/dev/null; then
        local rows4
        rows4=$(docker compose exec -T freqtrade python3 -c "
import pandas as pd
df = pd.read_feather('/freqtrade/user_data/data/binance/BTC_USDT-4h.feather')
print(len(df))
" 2>/dev/null || echo "0")
        log_success "4h data: $rows4 candles"
        echo "**4h Data:** ✅ $rows4 candles" >> "$report"
    else
        log_warn "4h data not found (optional)"
        echo "**4h Data:** ⚠️ Not found (optional)" >> "$report"
    fi
    
    # Check configs
    log_info "Checking configs..."
    for cfg in config_baseline.json config.json config_freqai.json; do
        if [ -f "user_data/$cfg" ]; then
            log_success "Config: $cfg"
            echo "**Config $cfg:** ✅" >> "$report"
        else
            log_error "Config missing: $cfg"
            echo "**Config $cfg:** ❌" >> "$report"
            all_ok=false
        fi
    done
    
    # Check strategies
    log_info "Checking strategy files..."
    local v2_count
    v2_count=$(ls user_data/strategies_v2/BtcTrendFollowingV2Strategy.py 2>/dev/null | wc -l || echo "0")
    if [ "$v2_count" -gt 0 ]; then
        log_success "V2 strategy: present (v$(grep 'V2\.' user_data/strategies_v2/BtcTrendFollowingV2Strategy.py | head -1 | grep -oP 'V2\.\d+' || echo 'unknown'))"
        echo "**V2 Strategy:** ✅" >> "$report"
    else
        log_error "V2 strategy not found"
        echo "**V2 Strategy:** ❌" >> "$report"
        all_ok=false
    fi
    
    echo "" >> "$report"
    echo "---" >> "$report"
    if $all_ok; then
        echo "**Result:** ✅ All prerequisites met" >> "$report"
        log_success "Setup check complete — ready to proceed"
    else
        echo "**Result:** ❌ Some prerequisites missing — see report" >> "$report"
        log_error "Setup check failed — fix issues before proceeding"
    fi
    
    # Git commit
    git_commit_dir "$experiment_dir" "docs: phase 0 setup verification $(iso_now)"
    
    if [ "$SEND_WHATSAPP" = true ]; then
        send_whatsapp "$report"
    fi
    
    echo ""
    echo "Report: $report"
}

# ============================================================
# PHASE 1: Baseline backtests
# ============================================================
phase_baseline() {
    local experiment_dir="docs/experiments/PHASE1-baseline-$(timestamp)"
    mkdir -p "$experiment_dir"
    local report="$experiment_dir/report.md"
    local results_csv="$experiment_dir/results.csv"
    
    cat > "$report" <<'HEADER'
# Phase 1: Baseline Strategy Comparison

**Date:** {DATE}
**Goal:** Establish performance baseline for simple strategies on BTC/USDT 1h data.
**Purpose:** Know what "no edge" looks like before testing more complex approaches.

HEADER
    echo "" >> "$report"
    
    echo "strategy,trades,total_pnl_pct,max_drawdown,sharpe,profit_factor,win_rate,open_trades" > "$results_csv"
    
    # Strategies to test
    local strategies=(
        "BtcEmaCrossoverStrategy"
    )
    
    for strat in "${strategies[@]}"; do
        log_info "Backtesting: $strat"
        
        local result
        result=$(docker compose exec -T freqtrade freqtrade backtesting \
            --config /freqtrade/user_data/config_baseline.json \
            --strategy "$strat" \
            --timeframe 1h \
            --timerange 20240824-20260822 \
            --export trades \
            --cache none \
            --notes "BASELINE-$strat-$(timestamp)" 2>&1) || true
        
        # Also save export explicitly
        docker compose exec -T freqtrade freqtrade backtesting \
            --config /freqtrade/user_data/config_baseline.json \
            --strategy "$strat" \
            --timeframe 1h \
            --timerange 20240824-20260822 \
            --export trades \
            --cache none \
            --notes "BASELINE-$strat-$(timestamp)" 2>&1 > /dev/null || true
        
        # Extract metrics from result
        local trades pnl dd sharpe pf wr
        trades=$(echo "$result" | grep -oP 'Trades\s+\K\d+' || echo "0")
        pnl=$(echo "$result" | grep -oP 'Total Profit %\s+\K[-]?\d+\.\d+' || echo "0")
        dd=$(echo "$result" | grep -oP 'Drawdown\s+\K[-]?\d+\.\d+%' | head -1 | grep -oP '[-]?\d+\.\d+' || echo "0")
        sharpe=$(echo "$result" | grep -oP 'Sharpe \(daily[^)]*\)\s+\K[-]?\d+\.\d+' | head -1 || echo "0")
        pf=$(echo "$result" | grep -oP 'Profit Factor\s+\K\d+\.\d+' || echo "0")
        
        # Count open/closed from trade summary
        local open_trades
        open_trades=$(echo "$result" | grep -oP 'Opening Trades\s+\K\d+' || echo "0")
        
        # Win rate from trade table
        local win_rate
        win_rate=$(echo "$result" | grep -oP 'Win\s+\K\d+\.\d+%' | head -1 | grep -oP '\d+\.\d+' || echo "0")
        
        echo "$strat,$trades,$pnl,$dd,$sharpe,$pf,$win_rate,$open_trades" >> "$results_csv"
        
        echo "" >> "$report"
        echo "## $strat" >> "$report"
        echo "" >> "$report"
        echo "| Metric | Value |" >> "$report"
        echo "|--------|-------|" >> "$report"
        echo "| Trades | $trades |" >> "$report"
        echo "| Total P/L | ${pnl}% |" >> "$report"
        echo "| Max Drawdown | ${dd}% |" >> "$report"
        echo "| Sharpe | $sharpe |" >> "$report"
        echo "| Profit Factor | $pf |" >> "$report"
        echo "| Win Rate | ${win_rate}% |" >> "$report"
        echo "| Open Trades | $open_trades |" >> "$report"
        
        # Save raw result
        echo "$result" > "$experiment_dir/${strat}.raw.txt"
        
        # Git commit per strategy
        git_commit_dir "$experiment_dir" "docs: baseline backtest $strat $(iso_now)"
    done
    
    # Summary table
    echo "" >> "$report"
    echo "---" >> "$report"
    echo "" >> "$report"
    echo "## Baseline Comparison Summary" >> "$report"
    echo "" >> "$report"
    echo "| Strategy | Trades | P/L % | Drawdown % | Sharpe | PF | Win Rate % |" >> "$report"
    echo "|----------|--------|-------|------------|--------|-----|------------|" >> "$report"
    
    while IFS=, read -r strat trades pnl dd sharpe pf wr ot; do
        if [ "$strat" != "strategy" ]; then
            echo "| $strat | $trades | $pnl | $dd | $sharpe | $pf | $wr |" >> "$report"
        fi
    done < "$results_csv"
    
    echo "" >> "$report"
    echo "**Decision Gate:**" >> "$report"
    echo "- If any baseline shows positive P/L with reasonable drawd...[truncated]