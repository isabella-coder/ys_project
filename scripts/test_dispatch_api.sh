#!/usr/bin/env bash

set -euo pipefail

BASE_URL="${BASE_URL:-http://127.0.0.1:8000/api/v1}"
USERNAME="${USERNAME:-manager_yushuai}"
PASSWORD="${PASSWORD:-admin123}"
DATE_VALUE="${DATE_VALUE:-$(date +%F)}"
VIEW="${VIEW:-ALL}"
TECHNICIAN_NAME="${TECHNICIAN_NAME:-余帅}"
WORK_BAY="${WORK_BAY:-1号工位}"
DISPATCH_TIME="${DISPATCH_TIME:-}"

APPLY_MODE=0
ORDER_ID=""
ORDER_VERSION=""

usage() {
  cat <<'EOF'
Usage:
  scripts/test_dispatch_api.sh [options]

Options:
  --date YYYY-MM-DD         Query dispatch board by date (default: today)
  --view ALL|MINE           Dispatch board view (default: ALL)
  --username NAME           Store login username (default: manager_yushuai)
  --password PASS           Store login password (default: admin123)
  --tech NAME               Technician name for patch (default: 余帅)
  --bay NAME                Work bay for patch (default: 1号工位)
  --time HH:MM              Dispatch time for patch (default: use order time or 10:00)
  --order-id ID             Explicit order id for patch
  --version N               Explicit order version for patch
  --apply                   Execute PATCH /store/orders/{id}
  --help                    Show this help

Env overrides:
  BASE_URL, USERNAME, PASSWORD, DATE_VALUE, VIEW, TECHNICIAN_NAME, WORK_BAY, DISPATCH_TIME

Examples:
  scripts/test_dispatch_api.sh
  scripts/test_dispatch_api.sh --date 2026-03-11 --view ALL
  scripts/test_dispatch_api.sh --apply --order-id TM20260311202605879 --version 0 --tech 余帅 --bay 1号工位 --time 10:00
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --date)
      DATE_VALUE="$2"
      shift 2
      ;;
    --view)
      VIEW="$2"
      shift 2
      ;;
    --username)
      USERNAME="$2"
      shift 2
      ;;
    --password)
      PASSWORD="$2"
      shift 2
      ;;
    --tech)
      TECHNICIAN_NAME="$2"
      shift 2
      ;;
    --bay)
      WORK_BAY="$2"
      shift 2
      ;;
    --time)
      DISPATCH_TIME="$2"
      shift 2
      ;;
    --order-id)
      ORDER_ID="$2"
      shift 2
      ;;
    --version)
      ORDER_VERSION="$2"
      shift 2
      ;;
    --apply)
      APPLY_MODE=1
      shift
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1"
      usage
      exit 1
      ;;
  esac
done

echo "== Dispatch API Test =="
echo "BASE_URL=${BASE_URL}"
echo "DATE=${DATE_VALUE} VIEW=${VIEW}"
echo "MODE=$([[ ${APPLY_MODE} -eq 1 ]] && echo APPLY || echo READ_ONLY)"
echo

echo "[1/4] Login store account"
LOGIN_RESP="$(curl -fsS -X POST "${BASE_URL}/store/login" \
  -H 'Content-Type: application/json' \
  -d "{\"username\":\"${USERNAME}\",\"password\":\"${PASSWORD}\"}")"

TOKEN="$(printf '%s' "${LOGIN_RESP}" | python3 -c "import sys,json; print(json.load(sys.stdin).get('token',''))")"
if [[ -z "${TOKEN}" ]]; then
  echo "Login failed: token is empty"
  exit 1
fi
echo "  OK (token length=${#TOKEN})"
echo

echo "[2/4] Query dispatch board"
DISPATCH_JSON="$(curl -fsS "${BASE_URL}/store/dispatch?date=${DATE_VALUE}&view=${VIEW}" \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "X-Api-Token: ${TOKEN}")"

printf '%s' "${DISPATCH_JSON}" | python3 -c "
import sys,json
o=json.load(sys.stdin)
s=o.get('stats') or {}
print('  OK={} CODE={}'.format(o.get('ok'), o.get('code')))
print('  STATS total={total} assigned={assigned} unassigned={unassigned} conflict={conflict}'.format(
  total=s.get('total',0), assigned=s.get('assigned',0), unassigned=s.get('unassigned',0), conflict=s.get('conflict',0)
))
print('  ENTRIES={} CAPACITY={}'.format(len(o.get('entries') or []), len(o.get('capacity') or [])))
"
echo

echo "[3/4] Query orders and pick first candidate"
ORDERS_JSON="$(curl -fsS "${BASE_URL}/store/orders?view=ALL&status=ALL" \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "X-Api-Token: ${TOKEN}")"

FIRST_LINE="$(printf '%s' "${ORDERS_JSON}" | python3 -c "
import sys,json
o=json.load(sys.stdin)
items=o.get('items') or []
x=items[0] if items else {}
vals=[
  str(x.get('id','')),
  str(x.get('version','')),
  str(x.get('status','')),
  str(x.get('appointmentDate','')),
  str(x.get('appointmentTime','')),
]
print('\t'.join(vals))
")"

IFS=$'\t' read -r FIRST_ID FIRST_VERSION FIRST_STATUS FIRST_DATE FIRST_TIME <<< "${FIRST_LINE}"

if [[ -n "${FIRST_ID}" ]]; then
  echo "  FIRST_ID=${FIRST_ID}"
  echo "  FIRST_VERSION=${FIRST_VERSION}"
  echo "  FIRST_STATUS=${FIRST_STATUS}"
  echo "  FIRST_DATE=${FIRST_DATE} FIRST_TIME=${FIRST_TIME}"
else
  echo "  No orders found"
fi
echo

if [[ ${APPLY_MODE} -ne 1 ]]; then
  echo "[4/4] Skip patch (read-only mode). Use --apply to execute dispatch PATCH."
  exit 0
fi

echo "[4/4] Apply dispatch patch"

TARGET_ORDER_ID="${ORDER_ID:-${FIRST_ID}}"
TARGET_VERSION="${ORDER_VERSION:-${FIRST_VERSION}}"
TARGET_TIME="${DISPATCH_TIME}"
if [[ -z "${TARGET_TIME}" ]]; then
  TARGET_TIME="${FIRST_TIME:-10:00}"
fi

if [[ -z "${TARGET_ORDER_ID}" || -z "${TARGET_VERSION}" ]]; then
  echo "Missing order id/version for apply mode"
  echo "Provide --order-id and --version, or ensure orders list is not empty"
  exit 1
fi

NOW_TEXT="$(date '+%Y-%m-%d %H:%M')"

PATCH_RESP="$(curl -fsS -X PATCH "${BASE_URL}/store/orders/${TARGET_ORDER_ID}" \
  -H 'Content-Type: application/json' \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "X-Api-Token: ${TOKEN}" \
  -d "{\"version\":${TARGET_VERSION},\"status\":\"未完工\",\"dispatchInfo\":{\"date\":\"${DATE_VALUE}\",\"time\":\"${TARGET_TIME}\",\"workBay\":\"${WORK_BAY}\",\"technicianName\":\"${TECHNICIAN_NAME}\",\"technicianNames\":[\"${TECHNICIAN_NAME}\"],\"updatedAt\":\"${NOW_TEXT}\"}}")"

printf '%s' "${PATCH_RESP}" | python3 -c "
import sys,json
o=json.load(sys.stdin)
item=o.get('item') or {}
dispatch=item.get('dispatchInfo') or {}
print('  OK={} CODE={}'.format(o.get('ok'), o.get('code')))
print('  ORDER_ID={} VERSION={}'.format(item.get('id',''), item.get('version','')))
print('  DISPATCH date={date} time={time} bay={bay} tech={tech}'.format(
  date=dispatch.get('date',''),
  time=dispatch.get('time',''),
  bay=dispatch.get('workBay',''),
  tech=dispatch.get('technicianName','')
))
"

echo
echo "Done."
