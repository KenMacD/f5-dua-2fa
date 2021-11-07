# Duo HTOP for F5 VPN 2FA

This script performs the 2fa required for an F5 vpn using Duo Security. It can be used with the [OpenConnect](https://www.infradead.org/openconnect/) project during login. For example when starting attempting to connect you might see:

```
$ sudo ./openconnect --protocol=f5 vpn.example.org -v --useragent=...
...
Ignoring unknown form input type 'submit'
Initializing two-factor authentication... DUO-TXID(api-1234abcd.duosecurity.com|AaAaAaAaAaAaAaAaAaAa)

_F5_challenge:
```

Using that `DUO-TXID` value you could run:

```
$ main.py http://vpn.example.org/my.policy \
  $(ykman oath accounts code -s VPN) \
  DUO-TXID(api-1234abcd.duosecurity.com|AaAaAaAaAaAaAaAaAaAa)
Touch your YubiKey...
Cookie: BbBbBbBbBbBbBbBbBbBbBbBbBbBbBbBb
```

Take that cookie and paste it to OpenConnect to complete the connection.

NB: I required a proper useragent for F5 to avoid being redirected to a site with information about the VPN.
