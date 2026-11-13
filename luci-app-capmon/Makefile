include $(TOPDIR)/rules.mk

PKG_NAME:=luci-app-capmon
PKG_VERSION:=1.7.0
PKG_RELEASE:=2
PKG_LICENSE:=Apache-2.0
PKG_MAINTAINER:=Capmon Quota Manager

include $(INCLUDE_DIR)/package.mk

define Package/luci-app-capmon
  SECTION:=luci
  CATEGORY:=LuCI
  SUBMENU:=3. Applications
  TITLE:=LuCI Quota Manager - per-client internet statistics and data plans
  DEPENDS:=+luci-base +rpcd +firewall4 +curl +jshn +conntrack +cgi-io
  PKGARCH:=all
endef

define Package/luci-app-capmon/description
Advanced per-client quota for monitoring and managing internet upload and download traffic on LAN/Wi-Fi networks
endef

define Package/luci-app-capmon/conffiles
/etc/config/capmon
/etc/capmon/token
endef

define Build/Compile
endef

define Package/luci-app-capmon/install
	$(INSTALL_DIR) $(1)/www/luci-static/resources/capmon
	$(CP) ./htdocs/luci-static/resources/capmon/. $(1)/www/luci-static/resources/capmon/
	$(CP) ./root/. $(1)/
	chmod 0755 $(1)/etc/init.d/capmon $(1)/usr/sbin/capmon $(1)/usr/libexec/rpcd/capmon $(1)/etc/hotplug.d/iface/90-capmon $(1)/etc/hotplug.d/dhcp/90-capmon
	chmod 0600 $(1)/etc/config/capmon
	$(INSTALL_DIR) $(1)/usr/share/ucode/luci/template/capmon
	$(CP) ./ucode/template/capmon/. $(1)/usr/share/ucode/luci/template/capmon/
	$(SED) 's/@VERSION@/$(PKG_VERSION)-$(PKG_RELEASE)/g' $(1)/usr/share/ucode/luci/template/capmon/*.ut
endef

define Package/luci-app-capmon/postinst
#!/bin/sh
[ -n "$${IPKG_INSTROOT}" ] || [ -n "$${APK_INSTROOT}" ] && exit 0

chmod 0755 /etc/init.d/capmon 2>/dev/null
chmod 0755 /usr/sbin/capmon 2>/dev/null
chmod 0755 /usr/libexec/rpcd/capmon 2>/dev/null
chmod 0755 /etc/hotplug.d/iface/90-capmon 2>/dev/null
chmod 0755 /etc/hotplug.d/dhcp/90-capmon 2>/dev/null
chmod 0600 /etc/config/capmon 2>/dev/null
mkdir -p /etc/capmon && chmod 0700 /etc/capmon

sysctl -e -p /etc/sysctl.d/90-capmon.conf >/dev/null 2>&1

rm -f /tmp/luci-indexcache /tmp/luci-indexcache.*
rm -rf /tmp/luci-modulecache/

[ -x /etc/init.d/rpcd ] && /etc/init.d/rpcd restart 2>/dev/null

[ "$$(uci -q get capmon.main.enabled)" = "0" ] || /etc/init.d/capmon enable
/etc/init.d/capmon restart

exit 0
endef

define Package/luci-app-capmon/prerm
#!/bin/sh
[ -n "$${IPKG_INSTROOT}" ] || [ -n "$${APK_INSTROOT}" ] && exit 0

[ -x /etc/init.d/capmon ] && /etc/init.d/capmon stop 2>/dev/null
nft delete table inet capmon 2>/dev/null

exit 0
endef

define Package/luci-app-capmon/postrm
#!/bin/sh
[ -n "$${IPKG_INSTROOT}" ] || [ -n "$${APK_INSTROOT}" ] && exit 0

if grep -qF "/usr/sbin/capmon cron" /etc/crontabs/root 2>/dev/null; then
	mkdir -p /var/run
	rm -f /var/run/capmon.cron
	grep -vF "/usr/sbin/capmon cron" /etc/crontabs/root > /var/run/capmon.cron
	cat /var/run/capmon.cron > /etc/crontabs/root
	rm -f /var/run/capmon.cron
fi

nft delete table inet capmon 2>/dev/null
rm -rf /var/run/capmon
rm -f /tmp/capmon-import.tar.gz

rm -f /tmp/luci-indexcache /tmp/luci-indexcache.*
rm -rf /tmp/luci-modulecache/

[ -x /etc/init.d/rpcd ] && /etc/init.d/rpcd restart 2>/dev/null

exit 0
endef

$(eval $(call BuildPackage,luci-app-capmon))
