#!/usr/bin/env bash
BASE="${1:-https://ricemillmart.tech}"
BASE="${BASE%/}"
HOST="${BASE#*://}"; HOST="${HOST%%/*}"
PASS=0; FAIL=0

ok()   { PASS=$((PASS+1)); printf '  PASS  %s\n' "$1"; }
bad()  { FAIL=$((FAIL+1)); printf '  FAIL  %s\n' "$1"; }
code() { curl -sk -o /dev/null -m 20 -w '%{http_code}' "$@"; }
expect() {
  local label="$1" allowed="$2"; shift 2
  local got; got=$(code "$@")
  case " $allowed " in *" $got "*) ok "$label ($got)";; *) bad "$label: got $got, expected $allowed";; esac
}

echo "Testing $BASE"
echo "Server and pages"
body=$(curl -sk -m 20 "$BASE/api/healthz")
case "$body" in *'"ok"'*) ok "health check says ok";; *) bad "health check body: $body";; esac
expect "home page loads" "200" "$BASE/"
curl -sk -m 20 "$BASE/" | grep -q 'id="root"' && ok "home page is the React app" || bad "home page is not the React app"
expect "login/admin route loads (single-page app)" "200" "$BASE/admin"
expect "unknown API path is a clean 404" "404" "$BASE/api/does-not-exist"
curl -sk -m 20 "$BASE/api/does-not-exist" | grep -qi "URLconf" && bad "DEBUG looks ON (Django debug page shown)" || ok "no Django debug page"

echo "Access control (no login, so every private page must refuse)"
expect "machines need login" "401" "$BASE/api/machines"
expect "alerts need login" "401 404" "$BASE/api/alerts"
expect "admin users need login" "401" "$BASE/api/admin-portal/users"
expect "admin gateways need login" "401" "$BASE/api/admin-portal/gateways"
expect "admin enquiries need login" "401" "$BASE/api/admin-portal/enquiries"
expect "reports need login" "401" "$BASE/api/reports/daily"

echo "Gateway endpoints refuse wrong keys"
expect "HTTPS ingest, wrong key" "401 403" -X POST -H "X-Gateway-Key: wrong" -H "Content-Type: application/json" -d '{"readings":[]}' "$BASE/api/ingest"
expect "IoT rule endpoint, no secret" "401 403 404" -X POST -H "Content-Type: application/json" -d '{}' "$BASE/api/iot/ingest"
expect "gateway provision, wrong key" "401 403 404" -X POST -H "X-Provision-Key: wrong" -H "Content-Type: application/json" -d '{"serial":"X","name":"X"}' "$BASE/api/gateways/provision"

echo "Public contact form"
expect "empty contact form is rejected, not a crash" "400 422" -X POST -H "Content-Type: application/json" -d '{}' "$BASE/api/contact"

echo "Security"
hdr=$(curl -skI -m 20 "$BASE/")
case "$BASE" in https://*)
  echo "$hdr" | grep -qi '^strict-transport-security' && ok "HSTS header present" || bad "HSTS header missing"
  echo "$hdr" | grep -qi '^x-content-type-options' && ok "X-Content-Type-Options present" || bad "X-Content-Type-Options missing"
  echo "$hdr" | grep -qi '^content-security-policy' && ok "Content-Security-Policy present" || bad "Content-Security-Policy missing"
  r=$(curl -s -o /dev/null -m 20 -w '%{http_code}' "http://$HOST/")
  case "$r" in 301|302|307|308) ok "http redirects to https ($r)";; *) bad "http did not redirect (got $r)";; esac
  end=$(echo | openssl s_client -servername "$HOST" -connect "$HOST:443" 2>/dev/null | openssl x509 -noout -enddate 2>/dev/null | cut -d= -f2)
  if [ -n "$end" ]; then
    days=$(( ( $(date -d "$end" +%s) - $(date +%s) ) / 86400 ))
    [ "$days" -gt 14 ] && ok "HTTPS certificate valid for $days more days" || bad "HTTPS certificate expires in $days days"
  else bad "could not read the HTTPS certificate"; fi
  for p in 5432 6379; do
    if timeout 4 bash -c "exec 3<>/dev/tcp/$HOST/$p" 2>/dev/null; then bad "port $p is open to the internet"; else ok "port $p is closed"; fi
  done;;
esac

echo
echo "$PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ]
