function ismac(s) {
	return (s ~ /^[0-9a-f][0-9a-f]:[0-9a-f][0-9a-f]:[0-9a-f][0-9a-f]:[0-9a-f][0-9a-f]:[0-9a-f][0-9a-f]:[0-9a-f][0-9a-f]$/)
}

function isnum(s) {
	return (s ~ /^[0-9]+$/)
}

function isctr(s) {
	return (s ~ /^[0-9]+$/ && length(s) <= 15 && s + 0 <= 9000000000000000)
}

function isopt(s) {
	return (s == "" || isctr(s))
}

function isname(s) {
	return (s ~ /^[A-Za-z0-9 ._-]*$/)
}

function delta(lv, pv,   d) {
	d = lv - pv
	if (d < 0 || d > 9000000000000000)
		d = 0
	return d
}

function readlocal(   line, n, a, k) {
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
	pf = run "/plans"
	while ((getline line < pf) > 0) {
		n = split(line, a, "\t")
		if (n >= 5 && ismac(a[1])) {
			pname[a[1]] = a[2]
			plim[a[1]] = a[3] + 0
			pper[a[1]] = a[4]
			pen[a[1]] = a[5]
		}
	}
	close(pf)
	qf = run "/quota"
	while ((getline line < qf) > 0) {
		n = split(line, a, "\t")
		if (n >= 3) {
			lused[a[1]] = a[2] + 0
			lkey[a[1]] = a[3]
		}
	}
	close(qf)
	mf = run "/meta"
	getline lsince < mf
	getline lday < mf
	close(mf)
	lsince = lsince + 0
	ps = run "/pushed.stats"
	while ((getline line < ps) > 0) {
		n = split(line, a, "\t")
		if (n >= 15 && isctr(a[2]) && isctr(a[3]) && isctr(a[4]) && isctr(a[5])) {
			k = a[1]
			psup[k] = a[2] + 0
			psdn[k] = a[3] + 0
			ptup[k] = a[4] + 0
			ptdn[k] = a[5] + 0
			pyup[k] = a[6] + 0
			pydn[k] = a[7] + 0
			pmup[k] = a[8] + 0
			pmdn[k] = a[9] + 0
			plup[k] = a[10] + 0
			pldn[k] = a[11] + 0
			pwup[k] = a[12] + 0
			pwdn[k] = a[13] + 0
			ppup[k] = a[14] + 0
			ppdn[k] = a[15] + 0
		}
	}
	close(ps)
	pq = run "/pushed.quota"
	while ((getline line < pq) > 0) {
		n = split(line, a, "\t")
		if (n >= 3 && isctr(a[2]) && isnum(a[3])) {
			pused[a[1]] = a[2] + 0
			pkey[a[1]] = a[3]
		}
	}
	close(pq)
}

BEGIN {
	FS = ","
	readlocal()
}

FNR == 1 { next }

{
	sub(/\r$/, "")
}

$1 == "meta" {
	if (isnum($15))
		ssince = $15 + 0
	if ($16 ~ /^[0-9]+$/)
		sday = $16
	next
}

$1 == "client" {
	k = $2
	if (!(ismac(k) || k == "router" || k ~ /^[0-9a-f:.]+$/))
		next
	if (!isname($3) || !isctr($5) || !isctr($6) || !isctr($7) || !isctr($8) || !isctr($9) || !isopt($17) || !isopt($18) || !isopt($19) || !isopt($20) || !isopt($21) || !isopt($22) || !isopt($23) || !isopt($24) || !isopt($25) || !isopt($26))
		next
	cn[k] = ($3 == "") ? "-" : $3
	ci[k] = ($4 == "") ? "-" : $4
	cu[k] = $5 + 0
	cd[k] = $6 + 0
	cxu[k] = $7 + 0
	cxd[k] = $8 + 0
	cs[k] = $9 + 0
	cyu[k] = $17 + 0
	cyd[k] = $18 + 0
	cmu[k] = $19 + 0
	cmd[k] = $20 + 0
	clu[k] = $21 + 0
	cld[k] = $22 + 0
	cwu[k] = $23 + 0
	cwd[k] = $24 + 0
	cpu[k] = $25 + 0
	cpd[k] = $26 + 0
	next
}

$1 == "plan" {
	m = $2
	if (!ismac(m) || !isname($3) || !isctr($10) || !isctr($13))
		next
	if ($11 != "none" && $11 != "daily" && $11 != "weekly" && $11 != "monthly")
		next
	if (($12 != "0" && $12 != "1") || $14 !~ /^[0-9]+$/)
		next
	susd[m] = $13 + 0
	skey[m] = $14
	next
}

END {
	sameday = (sday == lday)
	prevday = (sday == yday)
	smon = substr(sday, 1, 6)
	samemon = (smon == substr(lday, 1, 6))
	prevmon = (smon == pmon)
	swk = weekid(sday)
	lwk = weekid(lday)
	samewk = (swk == lwk)
	prevwk = (swk == lwk - 7)
	po = run "/pushed.stats.merge"
	printf "" > po
	for (k in cu) {
		if (k in smac) {
			lu = sup[k]
			ld = sdn[k]
			lxu = tup[k]
			lxd = tdn[k]
			lyu = yup[k]
			lyd = ydn[k]
			lmu = mup[k]
			lmd = mdn[k]
			llu = lup[k]
			lld = ldn[k]
			lwu = wup[k]
			lwd = wdn[k]
			lpu = pup[k]
			lpd = pdn[k]
			if (sname[k] == "-")
				sname[k] = cn[k]
			if (sip[k] == "-" || sip[k] == "")
				sip[k] = ci[k]
			if (cs[k] > sseen[k])
				sseen[k] = cs[k]
		} else {
			smac[k] = ismac(k) ? k : "-"
			sip[k] = ci[k]
			sname[k] = cn[k]
			lu = 0
			ld = 0
			lxu = 0
			lxd = 0
			lyu = 0
			lyd = 0
			lmu = 0
			lmd = 0
			llu = 0
			lld = 0
			lwu = 0
			lwd = 0
			lpu = 0
			lpd = 0
			sseen[k] = cs[k]
			tup[k] = 0
			tdn[k] = 0
			yup[k] = 0
			ydn[k] = 0
			mup[k] = 0
			mdn[k] = 0
			lup[k] = 0
			ldn[k] = 0
			wup[k] = 0
			wdn[k] = 0
			pup[k] = 0
			pdn[k] = 0
		}
		sup[k] = cu[k] + delta(lu, (k in psup) ? psup[k] : 0)
		sdn[k] = cd[k] + delta(ld, (k in psdn) ? psdn[k] : 0)
		if (sameday) {
			tup[k] = cxu[k] + delta(lxu, (k in ptup) ? ptup[k] : 0)
			tdn[k] = cxd[k] + delta(lxd, (k in ptdn) ? ptdn[k] : 0)
			yup[k] = cyu[k] + delta(lyu, (k in pyup) ? pyup[k] : 0)
			ydn[k] = cyd[k] + delta(lyd, (k in pydn) ? pydn[k] : 0)
			pu_y = cyu[k]
			pd_y = cyd[k]
		} else if (prevday) {
			yup[k] = cxu[k] + lyu
			ydn[k] = cxd[k] + lyd
			pu_y = cxu[k]
			pd_y = cxd[k]
		} else {
			pu_y = 0
			pd_y = 0
		}
		if (samemon) {
			mup[k] = cmu[k] + delta(lmu, (k in pmup) ? pmup[k] : 0)
			mdn[k] = cmd[k] + delta(lmd, (k in pmdn) ? pmdn[k] : 0)
			lup[k] = clu[k] + delta(llu, (k in plup) ? plup[k] : 0)
			ldn[k] = cld[k] + delta(lld, (k in pldn) ? pldn[k] : 0)
			pu_m = cmu[k]
			pd_m = cmd[k]
			pu_l = clu[k]
			pd_l = cld[k]
		} else if (prevmon) {
			lup[k] = cmu[k] + llu
			ldn[k] = cmd[k] + lld
			pu_m = 0
			pd_m = 0
			pu_l = cmu[k]
			pd_l = cmd[k]
		} else {
			pu_m = 0
			pd_m = 0
			pu_l = 0
			pd_l = 0
		}
		if (samewk) {
			wup[k] = cwu[k] + delta(lwu, (k in pwup) ? pwup[k] : 0)
			wdn[k] = cwd[k] + delta(lwd, (k in pwdn) ? pwdn[k] : 0)
			pup[k] = cpu[k] + delta(lpu, (k in ppup) ? ppup[k] : 0)
			pdn[k] = cpd[k] + delta(lpd, (k in ppdn) ? ppdn[k] : 0)
			pu_w = cwu[k]
			pd_w = cwd[k]
			pu_p = cpu[k]
			pd_p = cpd[k]
		} else if (prevwk) {
			pup[k] = cwu[k] + lpu
			pdn[k] = cwd[k] + lpd
			pu_w = 0
			pd_w = 0
			pu_p = cwu[k]
			pd_p = cwd[k]
		} else {
			pu_w = 0
			pd_w = 0
			pu_p = 0
			pd_p = 0
		}
		printf "%s\t%.0f\t%.0f\t%.0f\t%.0f\t%.0f\t%.0f\t%.0f\t%.0f\t%.0f\t%.0f\t%.0f\t%.0f\t%.0f\t%.0f\n", k, cu[k], cd[k], (sameday ? cxu[k] : 0), (sameday ? cxd[k] : 0), pu_y, pd_y, pu_m, pd_m, pu_l, pd_l, pu_w, pd_w, pu_p, pd_p > po
	}
	close(po)
	out = run "/stats.merge"
	printf "" > out
	for (k in smac)
		printf "%s\t%s\t%s\t%s\t%.0f\t%.0f\t%.0f\t%.0f\t%.0f\t%.0f\t%.0f\t%.0f\t%.0f\t%.0f\t%.0f\t%.0f\t%.0f\t%.0f\t%.0f\n", k, smac[k], sip[k], sname[k], sup[k], sdn[k], tup[k], tdn[k], sseen[k], yup[k], ydn[k], mup[k], mdn[k], lup[k], ldn[k], wup[k], wdn[k], pup[k], pdn[k] > out
	close(out)
	oq = run "/quota.merge"
	opq = run "/pushed.quota.merge"
	printf "" > oq
	printf "" > opq
	for (m in pname) {
		if (plim[m] <= 0)
			continue
		lu = (m in lused) ? lused[m] : 0
		if (m in lkey)
			lk = lkey[m]
		else if (m in skey)
			lk = skey[m]
		else
			lk = "0"
		pu = ((m in pused) && pkey[m] == lk) ? pused[m] : 0
		if ((m in susd) && skey[m] == lk)
			u = susd[m] + delta(lu, pu)
		else
			u = lu
		if (u > plim[m])
			u = plim[m]
		printf "%s\t%.0f\t%s\n", m, u, lk > oq
		if (m in susd)
			printf "%s\t%.0f\t%s\n", m, susd[m], skey[m] > opq
	}
	close(oq)
	close(opq)
	since = lsince
	if (ssince > 0 && (since <= 0 || ssince < since))
		since = ssince
	out = run "/meta.merge"
	printf "%.0f\n%s\n", since, lday > out
	close(out)
}
