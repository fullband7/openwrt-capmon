function san(s) {
	gsub(/[^A-Za-z0-9._-]/, "", s)
	return substr(s, 1, 63)
}

function isv4(s) {
	return (s ~ /^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$/)
}

function v4ok(s,   a, i) {
	if (!isv4(s))
		return 0
	split(s, a, ".")
	for (i = 1; i <= 4; i++)
		if (a[i] + 0 > 255)
			return 0
	return 1
}

function isv6(s) {
	return (s ~ /^[0-9a-f:.]+$/ && index(s, ":") > 0)
}

function ismac(s) {
	if (s == "00:00:00:00:00:00")
		return 0
	return (s ~ /^[0-9a-f][0-9a-f]:[0-9a-f][0-9a-f]:[0-9a-f][0-9a-f]:[0-9a-f][0-9a-f]:[0-9a-f][0-9a-f]:[0-9a-f][0-9a-f]$/)
}

function perkey(per) {
	if (per == "daily")
		return kd
	if (per == "weekly")
		return kw
	if (per == "monthly")
		return km
	return "0"
}

function v4n(s,   a) {
	split(s, a, ".")
	return ((a[1] * 256 + a[2]) * 256 + a[3]) * 256 + a[4]
}

function pad4(g) {
	return substr("0000", 1, 4 - length(g)) g
}

function hexv(c) {
	return index("0123456789abcdef", c) - 1
}

function v6x(s,   p, l, r, nl, nr, z, i, la, ra, out, g, a) {
	if (s !~ /^[0-9a-f:.]+$/)
		return ""
	if (index(s, ".") > 0) {
		i = match(s, /[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$/)
		if (i == 0)
			return ""
		g = substr(s, i)
		split(g, a, ".")
		s = substr(s, 1, i - 1) sprintf("%x:%x", a[1] * 256 + a[2], a[3] * 256 + a[4])
	}
	out = ""
	p = index(s, "::")
	if (p > 0) {
		l = substr(s, 1, p - 1)
		r = substr(s, p + 2)
		nl = (l == "") ? 0 : split(l, la, ":")
		nr = (r == "") ? 0 : split(r, ra, ":")
		z = 8 - nl - nr
		if (z < 1)
			return ""
		for (i = 1; i <= nl; i++)
			out = out pad4(la[i])
		for (i = 1; i <= z; i++)
			out = out "0000"
		for (i = 1; i <= nr; i++)
			out = out pad4(ra[i])
	} else {
		if (split(s, la, ":") != 8)
			return ""
		for (i = 1; i <= 8; i++)
			out = out pad4(la[i])
	}
	return (length(out) == 32) ? out : ""
}

function addlan(fam, addr, len,   h, f, r) {
	len = len + 0
	if (fam == "inet") {
		if (!v4ok(addr) || len < 0 || len > 32)
			return
		l4s[nl4] = P2[32 - len]
		l4n[nl4] = int(v4n(addr) / l4s[nl4]) * l4s[nl4]
		nl4++
	} else {
		h = v6x(addr)
		if (h == "" || len < 0 || len > 128)
			return
		f = int(len / 4)
		r = len - f * 4
		l6f[nl6] = f
		l6r[nl6] = r
		l6p[nl6] = substr(h, 1, f)
		l6v[nl6] = (r > 0) ? int(hexv(substr(h, f + 1, 1)) / P2[4 - r]) : 0
		nl6++
	}
}

function cls4(a,   n, i) {
	n = v4n(a)
	if (n < 16777216 || (n >= 2130706432 && n < 2147483648) || (n >= 2851995648 && n < 2852061184) || n >= 3758096384)
		return "x"
	if (a in own4)
		return "r"
	for (i = 0; i < nl4; i++)
		if (int(n / l4s[i]) * l4s[i] == l4n[i])
			return "l"
	return "w"
}

function cls6(h,   i) {
	if (h == "")
		return "x"
	if (h == "00000000000000000000000000000000" || h == "00000000000000000000000000000001")
		return "x"
	if (substr(h, 1, 2) == "ff")
		return "x"
	if (substr(h, 1, 2) == "fe" && index("89ab", substr(h, 3, 1)) > 0)
		return "x"
	if (h in own6)
		return "r"
	for (i = 0; i < nl6; i++) {
		if (substr(h, 1, l6f[i]) != l6p[i])
			continue
		if (l6r[i] == 0 || int(hexv(substr(h, l6f[i] + 1, 1)) / P2[4 - l6r[i]]) == l6v[i])
			return "l"
	}
	return "w"
}

function mk(key, mac, ad) {
	smac[key] = mac
	sip[key] = ad
	sname[key] = "-"
	sup[key] = 0
	sdn[key] = 0
	tup[key] = 0
	tdn[key] = 0
	yup[key] = 0
	ydn[key] = 0
	mup[key] = 0
	mdn[key] = 0
	lup[key] = 0
	ldn[key] = 0
	wup[key] = 0
	wdn[key] = 0
	pup[key] = 0
	pdn[key] = 0
	sseen[key] = 0
}

function drop(key) {
	delete smac[key]
	delete sip[key]
	delete sname[key]
	delete sup[key]
	delete sdn[key]
	delete tup[key]
	delete tdn[key]
	delete yup[key]
	delete ydn[key]
	delete mup[key]
	delete mdn[key]
	delete lup[key]
	delete ldn[key]
	delete wup[key]
	delete wdn[key]
	delete pup[key]
	delete pdn[key]
	delete sseen[key]
}

function credit(ad, up, dn,   mac, key) {
	mac = ""
	if (ad == "router") {
		key = "router"
		if (!(key in smac))
			mk(key, "-", rip)
	} else {
		if (ad in a2m)
			mac = a2m[ad]
		else if (ad in l2m)
			mac = l2m[ad]
		else if (index(ad, ":") > 0 && (v6x(ad) in x2m))
			mac = x2m[v6x(ad)]
		if (mac != "") {
			key = mac
			if (!(key in smac))
				mk(key, mac, ad)
			if ((ad in smac) && smac[ad] == "-" && ad != key) {
				sup[key] += sup[ad]
				sdn[key] += sdn[ad]
				tup[key] += tup[ad]
				tdn[key] += tdn[ad]
				yup[key] += yup[ad]
				ydn[key] += ydn[ad]
				mup[key] += mup[ad]
				mdn[key] += mdn[ad]
				lup[key] += lup[ad]
				ldn[key] += ldn[ad]
				wup[key] += wup[ad]
				wdn[key] += wdn[ad]
				pup[key] += pup[ad]
				pdn[key] += pdn[ad]
				if (sseen[ad] > sseen[key])
					sseen[key] = sseen[ad]
				drop(ad)
			}
		} else {
			key = ad
			if (!(key in smac))
				mk(key, "-", ad)
		}
		if (isv4(ad))
			sip[key] = ad
		else if (sip[key] == "-" || sip[key] == "")
			sip[key] = ad
	}
	sup[key] += up
	tup[key] += up
	sdn[key] += dn
	tdn[key] += dn
	mup[key] += up
	mdn[key] += dn
	wup[key] += up
	wdn[key] += dn
	sseen[key] = now
	if (mac != "") {
		if (mac in qen)
			qd[mac] += up + dn
		if ((mac in blk0) && up + dn > 0)
			leak[ad] = 1
	}
}

function flow(   fam, i, e, k, v, ns, nd, nb, s1, s2, b1, b2, ca, cc, du, dd, host, inv) {
	fam = $1
	if (fam != "ipv4" && fam != "ipv6")
		return
	ctlines++
	for (i = 4; i <= NF; i++) {
		e = index($i, "=")
		if (e == 0)
			continue
		k = substr($i, 1, e - 1)
		v = substr($i, e + 1)
		if (k == "src") {
			if (++ns == 1)
				s1 = v
			else if (ns == 2)
				s2 = v
		} else if (k == "dst") {
			nd++
		} else if (k == "bytes" && v ~ /^[0-9]+$/) {
			if (++nb == 1)
				b1 = v + 0
			else if (nb == 2)
				b2 = v + 0
		}
	}
	if (nb < 2 || ns < 2 || nd < 1)
		return
	ctbytes++
	if (fam == "ipv6") {
		s1 = tolower(s1)
		s2 = tolower(s2)
		ca = cls6(v6x(s1))
		cc = cls6(v6x(s2))
	} else {
		if (!v4ok(s1) || !v4ok(s2))
			return
		ca = cls4(s1)
		cc = cls4(s2)
	}
	if (ca == "l" && cc == "w") {
		host = s1
		inv = 0
	} else if (ca == "w" && cc == "l") {
		host = s2
		inv = 1
	} else if (crouter == 1 && ca == "r" && cc == "w") {
		host = "router"
		inv = 0
	} else if (crouter == 1 && ca == "w" && cc == "r") {
		host = "router"
		inv = 1
	} else {
		return
	}
	if (baseline == 1)
		return
	du = b1
	dd = b2
	if (du == 0 && dd == 0)
		return
	if (inv == 0)
		credit(host, du, dd)
	else
		credit(host, dd, du)
}

function addip(ad) {
	if (substr(ad, 1, 5) == "fe80:" || (ad in done))
		return
	if (v4ok(ad))
		v4s = v4s (v4s != "" ? ", " : "") ad
	else if (isv6(ad) && v6x(ad) != "")
		v6s = v6s (v6s != "" ? ", " : "") ad
	else
		return
	done[ad] = 1
	print "ip\t" ad > bout
	if (!(ad in oldip) && !(ad in killed)) {
		killed[ad] = 1
		print ad > kout
	}
}

BEGIN {
	nl4 = 0
	nl6 = 0
	ctlines = 0
	ctbytes = 0
	P2[0] = 1
	for (i = 1; i <= 32; i++)
		P2[i] = P2[i - 1] * 2
	sf = run "/stats"
	while ((getline line < sf) > 0) {
		n = split(line, a, "\t")
		if (n >= 9) {
			k = a[1]
			smac[k] = a[2]
			sip[k] = a[3]
			sname[k] = a[4]
			sup[k] = a[5] + 0
			sdn[k] = a[6] + 0
			tup[k] = a[7] + 0
			tdn[k] = a[8] + 0
			yup[k] = a[10] + 0
			ydn[k] = a[11] + 0
			mup[k] = a[12] + 0
			mdn[k] = a[13] + 0
			lup[k] = a[14] + 0
			ldn[k] = a[15] + 0
			wup[k] = a[16] + 0
			wdn[k] = a[17] + 0
			pup[k] = a[18] + 0
			pdn[k] = a[19] + 0
			sseen[k] = a[9] + 0
		}
	}
	close(sf)
	lf = run "/plans"
	while ((getline line < lf) > 0) {
		n = split(line, a, "\t")
		if (n >= 5 && ismac(a[1])) {
			plim[a[1]] = a[3] + 0
			pper[a[1]] = a[4]
			pen[a[1]] = a[5]
			if (a[5] == "1" && a[3] + 0 > 0)
				qen[a[1]] = 1
		}
	}
	close(lf)
	qf = run "/quota"
	while ((getline line < qf) > 0) {
		n = split(line, a, "\t")
		if (n >= 3) {
			qused[a[1]] = a[2] + 0
			qkey[a[1]] = a[3]
		}
	}
	close(qf)
	for (m in qen) {
		ck = perkey(pper[m])
		okey = (m in qkey) ? qkey[m] : ck
		if (okey == ck && (m in qused) && qused[m] >= plim[m])
			blk0[m] = 1
	}
	bf = run "/blocked"
	while ((getline line < bf) > 0) {
		n = split(line, a, "\t")
		if (n >= 2 && a[1] == "ip")
			oldip[a[2]] = 1
	}
	close(bf)
	if (sday != today) {
		for (k in smac) {
			yup[k] = (sday == yday) ? tup[k] : 0
			ydn[k] = (sday == yday) ? tdn[k] : 0
			tup[k] = 0
			tdn[k] = 0
		}
	}
	if (substr(sday, 1, 6) != substr(today, 1, 6)) {
		for (k in smac) {
			lup[k] = (substr(sday, 1, 6) == pmon) ? mup[k] : 0
			ldn[k] = (substr(sday, 1, 6) == pmon) ? mdn[k] : 0
			mup[k] = 0
			mdn[k] = 0
		}
	}
	wsd = weekid(sday)
	wtd = weekid(today)
	if (wsd != wtd) {
		for (k in smac) {
			pup[k] = (wsd == wtd - 7) ? wup[k] : 0
			pdn[k] = (wsd == wtd - 7) ? wdn[k] : 0
			wup[k] = 0
			wdn[k] = 0
		}
	}
	now = now + 0
	statout = run "/stats.new"
	quotaout = run "/quota.new"
	nftout = run "/block.new"
	bout = run "/blocked.new"
	kout = run "/kill.list"
	aout = run "/acct"
	printf "" > bout
	printf "" > kout
}

$0 == "@@ARP" { sec = "arp"; next }
$0 == "@@NB6" { sec = "nb6"; next }
$0 == "@@LEASE" { sec = "lease"; next }
$0 == "@@WAN" { sec = "wan"; next }
$0 == "@@ADDR" { sec = "addr"; next }
$0 == "@@CT" { sec = "ct"; next }

sec == "arp" && NF >= 4 {
	if (isv4($1) && $3 != "0x0") {
		m = tolower($4)
		if (ismac(m))
			a2m[$1] = m
	}
	next
}

sec == "nb6" && NF >= 4 {
	for (i = 1; i < NF; i++) {
		if ($i == "lladdr") {
			m = tolower($(i + 1))
			st = $NF
			if (ismac(m) && st != "FAILED" && st != "INCOMPLETE") {
				a2m[tolower($1)] = m
				x = v6x(tolower($1))
				if (x != "")
					x2m[x] = m
			}
			break
		}
	}
	next
}

sec == "lease" && NF >= 4 {
	m = tolower($2)
	ip = $3
	if (ismac(m) && isv4(ip)) {
		l2m[ip] = m
		if ($4 != "*") {
			h = san($4)
			if (h != "") {
				mname[m] = h
				iname[ip] = h
			}
		}
	}
	next
}

sec == "wan" {
	for (i = 1; i <= NF; i++)
		wan[$i] = 1
	next
}

sec == "addr" && NF >= 4 {
	dev = $2
	sub(/@.*/, "", dev)
	fam = $3
	ad = tolower($4)
	len = (fam == "inet") ? 32 : 128
	p = index(ad, "/")
	if (p > 0) {
		len = substr(ad, p + 1)
		ad = substr(ad, 1, p - 1)
	}
	if (fam == "inet" && v4ok(ad)) {
		own4[ad] = 1
		if (!(dev in wan) && dev != "lo") {
			addlan(fam, ad, len)
			if (rip == "")
				rip = ad
		}
	} else if (fam == "inet6") {
		x = v6x(ad)
		if (x != "") {
			own6[x] = 1
			if (!(dev in wan) && dev != "lo")
				addlan(fam, ad, len)
		}
	}
	next
}

sec == "ct" && NF >= 8 {
	flow()
	next
}

END {
	if (crouter == 1 && !("router" in smac))
		mk("router", "-", rip)
	if (crouter == 1 && ismac(rmac))
		smac["router"] = rmac
	if (crouter == 1 && rip != "" && (sip["router"] == "-" || sip["router"] == ""))
		sip["router"] = rip
	for (k in smac) {
		if (k == "router") {
			sname[k] = (rname != "") ? rname : "-"
			continue
		}
		if (smac[k] != "-") {
			if (smac[k] in mname)
				sname[k] = mname[smac[k]]
		} else if (sip[k] in iname) {
			sname[k] = iname[sip[k]]
		}
	}
	for (k in smac) {
		if (k == "router") {
			if (crouter != 1)
				continue
		} else if (sseen[k] > 0 && now - sseen[k] > 7776000) {
			continue
		}
		printf "%s\t%s\t%s\t%s\t%.0f\t%.0f\t%.0f\t%.0f\t%.0f\t%.0f\t%.0f\t%.0f\t%.0f\t%.0f\t%.0f\t%.0f\t%.0f\t%.0f\t%.0f\n", k, smac[k], sip[k], sname[k], sup[k], sdn[k], tup[k], tdn[k], sseen[k], yup[k], ydn[k], mup[k], mdn[k], lup[k], ldn[k], wup[k], wdn[k], pup[k], pdn[k] > statout
	}
	printf "" > quotaout
	for (m in plim) {
		ck = perkey(pper[m])
		okey = (m in qkey) ? qkey[m] : ck
		u = (okey == ck && (m in qused)) ? qused[m] : 0
		if (m in qd)
			u += qd[m]
		if (plim[m] > 0 && u > plim[m])
			u = plim[m]
		printf "%s\t%.0f\t%s\n", m, u, ck > quotaout
		if ((m in qen) && u >= plim[m])
			blk[m] = 1
	}
	v4s = ""
	v6s = ""
	ms = ""
	for (m in blk) {
		ms = ms (ms != "" ? ", " : "") m
		print "mac\t" m > bout
	}
	for (ad in a2m)
		if (a2m[ad] in blk)
			addip(ad)
	for (ad in l2m)
		if (!(ad in a2m) && (l2m[ad] in blk))
			addip(ad)
	for (ad in leak)
		if (!(ad in killed) && (v4ok(ad) || (isv6(ad) && v6x(ad) != ""))) {
			killed[ad] = 1
			print ad > kout
		}
	printf "flush set inet capmon blkmac\nflush set inet capmon blk4\nflush set inet capmon blk6\n" > nftout
	if (ms != "")
		printf "add element inet capmon blkmac { %s }\n", ms > nftout
	if (v4s != "")
		printf "add element inet capmon blk4 { %s }\n", v4s > nftout
	if (v6s != "")
		printf "add element inet capmon blk6 { %s }\n", v6s > nftout
	printf "%d\n", ((ctlines == 0 || ctbytes > 0) ? 1 : 0) > aout
	close(statout)
	close(quotaout)
	close(nftout)
	close(bout)
	close(kout)
	close(aout)
}
