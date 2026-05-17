import unittest

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.config import Settings
from app.errors import INVALID_PARAMS, METHOD_NOT_FOUND
from app.errors import RpcException
from app.routes.jsonrpc import build_jsonrpc_router


class FakeDispatcher:
    def dispatch(self, method, params):
        if method == "rpc.discover":
            return {"service": "sigma-jsonrpc"}
        if method == "sigma.convert":
            target = params.get("target")
            if not target:
                raise RpcException(INVALID_PARAMS, "missing required field 'target'")
            return {"target": target, "query": "index=*"}
        raise RpcException(METHOD_NOT_FOUND, f"Method not found: {method}")


class JsonRpcApiTests(unittest.TestCase):
    def setUp(self) -> None:
        settings = Settings(SIGMA_AUTH_REQUIRED=False)
        app = FastAPI()
        app.include_router(build_jsonrpc_router(settings, FakeDispatcher()))
        self.client = TestClient(app)

    def test_success_response(self) -> None:
        response = self.client.post(
            "/jsonrpc",
            json={"jsonrpc": "2.0", "id": "1", "method": "rpc.discover", "params": {}},
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["jsonrpc"], "2.0")
        self.assertEqual(payload["id"], "1")
        self.assertEqual(payload["result"]["service"], "sigma-jsonrpc")

    def test_notification_returns_204(self) -> None:
        response = self.client.post(
            "/jsonrpc",
            json={"jsonrpc": "2.0", "method": "rpc.discover", "params": {}},
        )
        self.assertEqual(response.status_code, 204)
        self.assertEqual(response.text, "")

    def test_invalid_json_returns_parse_error(self) -> None:
        response = self.client.post(
            "/jsonrpc", data='{"jsonrpc":', headers={"Content-Type": "application/json"}
        )
        self.assertEqual(response.status_code, 400)
        payload = response.json()
        self.assertEqual(payload["error"]["code"], -32700)

    def test_invalid_request_returns_error(self) -> None:
        response = self.client.post(
            "/jsonrpc", json={"jsonrpc": "1.0", "id": 1, "method": "rpc.discover"}
        )
        self.assertEqual(response.status_code, 400)
        payload = response.json()
        self.assertEqual(payload["error"]["code"], -32600)

    def test_method_error_is_wrapped_in_jsonrpc_error(self) -> None:
        response = self.client.post(
            "/jsonrpc",
            json={"jsonrpc": "2.0", "id": 99, "method": "missing.method", "params": {}},
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["id"], 99)
        self.assertEqual(payload["error"]["code"], METHOD_NOT_FOUND)


if __name__ == "__main__":
    unittest.main()
