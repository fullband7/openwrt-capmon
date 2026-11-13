#!/bin/sh

REPO_API="https://api.github.com/repos/fullband7/openwrt-capmon/releases/latest"
URL_PREFIX="https://github.com/fullband7/openwrt-capmon/releases/download/"

KEY_APK='-----BEGIN PUBLIC KEY-----
MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAEyIrN0Z/fqpDzB/9IUbViZKj3YgRF
tRW/onSXkQgpTAo5v8TVX4O1qMICi0YMdhpDMaEqugInL2fCO/XlPJ0CmA==
-----END PUBLIC KEY-----'

KEY_IPK='untrusted comment: capmon package signing key (ipk) public key
RWRx7zZpnNjIJU6JWYJ/3leIB5Ok790mOROKq6wb+/Ey7YzsQ05KCWku'

say() {
	printf '\033[%sm%s\033[0m\n' "$1" "$2"
}

fail() {
	say "1;31" "Error: $1"
	exit 1
}

[ "$(id -u)" = "0" ] || fail "This installer must be run as root."

TMP_DIR=$(mktemp -d /tmp/capmon-install.XXXXXX) || fail "Cannot create a temporary directory."
trap 'rm -rf "$TMP_DIR"' EXIT
trap 'exit 1' INT TERM HUP

say "38;2;38;147;255" "Capmon Installer"

RELEASE=$(wget -qO- "$REPO_API" 2>/dev/null)
[ -n "$RELEASE" ] || fail "Cannot reach the GitHub API. Check your internet connection and HTTPS support."

download_asset() {
	ext="$1"
	var="${2:-PKG_FILE}"
	url=$(printf '%s' "$RELEASE" | jsonfilter -e '@.assets[*].browser_download_url' 2>/dev/null | grep -E "\\.$ext\$" | head -n 1)

	[ -n "$url" ] || fail "No .${ext} file found in the latest release!"

	case "$url" in
		"$URL_PREFIX"?*) ;;
		*) fail "The release file is not hosted in the official repository." ;;
	esac

	dest="$TMP_DIR/luci-app-capmon.$ext"
	echo "Downloading: $url"
	wget -O "$dest" "$url" && [ -s "$dest" ] || fail "Download failed!"
	eval "$var=\$dest"
}

if command -v apk >/dev/null 2>&1; then
	echo "Detected: apk (OpenWrt 25.12)"

	echo "Installing the embedded public key"
	mkdir -p /etc/apk/keys || fail "Cannot create /etc/apk/keys."
	printf '%s\n' "$KEY_APK" > /etc/apk/keys/capmon.pem || fail "Cannot install the public key."
	chmod 0644 /etc/apk/keys/capmon.pem

	download_asset apk
	apk add "$PKG_FILE" || fail "Package signature verification or installation failed!"
elif command -v opkg >/dev/null 2>&1; then
	echo "Detected: opkg (OpenWrt 24.10)"
	command -v usign >/dev/null 2>&1 || fail "usign is required to verify the package signature but was not found."

	echo "Installing the embedded public key"
	printf '%s\n' "$KEY_IPK" > "$TMP_DIR/capmon-public.key" || fail "Cannot write the public key."
	KEY_FP=$(usign -F -p "$TMP_DIR/capmon-public.key") && [ -n "$KEY_FP" ] || fail "Cannot read the public key fingerprint."
	mkdir -p /etc/opkg/keys || fail "Cannot create /etc/opkg/keys."
	cp "$TMP_DIR/capmon-public.key" "/etc/opkg/keys/$KEY_FP" || fail "Cannot install the public key."
	chmod 0644 "/etc/opkg/keys/$KEY_FP"

	download_asset ipk
	download_asset ipk.sig SIG_FILE

	usign -V -p "/etc/opkg/keys/$KEY_FP" -m "$PKG_FILE" -x "$SIG_FILE" || fail "Package signature verification FAILED! The file may be corrupted or tampered with."
	echo "Signature verified."
	opkg install "$PKG_FILE" || fail "Package installation failed!"
else
	fail "Neither apk nor opkg found!"
fi

chmod 0755 /usr/libexec/rpcd/capmon 2>/dev/null
rm -f /tmp/luci-indexcache /tmp/luci-indexcache.* 2>/dev/null
rm -rf /tmp/luci-modulecache/ 2>/dev/null
[ -x /etc/init.d/rpcd ] && /etc/init.d/rpcd restart 2>/dev/null

say "1;32" "Capmon Installed Successfully!"
