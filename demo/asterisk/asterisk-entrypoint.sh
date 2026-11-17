#!/bin/sh
set -eu

: "${ASTERISK_SIP_PASSWORD:?Set ASTERISK_SIP_PASSWORD in .env.demo}"
: "${ASTERISK_ARI_PASSWORD:?Set ASTERISK_ARI_PASSWORD in .env.demo}"
: "${ASTERISK_ARI_USERNAME:?Set ASTERISK_ARI_USERNAME in .env.demo}"
: "${ASTERISK_MEDIA_IP:?Set ASTERISK_MEDIA_IP to this laptop's LAN IPv4 address}"

# Restrict substitutions to simple token values so config syntax cannot be injected.
for value in "$ASTERISK_SIP_PASSWORD" "$ASTERISK_ARI_PASSWORD" "$ASTERISK_ARI_USERNAME" "$ASTERISK_MEDIA_IP"; do
  case "$value" in
    ''|*[!A-Za-z0-9_.:-]*) echo "Asterisk demo credentials/address must use only letters, digits, dot, underscore, colon, and hyphen." >&2; exit 2 ;;
  esac
done

sed "s/__ASTERISK_SIP_PASSWORD__/$ASTERISK_SIP_PASSWORD/g; s/__ASTERISK_MEDIA_IP__/$ASTERISK_MEDIA_IP/g" \
  /opt/momo-asterisk/pjsip.conf.template > /etc/asterisk/pjsip.conf
sed "s/__ASTERISK_ARI_USERNAME__/$ASTERISK_ARI_USERNAME/g; s/__ASTERISK_ARI_PASSWORD__/$ASTERISK_ARI_PASSWORD/g" \
  /opt/momo-asterisk/ari.conf.template > /etc/asterisk/ari.conf
cp /opt/momo-asterisk/http.conf /etc/asterisk/http.conf
cp /opt/momo-asterisk/extensions.conf /etc/asterisk/extensions.conf
cp /opt/momo-asterisk/rtp.conf /etc/asterisk/rtp.conf

exec "$@"
