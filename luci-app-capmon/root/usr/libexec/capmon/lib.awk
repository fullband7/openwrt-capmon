function dayn(ymd,   y, m, d, a) {
	if (length(ymd) != 8 || ymd !~ /^[0-9]+$/)
		return 0
	y = substr(ymd, 1, 4) + 0
	m = substr(ymd, 5, 2) + 0
	d = substr(ymd, 7, 2) + 0
	a = (m < 3) ? 1 : 0
	y -= a
	m += 12 * a - 3
	return 365 * y + int(y / 4) - int(y / 100) + int(y / 400) + int((153 * m + 2) / 5) + d
}

function weekid(ymd,   days) {
	days = dayn(ymd)
	if (days == 0)
		return 0
	return days - (days + 1) % 7
}
