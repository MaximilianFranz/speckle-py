import re
from gql.client import SyncClientSession
from specklepy.logging.exceptions import SpeckleException
from typing import Dict

from specklepy.api import resources
from specklepy.api.resources import (
    branch,
    commit,
    stream,
    object,
    server,
    user,
    subscriptions,
)
from specklepy.api.models import ServerInfo
from gql import Client, gql
from gql.transport.requests import RequestsHTTPTransport
from gql.transport.aiohttp import AIOHTTPTransport
from gql.transport.websockets import WebsocketsTransport


class SpeckleClient:
    DEFAULT_HOST = "speckle.xyz"
    USE_SSL = True

    def __init__(self, host: str = DEFAULT_HOST, use_ssl: bool = USE_SSL) -> None:
        ws_protocol = "ws"
        http_protocol = "http"

        if use_ssl:
            ws_protocol = "wss"
            http_protocol = "https"

        # sanitise host input by removing protocol and trailing slash
        host = re.sub(r"((^\w+:|^)\/\/)|(\/$)", "", host)

        self.url = f"{http_protocol}://{host}"
        self.graphql = self.url + "/graphql"
        self.ws_url = f"{ws_protocol}://{host}/graphql"
        self.me = None

        self.httpclient = Client(
            transport=RequestsHTTPTransport(url=self.graphql, verify=True, retries=3)
        )
        self.wsclient = None

        self._init_resources()

        # Check compatibility with the server
        try:
            serverInfo = self.server.get()
            if not isinstance(serverInfo, ServerInfo):
                raise Exception("Couldn't get ServerInfo")
        except Exception as ex:
            raise SpeckleException(f"{self.url} is not a compatible Speckle Server", ex)

    def authenticate(self, token: str) -> None:
        """Authenticate the client using a personal access token
        The token is saved in the client object and a synchronous GraphQL entrypoint is created

        Arguments:
            token {str} -- an api token
        """
        self.me = {"token": token}
        headers = {
            "Authorization": f"Bearer {self.me['token']}",
            "Content-Type": "application/json",
        }
        httptransport = RequestsHTTPTransport(
            url=self.graphql, headers=headers, verify=True, retries=3
        )
        wstransport = WebsocketsTransport(
            url=self.ws_url,
            init_payload={"Authorization": f"Bearer {self.me['token']}"},
        )
        self.httpclient = Client(transport=httptransport)
        self.wsclient = Client(transport=wstransport)

        self._init_resources()

    def execute_query(self, query: str) -> Dict:
        return self.httpclient.execute(query)

    def _init_resources(self) -> None:
        self.stream = stream.Resource(
            me=self.me, basepath=self.url, client=self.httpclient
        )
        self.commit = commit.Resource(
            me=self.me, basepath=self.url, client=self.httpclient
        )
        self.branch = branch.Resource(
            me=self.me, basepath=self.url, client=self.httpclient
        )
        self.object = object.Resource(
            me=self.me, basepath=self.url, client=self.httpclient
        )
        self.server = server.Resource(
            me=self.me, basepath=self.url, client=self.httpclient
        )
        self.user = user.Resource(me=self.me, basepath=self.url, client=self.httpclient)
        self.subscribe = subscriptions.Resource(
            me=self.me,
            basepath=self.ws_url,
            client=self.wsclient,
        )

    def __getattr__(self, name):
        try:
            attr = getattr(resources, name)
            return attr.Resource(me=self.me, basepath=self.url, client=self.httpclient)
        except:
            raise SpeckleException(
                f"Method {name} is not supported by the SpeckleClient class"
            )
