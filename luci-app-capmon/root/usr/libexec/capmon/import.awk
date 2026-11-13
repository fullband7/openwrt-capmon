function fail(why) {
	reason = NR ": " why
	bad = 1
	exit 1
}

function num(v) {
	return sprintf("%.0f", v + 0)
}

BEGIN {
	FS = ","
	rank = 0
	slop = now + 172800
	statout = run "/stats.imp"
	printf "" > statout
}

{
	bytes += length($0) + 1
	if (done)
		fail("data after end")
	if (length($0) > 400 || $0 !~ /^[ -~]+$/)
		fail("invalid characters")
	if (NR == 1) {
		if (NF != 3 || $1 != "capmon-backup" || $2 != "1" || $3 !~ /^[1-9][0-9]*$/ || length($3) != 10 || $3 + 0 > slop)
			fail("invalid header")
		next
	}
	t = $1
	r = (t == "cfg") ? 1 : (t == "plan") ? 2 : (t == "meta") ? 3 : (t == "stat") ? 4 : (t == "quota") ? 5 : (t == "end") ? 6 : 0
	if (r == 0 || r < rank)
		fail("unexpected record")
	rank = r
	if (t == "cfg") {
		if (NF != 3 || !bcfg($2, $3) || ($2 in cfg))
			fail("invalid setting")
		cfg[$2] = $3
		ncfg++
	} else if (t == "plan") {
		if (NF != 6 || !bplan($2, $3, $4, $5, $6) || ($2 in plim) || nplans >= 128)
			fail("invalid plan")
		nplans++
		plim[$2] = $4 + 0
		pord[nplans] = $2
		pname[$2] = $3
		pper[$2] = $5
		pen[$2] = $6
	} else if (t == "meta") {
		if (seenmeta || NF != 3 || !bdig($2) || length($2) > 10 || $2 + 0 < 946684800 || $2 + 0 > slop || !bday($3) || dayn($3) > dayn(today) + 2)
			fail("invalid meta")
		seenmeta = 1
		msince = $2 + 0
		mday = $3
	} else if (t == "stat") {
		if (NF != 20 || nstats >= 4096 || ($2 in sdone) || !bkey($2, $3) || !bip($4) || !bname($5) || !bseen($10) || $10 + 0 > slop)
			fail("invalid client")
		for (i = 6; i <= 20; i++)
			if (i != 10 && !bctr($i))
				fail("invalid counter")
		sdone[$2] = 1
		nstats++
		s = $2 "\t" $3 "\t" $4 "\t" $5
		for (i = 6; i <= 20; i++)
			s = s "\t" num($i)
		print s > statout
	} else if (t == "quota") {
		if (NF != 4 || !($2 in plim) || ($2 in qdone) || !bctr($3) || $3 + 0 > plim[$2] || !bpkey($4))
			fail("invalid quota")
		qdone[$2] = 1
		nq++
		qrow[nq] = $2 "\t" num($3) "\t" $4
	} else {
		if (NF != 2 || !bdig($2) || length($2) > 5 || $2 + 0 != NR - 1)
			fail("invalid trailer")
		done = 1
	}
}

END {
	close(statout)
	if (!bad && (!done || ncfg != 7 || !seenmeta || bytes != fsize)) {
		reason = "incomplete file"
		bad = 1
	}
	if (bad) {
		print reason > "/dev/stderr"
		exit 1
	}
	qo = run "/quota.imp"
	printf "" > qo
	for (i = 1; i <= nq; i++)
		print qrow[i] > qo
	close(qo)
	mo = run "/meta.imp"
	printf "%.0f\n%s\n", msince, mday > mo
	close(mo)
	co = run "/cfg.imp"
	printf "" > co
	n = split(olds, a, " ")
	for (i = 1; i <= n; i++)
		if (a[i] ~ /^[A-Za-z0-9_]+$/)
			print "delete capmon." a[i] > co
	print "set capmon.main=capmon" > co
	print "set capmon.main.interval='" num(cfg["interval"]) "'" > co
	print "set capmon.main.count_router='" cfg["count_router"] "'" > co
	print "set capmon.main.server_url='" cfg["server_url"] "'" > co
	print "set capmon.main.server_pin='" cfg["server_pin"] "'" > co
	print "set capmon.main.router_id='" cfg["router_id"] "'" > co
	chg = (cfg["server_url"] != ocurl || cfg["router_id"] != ocid)
	en = (chg || cfg["server_url"] == "") ? "0" : cfg["server_enabled"]
	print "set capmon.main.server_enabled='" en "'" > co
	if (cfg["extra_dev"] != "")
		print "set capmon.main.extra_dev='" cfg["extra_dev"] "'" > co
	for (i = 1; i <= nplans; i++) {
		m = pord[i]
		sec = m
		gsub(/:/, "", sec)
		print "set capmon.plan_" sec "=plan" > co
		print "set capmon.plan_" sec ".mac='" m "'" > co
		print "set capmon.plan_" sec ".name='" pname[m] "'" > co
		print "set capmon.plan_" sec ".limit='" num(plim[m]) "'" > co
		print "set capmon.plan_" sec ".period='" pper[m] "'" > co
		print "set capmon.plan_" sec ".enabled='" pen[m] "'" > co
	}
	close(co)
	print (chg ? "chg" : "same")
}
