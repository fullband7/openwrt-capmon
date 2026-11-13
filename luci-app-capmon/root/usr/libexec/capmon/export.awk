function num(v) {
	return sprintf("%.0f", v + 0)
}

function put(s) {
	out[++n] = s
}

BEGIN {
	FS = "\t"
	nplans = 0
	nstats = 0
	if (!bcfg("interval", interval))
		interval = "10"
	if (!bcfg("count_router", count_router))
		count_router = "1"
	if (!bcfg("server_url", server_url))
		server_url = ""
	if (!bcfg("server_pin", server_pin))
		server_pin = ""
	if (!bcfg("server_enabled", server_enabled))
		server_enabled = "0"
	if (!bcfg("router_id", router_id))
		router_id = ""
	if (!bcfg("extra_dev", extra_dev))
		extra_dev = ""
	if (!bdig(since) || length(since) > 10 || since + 0 < 946684800 || since + 0 > now + 172800)
		since = now
	if (!bday(day) || dayn(day) > dayn(today) + 2)
		day = today
}

FILENAME == pf {
	if (NF >= 5 && nplans < 128 && !($1 in plim) && bplan($1, $2, $3, $4, $5)) {
		nplans++
		plim[$1] = $3 + 0
		plines[nplans] = "plan," $1 "," $2 "," num($3) "," $4 "," $5
	}
	next
}

FILENAME == qf {
	if (NF >= 3 && ($1 in plim) && !($1 in qdone) && bctr($2) && bpkey($3)) {
		qdone[$1] = 1
		nq++
		qlines[nq] = "quota," $1 "," num(($2 + 0 > plim[$1]) ? plim[$1] : $2) "," $3
	}
	next
}

FILENAME == sf {
	if (NF < 19 || nstats >= 4096 || ($1 in sdone))
		next
	if (!bkey($1, $2) || !bip($3) || !bname($4) || !bseen($9))
		next
	for (i = 5; i <= 19; i++)
		if (i != 9 && !bctr($i))
			next
	sdone[$1] = 1
	nstats++
	s = "stat," $1 "," $2 "," $3 "," $4
	for (i = 5; i <= 19; i++)
		s = s "," num($i)
	slines[nstats] = s
	next
}

END {
	put("capmon-backup,1," now)
	put("cfg,interval," num(interval))
	put("cfg,count_router," count_router)
	put("cfg,server_url," server_url)
	put("cfg,server_pin," server_pin)
	put("cfg,server_enabled," server_enabled)
	put("cfg,router_id," router_id)
	put("cfg,extra_dev," extra_dev)
	for (i = 1; i <= nplans; i++)
		put(plines[i])
	put("meta," since "," day)
	for (i = 1; i <= nstats; i++)
		put(slines[i])
	for (i = 1; i <= nq; i++)
		put(qlines[i])
	for (i = 1; i <= n; i++)
		print out[i]
	print "end," n
}
