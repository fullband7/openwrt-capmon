function bdig(s) {
	return (s ~ /^[0-9]+$/)
}

function bctr(s) {
	return (s ~ /^[0-9]+$/ && length(s) <= 15)
}

function bmac(s) {
	return (s ~ /^[0-9a-f][0-9a-f]:[0-9a-f][0-9a-f]:[0-9a-f][0-9a-f]:[0-9a-f][0-9a-f]:[0-9a-f][0-9a-f]:[0-9a-f][0-9a-f]$/)
}

function bday(d,   y, m, n, mx) {
	if (length(d) != 8 || !bdig(d))
		return 0
	y = substr(d, 1, 4) + 0
	m = substr(d, 5, 2) + 0
	n = substr(d, 7, 2) + 0
	if (y < 2000 || y > 2099 || m < 1 || m > 12 || n < 1)
		return 0
	mx = substr("312831303130313130313031", 2 * m - 1, 2) + 0
	if (m == 2 && y % 4 == 0 && (y % 100 != 0 || y % 400 == 0))
		mx = 29
	return (n <= mx)
}

function bdevs(v,   a, n, i) {
	if (v == "")
		return 1
	if (v !~ /^[A-Za-z0-9._-]+( [A-Za-z0-9._-]+)*$/)
		return 0
	n = split(v, a, " ")
	if (n > 8)
		return 0
	for (i = 1; i <= n; i++)
		if (length(a[i]) > 15)
			return 0
	return 1
}

function bcfg(k, v) {
	if (k == "interval")
		return (bdig(v) && length(v) <= 2 && v + 0 >= 5 && v + 0 <= 60)
	if (k == "count_router" || k == "server_enabled")
		return (v == "0" || v == "1")
	if (k == "server_url")
		return (v == "" || (v ~ /^https:\/\/[A-Za-z0-9.:_-]+$/ && length(v) <= 120))
	if (k == "server_pin")
		return (v == "" || (v ~ /^sha256\/\/[A-Za-z0-9+\/]+=$/ && length(v) == 52))
	if (k == "router_id")
		return (v == "" || (v ~ /^[A-Za-z0-9_-]+$/ && length(v) <= 32))
	if (k == "extra_dev")
		return bdevs(v)
	return 0
}

function bplan(m, n, l, p, e) {
	if (!bmac(m) || n !~ /^[A-Za-z0-9 ._-]*$/ || length(n) > 32)
		return 0
	if (l !~ /^[1-9][0-9]*$/ || length(l) > 15)
		return 0
	if (p != "none" && p != "daily" && p != "weekly" && p != "monthly")
		return 0
	return (e == "0" || e == "1")
}

function bip(s,   a, i) {
	if (s == "-")
		return 1
	if (length(s) > 45)
		return 0
	if (s ~ /^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$/) {
		split(s, a, ".")
		for (i = 1; i <= 4; i++)
			if (length(a[i]) > 3 || a[i] + 0 > 255)
				return 0
		return 1
	}
	return (s ~ /^[0-9a-f:.]+$/ && index(s, ":") > 0)
}

function bkey(k, m) {
	if (length(k) > 45)
		return 0
	if (k == "router")
		return (m == "-" || bmac(m))
	if (k !~ /^[0-9a-f:.]+$/)
		return 0
	if (bmac(k))
		return (m == k)
	return (m == "-")
}

function bname(s) {
	return (s == "-" || (s ~ /^[A-Za-z0-9._-]+$/ && length(s) <= 63))
}

function bseen(s) {
	return (bdig(s) && length(s) <= 10)
}

function bpkey(s) {
	return (bdig(s) && length(s) <= 8)
}
