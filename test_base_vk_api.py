from __future__ import annotations

from copy import copy
from json import JSONDecodeError
from typing import Any, Callable, Literal
from urllib.parse import urlencode

import pytest
import requests
import responses
from pydantic import BaseModel

from base_vk_api import BaseVKAPI, VKAPIError


@pytest.fixture
def token():
    return "some token value"


@pytest.fixture
def vk(token: str):
    return BaseVKAPI(token)


def test_get_params(vk: BaseVKAPI):
    assert vk._get_params({"foo": "bar", "foolist": ["foo", "bar", 1]}) == {
        "access_token": vk.token,
        "v": vk.api_version,
        "lang": vk.lang,
        "foo": "bar",
        "foolist": "foo,bar,1",
    }


def _get_mock_response(f: Callable[[], Any]) -> requests.Response:
    class MyResponse:
        def json(self):
            return f()

    return MyResponse()  # type: ignore


def test_parse_response_not_json(vk: BaseVKAPI):
    def json():
        raise JSONDecodeError("", "", 0)

    response = _get_mock_response(json)
    with pytest.raises(VKAPIError, match="Can't decode json response") as exc:
        vk.parse_response(response=response)
    assert exc.value.response == response


def test_parse_response_with_error(vk: BaseVKAPI):
    response = _get_mock_response(
        lambda: {"error": {"error_code": 1, "error_msg": "lala"}}
    )
    with pytest.raises(VKAPIError, match="lala") as exc:
        vk.parse_response(response=response)
    assert exc.value.response == response
    assert exc.value.error_code == 1
    assert exc.value.error_msg == "lala"


@pytest.mark.parametrize("v", ({"notresponse": "foo"}, ["foo", "ba"]))
def test_parse_response_no_response_key(vk: BaseVKAPI, v: Any):
    response = _get_mock_response(lambda: v)
    with pytest.raises(
        VKAPIError, match='No "response" key found in response dict'
    ) as exc:
        vk.parse_response(response=response)
    assert exc.value.response == response


def test_parse_response_no_model(vk: BaseVKAPI):
    assert vk.parse_response(
        response=_get_mock_response(lambda: {"response": ["foo", "bar"]})
    ) == ["foo", "bar"]


def test_parse_response_with_model(vk: BaseVKAPI):
    class MyResponseModel(BaseModel):
        foo: str

    resp = vk.parse_response(
        response=_get_mock_response(lambda: {"response": {"foo": "bar"}}),
        model=MyResponseModel,
    )
    assert resp == MyResponseModel(foo="bar")


@pytest.mark.parametrize("endpoint", ("https://example.com", None))
@responses.activate
def test_make_request(vk: BaseVKAPI, endpoint: str | None):
    if endpoint is not None:
        vk.endpoint = copy(endpoint)
    else:
        endpoint = copy(vk.endpoint)
    responses.add(
        method=responses.GET,
        url=f"{endpoint}/method/wall.get",
        json={"response": {"foo": "bar"}},
        match=[
            responses.matchers.query_string_matcher(  # type: ignore
                urlencode(
                    {
                        "access_token": vk.token,
                        "v": vk.api_version,
                        "lang": vk.lang,
                        "owner_id": 1,
                    }
                )
            )
        ],
    )

    class WallGetResponse(BaseModel):
        foo: Literal["bar"]

    assert vk.make_request(
        method="wall.get", params={"owner_id": 1}, model=WallGetResponse
    ) == WallGetResponse(foo="bar")
