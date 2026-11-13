function clean(s) {
	gsub(/[^A-Za-z0-9 ._:-]/, "", s)
	return s
}

function emit(type, key, name, ip, up, dn, tup, tdn, seen, limit, period, enabled, used, pkey, since, day, yup, ydn, mup, mdn, lup, ldn, wup, wdn, pup, pdn) {
	printf "%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s\n", type, key, name, ip, up, dn, tup, tdn, seen, limit, period, enabled, used, pkey, since, day, yup, ydn, mup, mdn, lup, ldn, wup, wdn, pup, pdn
}

function num(v) {
	return sprintf("%.0f", v + 0)
}

BEGIN {
	FS = "\t"
	np = 0
	nc = 0
}

FILENAME == qf {
	if (NF >= 3) {
		qused[$1] = $2 + 0
		qkey[$1] = $3
	}
	next
}

FILENAME == pf {
	if (NF >= 5) {
		np++
		pmac[np] = clean($1)
		pname[np] = clean($2)
		plim[np] = $3 + 0
		pper[np] = clean($4)
		pen[np] = ($5 == "1") ? 1 : 0
	}
	next
}

NF >= 9 {
	nc++
	ckey[nc] = clean($1)
	cname[nc] = clean($4)
	ip = clean($3)
	cip[nc] = (ip == "") ? "-" : ip
	cup[nc] = $5
	cdn[nc] = $6
	ctup[nc] = $7
	ctdn[nc] = $8
	cseen[nc] = $9
	cyup[nc] = $10
	cydn[nc] = $11
	cmup[nc] = $12
	cmdn[nc] = $13
	clup[nc] = $14
	cldn[nc] = $15
	cwup[nc] = $16
	cwdn[nc] = $17
	cpup[nc] = $18
	cpdn[nc] = $19
}

END {
	print header
	emit("meta", clean(id), "", "", "", "", "", "", "", "", "", "", "", "", num(since), clean(day), "", "", "", "", "", "", "", "", "", "")
	for (i = 1; i <= nc; i++)
		emit("client", ckey[i], cname[i], cip[i], num(cup[i]), num(cdn[i]), num(ctup[i]), num(ctdn[i]), num(cseen[i]), "", "", "", "", "", "", "", num(cyup[i]), num(cydn[i]), num(cmup[i]), num(cmdn[i]), num(clup[i]), num(cldn[i]), num(cwup[i]), num(cwdn[i]), num(cpup[i]), num(cpdn[i]))
	for (i = 1; i <= np; i++) {
		m = pmac[i]
		u = (m in qused) ? qused[m] : 0
		k = (m in qkey) ? clean(qkey[m]) : "0"
		emit("plan", m, pname[i], "", "", "", "", "", "", num(plim[i]), pper[i], pen[i], num(u), k, "", "", "", "", "", "", "", "", "", "", "", "")
	}
}
