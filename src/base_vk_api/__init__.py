from __future__ import annotations

from json import JSONDecodeError
from typing import Any, TypeVar, overload

import requests
from pydantic import BaseModel

__all__ = ["BaseVKAPI", "VKAPIError"]


class VKAPIError(Exception):
    response: requests.Response
    error_code: int | None
    error_msg: str | None

    def __init__(
        self,
        *args: Any,
        response: requests.Response,
        error_code: int | None = None,
        error_msg: str | None = None,
    ) -> None:
        self.response = response
        self.error_code = error_code
        self.error_msg = error_msg
        super().__init__(*args)


class BaseVKErrorResponseError(BaseModel):
    error_code: int
    error_msg: str


class BaseVKErrorResponse(BaseModel):
    error: BaseVKErrorResponseError


class BaseVKAPIResponse(BaseModel):
    response: Any


_T = TypeVar("_T", bound=BaseModel)


class BaseVKAPI:
    token: str
    endpoint: str
    api_version: str
    lang: str
    _session: requests.Session

    def __init__(
        self,
        token: str,
        *,
        endpoint: str = "https://api.vk.com",
        api_version: str = "5.131",
        lang: str = "ru",
    ) -> None:
        self.token = token
        self.endpoint = endpoint
        self.api_version = api_version
        self.lang = lang
        self._session = requests.Session()

    def _get_params(self, params: dict[str, Any]) -> dict[str, Any]:
        for key in params:
            # Required format for list params
            if isinstance(params[key], list):
                params[key] = ",".join(str(p) for p in params[key])

        params |= {
            "access_token": self.token,
            "v": self.api_version,
            "lang": self.lang,
        }
        return params

    @overload
    def parse_response(self, *, response: requests.Response, model: type[_T]) -> _T:
        ...

    @overload
    def parse_response(self, *, response: requests.Response, model: None) -> Any:
        ...

    @overload
    def parse_response(self, *, response: requests.Response) -> Any:
        ...

    def parse_response(
        self, *, response: requests.Response, model: type[_T] | None = None
    ) -> _T | Any:
        try:
            resp_json = response.json()
        except JSONDecodeError:
            raise VKAPIError("Can't decode json response", response=response)

        if "error" in resp_json:
            parsed_resp = BaseVKErrorResponse(**resp_json)
            raise VKAPIError(
                parsed_resp.error.error_msg,
                response=response,
                error_code=parsed_resp.error.error_code,
                error_msg=parsed_resp.error.error_msg,
            )

        if "response" not in resp_json:
            raise VKAPIError(
                'No "response" key found in response dict', response=response
            )

        if model is None:
            return resp_json["response"]

        return model(**resp_json["response"])

    @overload
    def make_request(
        self, *, method: str, params: dict[str, Any], model: type[_T]
    ) -> _T:
        ...

    @overload
    def make_request(self, *, method: str, params: dict[str, Any], model: None) -> Any:
        ...

    @overload
    def make_request(self, *, method: str, params: dict[str, Any]) -> Any:
        ...

    def make_request(
        self, *, method: str, params: dict[str, Any], model: type[_T] | None = None
    ) -> _T | Any:
        params_ = self._get_params(params)
        response = self._session.get(f"{self.endpoint}/method/{method}", params=params_)
        return self.parse_response(response=response, model=model)
