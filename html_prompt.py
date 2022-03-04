# -*- coding=UTF-8 -*-
# pyright: strict

from __future__ import annotations

import threading
import http.server
import http
from typing import Any, Dict, Text
import webbrowser
import json
import urllib.parse

import logging
_LOGGER = logging.getLogger(__name__)


def prompt(html: Text) -> Dict[Any, Any]:
    ret: Dict[Any, Any] = {}

    class _Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            # self.send_response(http.HTTPStatus.OK)
            self._render_html(http.HTTPStatus.OK, html)

        def do_POST(self):
            data = self._read_body()
            ct = self.headers["Content-Type"]
            try:
                if ct in ("application/json", "text/json"):
                    o = json.loads(data)
                    ret.update(o)
                elif ct in ("application/x-www-form-urlencoded"):
                    o = urllib.parse.parse_qs(data, strict_parsing=True)
                    ret.update(o)
                else:
                    raise NotImplementedError(
                        "request Content-Type not supported: %s" % ct
                    )
            except Exception as ex:
                self._render_html(http.HTTPStatus.BAD_REQUEST, str(ex))
                return
            self._render_html(
                http.HTTPStatus.OK,
                """
<h1>done</h1>
<p>this page can be closed.</p>
""",
            )
            self._request_server_shutdown()

        def _request_server_shutdown(self):
            threading.Thread(
                target=self.server.shutdown,
            ).start()

        def _render_html(self, code: int, html: Text):
            enc = "utf-8"
            encoded = html.encode(enc, "surrogateescape")
            self.send_response(code)
            self.send_header("Content-type", "text/html; charset=%s" % enc)
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

        def _read_body(self):
            data = self.rfile.read(int(self.headers["Content-Length"]))
            return data

    with http.server.HTTPServer(("127.0.0.1", 0), _Handler) as httpd:
        host, port = httpd.server_address
        url = f"http://{host}:{port}"
        _LOGGER.info(f"temporary http server at: {url}")
        webbrowser.open(url)
        httpd.serve_forever()
    return ret


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print(
        prompt(
            f"""\
<h1>test</h1>
<form method="POST">
<input name="value" />
<button type="submit" >submit</button>
</form>
"""
        )
    )
