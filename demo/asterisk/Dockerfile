FROM andrius/asterisk:22.10.1_debian-trixie
USER root

COPY asterisk-entrypoint.sh /usr/local/bin/momo-asterisk-entrypoint
COPY pjsip.conf /opt/momo-asterisk/pjsip.conf.template
COPY ari.conf /opt/momo-asterisk/ari.conf.template
COPY http.conf /opt/momo-asterisk/http.conf
COPY extensions.conf /opt/momo-asterisk/extensions.conf
COPY rtp.conf /opt/momo-asterisk/rtp.conf
RUN chmod 0755 /usr/local/bin/momo-asterisk-entrypoint

ENTRYPOINT ["/usr/local/bin/momo-asterisk-entrypoint"]
CMD ["/usr/sbin/asterisk", "-f", "-U", "asterisk", "-G", "asterisk", "-p"]
