function esc(s) {
	gsub(/\\/, "\\\\", s)
	gsub(/"/, "\\\"", s)
	gsub(/[^ -~]/, "", s)
	return s
}

function fmt(b,   i, v) {
	v = b + 0
	for (i = 1; v >= 1024 && i < 6; i++)
		v /= 1024
	if (i == 1)
		return sprintf("%d %s", v, U[i])
	if (v >= 100)
		return sprintf("%d %s", v, U[i])
	if (v >= 10)
		return sprintf("%.1f %s", v, U[i])
	return sprintf("%.2f %s", v, U[i])
}

BEGIN {
	FS = "\t"
	split("B KB MB GB TB PB", U, " ")
	split("50 20 10", PCT, " ")
	split("3 4 5", PRI, " ")
	split("chart_with_downwards_trend warning rotating_light", TAG, " ")
	while ((getline line < state) > 0) {
		n = split(line, a, "\t")
		if (n >= 3) {
			sk[a[1]] = a[2]
			sl[a[1]] = a[3] + 0
		}
	}
	close(state)
	while ((getline line < quota) > 0) {
		n = split(line, a, "\t")
		if (n >= 3) {
			qu[a[1]] = a[2] + 0
			qk[a[1]] = a[3]
		}
	}
	close(quota)
	while ((getline line < stats) > 0) {
		n = split(line, a, "\t")
		if (n >= 4 && a[2] ~ /^[0-9a-f][0-9a-f](:[0-9a-f][0-9a-f]){5}$/ && a[4] != "-" && length(a[4]) <= 63 && a[4] ~ /^[A-Za-z0-9._-]+$/ && !(a[2] in hn))
			hn[a[2]] = a[4]
	}
	close(stats)
	printf "" > stout
	printf "" > qout
}

NF >= 5 {
	mac = $1
	lim = $3 + 0
	if ($5 != "1" || lim <= 0 || mac !~ /^[0-9a-f][0-9a-f](:[0-9a-f][0-9a-f]){5}$/)
		next
	used = (mac in qu) ? qu[mac] : 0
	key = (mac in qk) ? qk[mac] : "0"
	if (used > lim)
		used = lim
	rem = (lim - used) * 100 / lim
	cur = (rem <= 10) ? 3 : (rem <= 20) ? 2 : (rem <= 50) ? 1 : 0
	if (!(mac in sl))
		prev = cur
	else if (sk[mac] != key)
		prev = 0
	else
		prev = sl[mac]
	st = (cur > prev) ? prev : cur
	printf "%s\t%s\t%d\n", mac, key, st > stout
	if (cur > prev) {
		nm = ($2 != "") ? $2 : (mac in hn) ? hn[mac] : "client-" substr(mac, 10)
		msg = "Client: " esc(nm) "\\nRemaining: " fmt(lim - used) " of " fmt(lim) "\\nRouter: " esc(rname)
		printf "%s\t%s\t%d\t{\"topic\":\"%s\",\"title\":\"Data plan: %d%% remaining\",\"message\":\"%s\",\"priority\":%d,\"tags\":[\"%s\"]}\n", mac, key, cur, esc(topic), PCT[cur], msg, PRI[cur], TAG[cur] > qout
	}
}

END {
	close(stout)
	close(qout)
}
