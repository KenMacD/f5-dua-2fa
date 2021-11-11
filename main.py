#!/usr/bin/env python3

import re
import sys
from urllib.parse import parse_qs, urlparse
from subprocess import check_output

import pexpect
import requests

##########
# Config #
##########

# Need a build with f5 support
OPENCONNECT_PATH = "/home/user/src/openconnect/openconnect"

# Some VPNs require a real user-agent
USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64; rv:93.0) Gecko/20100101 Firefox/93.0"

VPN_URL = "https://vpn.example.org/"
VPN_USER = "USER"
VPN_PASS_CMD = "pass show vpn.example.org | head -n 1 | tr -d '\n'"

DUO_AUTH = "https://{api_host}/frame/proxy/v1/auth"
DUO_PROMPT = "https://{api_host}/frame/prompt"
DUO_STATUS = "https://{api_host}/frame/status"
DUO_PASSCODE_CMD = "ykman oath accounts code -s Duo | tr -d '\n'"


def get_passwd():
    return check_output(VPN_PASS_CMD, shell=True)


def get_passcode():
    return check_output(DUO_PASSCODE_CMD, shell=True)


def connect():
    p = pexpect.spawn(
        OPENCONNECT_PATH,
        [
            "--protocol=f5",
            "--useragent={}".format(USER_AGENT),
            "--user={}".format(VPN_USER),
            "--server={}".format(VPN_URL),
            "--script-tun",
            "--script=ocproxy -D 11080",
        ],
    )

    # p.logfile = sys.stdout.buffer
    p.expect("password:")
    p.sendline(get_passwd())
    p.expect("DUO-TXID\(([^|]+)\|([^)]+)\)")
    (api, txid) = [x.decode("utf-8") for x in p.match.groups()]
    p.expect("_F5_challenge:")

    cookie = duo(f"{VPN_URL}my.policy", get_passcode(), api, txid)
    p.sendline(cookie)
    p.interact()


def duo(parent_url, passcode, api_host, txid):

    session: requests.Session = requests.Session()
    session.headers["User-Agent"] = USER_AGENT
    session.hooks["response"] = [
        lambda response, *args, **kwargs: response.raise_for_status()
    ]

    # Get the DUO_AUTH url in order for the _xsrf cookie to be set
    session.get(
        url=DUO_AUTH.format(api_host=api_host),
        params={
            "proxy_txid": txid,
            "parent": parent_url,
            "supports_duo_open_window": "true",
        },
    )
    rep = session.post(
        url=DUO_AUTH.format(api_host=api_host),
        data={
            "proxy_txid": txid,
            "parent": parent_url,
            "java_version": "",
            "flash_version": "",
            "screen_resolution_width": 1920,
            "screen_resolution_height": 1080,
            "color_depth": 32,
            "is_cef_browser": "false",
            "is_ipad_os": "false",
            "is_ie_compatibility_mode": "",
            "is_user_verifying_platform_authenticator_available": "false",
            "user_verifying_platform_authenticator_available_error": "",
            "acting_ie_version": "",
            "react_support": "true",
            "react_support_error_message": "",
        },
    )
    # Request leads to a redirect with the require 'sid' as a queryparam
    sid = parse_qs(urlparse(rep.url).query)["sid"][0]

    # TODO: make device and factor configurable.
    # TODO: support push
    # 'device' uses 'phoneX', not the name you set
    res = session.post(
        url=DUO_PROMPT.format(api_host=api_host),
        data={
            "sid": sid,
            "device": "phone2",
            "factor": "Passcode",  # or Push
            "passcode": passcode,
            "out_of_date": "",
            "days_out_of_date": "",
            "days_to_block": "None",
        },
    )

    res = res.json()
    assert res["stat"] == "OK"
    txid = res["response"]["txid"]

    res = session.post(
        url=DUO_STATUS.format(api_host=api_host), data={"sid": sid, "txid": txid}
    )
    res = res.json()
    assert res["stat"] == "OK"
    assert res["response"]["result"] == "SUCCESS"
    result_url = res["response"]["result_url"]

    # TODO: loop on prompt/status if not yet done (ie for push)

    res = session.post(
        url="https://{api_host}{result_url}".format(
            api_host=api_host, result_url=result_url
        ),
        data={
            "sid": sid,
            "txid": txid,
        },
    )
    res = res.json()
    assert res["stat"] == "OK"
    cookie = res["response"]["cookie"]

    print("Cookie: {}".format(cookie))
    return cookie

    # res = session.post(
    #     url=parent_url,
    #     data={
    #         "_F5_challenge": cookie,
    #         "vhost": "standard",
    #     },
    # )
    # cookies = res.cookies

    # Set-Cookie:	F5_ST=1z1z1z1555555555z86400;path=/;secure
    # Set-Cookie:	LastMRH_Session=abcd1234;path=/;secure
    # Set-Cookie:	MRHSession=abcd1234567890abcdef1234567890ab;path=/;secure


if __name__ == "__main__":
    connect()
