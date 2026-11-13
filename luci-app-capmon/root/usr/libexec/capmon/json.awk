function clean(s) {
	gsub(/[^A-Za-z0-9._:-]/, "", s)
	return s
}

function cleanname(s) {
	gsub(/[^A-Za-z0-9 ._-]/, "", s)
	return substr(s, 1, 32)
}

BEGIN {
	FS = "\t"
	n = 0
	np = 0
	tu = 0
	td = 0
	ttu = 0
	ttd = 0
	tyu = 0
	tyd = 0
	tlu = 0
	tld = 0
	tpu = 0
	tpd = 0
}

FILENAME == qf {
	if (NF >= 3)
		qused[$1] = $2 + 0
	next
}

FILENAME == pf {
	if (NF >= 5) {
		np++
		pmac[np] = clean($1)
		pname[np] = cleanname($2)
		plim[np] = $3 + 0
		pper[np] = clean($4)
		pen[np] = ($5 == "1") ? 1 : 0
	}
	next
}

NF >= 9 {
	n++
	rt[n] = ($1 == "router") ? "true" : "false"
	mac[n] = clean($2)
	ip[n] = clean($3)
	name[n] = clean($4)
	up[n] = $5 + 0
	dn[n] = $6 + 0
	dup[n] = $7 + 0
	ddn[n] = $8 + 0
	seen[n] = $9 + 0
	yu[n] = $10 + 0
	yd[n] = $11 + 0
	lu[n] = $14 + 0
	ld[n] = $15 + 0
	pu[n] = $18 + 0
	pd[n] = $19 + 0
	tu += $5
	td += $6
	ttu += $7
	ttd += $8
	tyu += $10
	tyd += $11
	tlu += $14
	tld += $15
	tpu += $18
	tpd += $19
}

END {
	printf "{\"since\":%.0f,\"day\":\"%s\",\"now\":%.0f,", since + 0, clean(day), now + 0
	printf "\"acct\":%s,\"active\":%s,\"enabled\":%s,\"offload\":\"%s\",", (acct == 1 ? "true" : "false"), (active == 1 ? "true" : "false"), (en == 1 ? "true" : "false"), clean(offload)
	printf "\"total\":{\"up\":%.0f,\"dn\":%.0f,\"tup\":%.0f,\"tdn\":%.0f,\"yup\":%.0f,\"ydn\":%.0f,\"lup\":%.0f,\"ldn\":%.0f,\"pup\":%.0f,\"pdn\":%.0f},\"clients\":[", tu, td, ttu, ttd, tyu, tyd, tlu, tld, tpu, tpd
	for (i = 1; i <= n; i++) {
		if (i > 1)
			printf ","
		printf "{\"mac\":\"%s\",\"ip\":\"%s\",\"name\":\"%s\",\"router\":%s,\"up\":%.0f,\"dn\":%.0f,\"tup\":%.0f,\"tdn\":%.0f,\"yup\":%.0f,\"ydn\":%.0f,\"lup\":%.0f,\"ldn\":%.0f,\"pup\":%.0f,\"pdn\":%.0f,\"seen\":%.0f}", mac[i], ip[i], name[i], rt[i], up[i], dn[i], dup[i], ddn[i], yu[i], yd[i], lu[i], ld[i], pu[i], pd[i], seen[i]
	}
	printf "],\"plans\":["
	for (i = 1; i <= np; i++) {
		if (i > 1)
			printf ","
		u = (pmac[i] in qused) ? qused[pmac[i]] : 0
		if (plim[i] > 0 && u > plim[i])
			u = plim[i]
		ex = (pen[i] == 1 && plim[i] > 0 && u >= plim[i]) ? "true" : "false"
		printf "{\"mac\":\"%s\",\"name\":\"%s\",\"limit\":%.0f,\"period\":\"%s\",\"enabled\":%s,\"used\":%.0f,\"exceeded\":%s}", pmac[i], pname[i], plim[i], pper[i], (pen[i] == 1 ? "true" : "false"), u, ex
	}
	printf "],\"sync\":{\"configured\":%s,\"disabled\":%s,\"restored\":%s,\"ok\":%.0f,\"try\":%.0f,\"error\":\"%s\"}}\n", (sc == 1 ? "true" : "false"), (sd == 1 ? "true" : "false"), (rs == 1 ? "true" : "false"), sok + 0, stry + 0, clean(serr)
}
