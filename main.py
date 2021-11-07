#!/usr/bin/env python3

import re
import sys
from urllib.parse import parse_qs, urlparse

import requests

USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64; rv:93.0) Gecko/20100101 Firefox/93.0"

DUO_AUTH = "https://{api_domain}/frame/proxy/v1/auth"
DUO_PROMPT = "https://{api_domain}/frame/prompt"
DUO_STATUS = "https://{api_domain}/frame/status"


def main(auth_url, passcode, duo_txid):

    session: requests.Session = requests.Session()
    session.headers["User-Agent"] = USER_AGENT
    session.hooks["response"] = [
        lambda response, *args, **kwargs: response.raise_for_status()
    ]

    (api, txid) = re.search("DUO-TXID\(([^|]+)\|([^)]+)\)", duo_txid).groups()
    # print(f"API: {api} txid: {txid}")

    # Get the DUO_AUTH url in order for the _xsrf cookie to be set
    session.get(
        url=DUO_AUTH.format(api_domain=api),
        params={
            "proxy_txid": txid,
            "parent": auth_url,
            "supports_duo_open_window": "true",
        },
    )
    rep = session.post(
        url=DUO_AUTH.format(api_domain=api),
        data={
            "proxy_txid": txid,
            "parent": auth_url,
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
    # print(sid)

    # TODO: make device and factor configurable.
    # TODO: support push
    # 'device' uses 'phoneX', not the name you set
    res = session.post(
        url=DUO_PROMPT.format(api_domain=api),
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
        url=DUO_STATUS.format(api_domain=api), data={"sid": sid, "txid": txid}
    )
    res = res.json()
    assert res["stat"] == "OK"
    assert res["response"]["result"] == "SUCCESS"
    result_url = res["response"]["result_url"]

    # TODO: loop on prompt/status if not yet done (ie for push)

    res = session.post(
        url="https://{api_domain}{result_url}".format(
            api_domain=api, result_url=result_url
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

    # res = session.post(
    #     url=auth_url,
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

    if len(sys.argv) != 4:
        print(f"Usage: {sys.argv[0]} vpn_url hotp duo-txid")
        print(
            f"Example: {sys.argv[0]} http://vpn.example.org/my.policy 123456 DUO-TXID(api-1234abcd.duosecurity.com|AaAaAaAaAaAaAaAaAaAa)"
        )
    else:
        main(*sys.argv[1:])
