# Copyright (c) 2021, VRAI Labs and/or its affiliates. All rights reserved.
#
# This software is licensed under the Apache License, Version 2.0 (the
# "License") as published by the Apache Software Foundation.
#
# You may not use this file except in compliance with the License. You may
# obtain a copy of the License at http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

from typing import Any, Dict, List
from unittest.mock import MagicMock

from fastapi import FastAPI
from fastapi.requests import Request
from fastapi.testclient import TestClient
from pytest import fixture, mark

from supertokens_python import InputAppInfo, SupertokensConfig, init
from supertokens_python.framework.fastapi.fastapi_middleware import get_middleware
from supertokens_python.process_state import AllowedProcessStates, ProcessState
from supertokens_python.recipe import session
from supertokens_python.recipe.session import InputOverrideConfig, SessionRecipe
from supertokens_python.recipe.session.asyncio import (
    create_new_session as async_create_new_session,
)
from supertokens_python.recipe.session.asyncio import (
    get_all_session_handles_for_user,
    get_session_information,
    regenerate_access_token,
)
from supertokens_python.recipe.session.asyncio import (
    revoke_session as asyncio_revoke_session,
)
from supertokens_python.recipe.session.asyncio import (
    update_access_token_payload,
    update_session_data,
)
from supertokens_python.recipe.session.interfaces import RecipeInterface
from supertokens_python.recipe.session.recipe_implementation import RecipeImplementation
from supertokens_python.recipe.session.session_functions import (
    create_new_session,
    get_session,
    refresh_session,
    revoke_session,
)
from tests.utils import clean_st, reset, setup_st, start_st

pytestmark = mark.asyncio


def setup_function(_):
    reset()
    clean_st()
    setup_st()


def teardown_function(_):
    reset()
    clean_st()


async def test_that_once_the_info_is_loaded_it_doesnt_query_again():
    init(
        supertokens_config=SupertokensConfig("http://localhost:3567"),
        app_info=InputAppInfo(
            app_name="SuperTokens Demo",
            api_domain="https://api.supertokens.io",
            website_domain="supertokens.io",
        ),
        framework="fastapi",
        recipe_list=[session.init(anti_csrf="VIA_TOKEN")],
    )
    start_st()

    s = SessionRecipe.get_instance()
    if not isinstance(s.recipe_implementation, RecipeImplementation):
        raise Exception("Should never come here")

    response = await create_new_session(s.recipe_implementation, "", {}, {})

    assert response["session"] is not None
    assert response["accessToken"] is not None
    assert response["refreshToken"] is not None
    assert response["idRefreshToken"] is not None
    assert response["antiCsrfToken"] is not None
    assert len(response.keys()) == 5

    await get_session(
        s.recipe_implementation,
        response["accessToken"]["token"],
        response["antiCsrfToken"],
        True,
        response["idRefreshToken"]["token"],
    )
    assert (
        AllowedProcessStates.CALLING_SERVICE_IN_VERIFY
        not in ProcessState.get_instance().history
    )

    response2 = await refresh_session(
        s.recipe_implementation,
        response["refreshToken"]["token"],
        response["antiCsrfToken"],
        True,
    )

    assert response2["session"] is not None
    assert response2["accessToken"] is not None
    assert response2["refreshToken"] is not None
    assert response2["idRefreshToken"] is not None
    assert response2["antiCsrfToken"] is not None
    assert len(response.keys()) == 5

    response3 = await get_session(
        s.recipe_implementation,
        response2["accessToken"]["token"],
        response2["antiCsrfToken"],
        True,
        response["idRefreshToken"]["token"],
    )

    assert (
        AllowedProcessStates.CALLING_SERVICE_IN_VERIFY
        in ProcessState.get_instance().history
    )

    assert response3["session"] is not None
    assert response3["accessToken"] is not None
    assert len(response3.keys()) == 2

    ProcessState.get_instance().reset()

    response4 = await get_session(
        s.recipe_implementation,
        response3["accessToken"]["token"],
        response2["antiCsrfToken"],
        True,
        response["idRefreshToken"]["token"],
    )
    assert (
        AllowedProcessStates.CALLING_SERVICE_IN_VERIFY
        not in ProcessState.get_instance().history
    )

    assert response4["session"] is not None
    assert "accessToken" not in response4
    assert len(response4.keys()) == 1

    response5 = await revoke_session(
        s.recipe_implementation, response4["session"]["handle"]
    )

    assert response5 is True


async def test_creating_many_sessions_for_one_user_and_looping():
    init(
        supertokens_config=SupertokensConfig("http://localhost:3567"),
        app_info=InputAppInfo(
            app_name="SuperTokens Demo",
            api_domain="https://api.supertokens.io",
            website_domain="supertokens.io",
        ),
        framework="fastapi",
        recipe_list=[session.init()],
    )
    start_st()

    s = SessionRecipe.get_instance()
    if not isinstance(s.recipe_implementation, RecipeImplementation):
        raise Exception("Should never come here")

    access_tokens: List[str] = []
    for _ in range(7):
        new_session = await create_new_session(
            s.recipe_implementation, "someUser", {"someKey": "someValue"}, {}
        )
        access_tokens.append(new_session["accessToken"]["token"])

    session_handles = await get_all_session_handles_for_user("someUser")

    assert len(session_handles) == 7

    for i, handle in enumerate(session_handles):
        info = await get_session_information(handle)
        assert info is not None
        assert info.user_id == "someUser"
        assert info.access_token_payload["someKey"] == "someValue"

        is_updated = await update_access_token_payload(
            handle, {"someKey2": "someValue"}
        )
        assert is_updated

        is_updated = await update_session_data(handle, {"foo": "bar"})
        assert is_updated

    # Confirm that update funcs worked:
    for handle in session_handles:
        info = await get_session_information(handle)
        assert info is not None
        assert info.user_id == "someUser"
        assert info.access_token_payload == {"someKey2": "someValue"}
        assert info.session_data == {"foo": "bar"}

    # Regenerate access token with new access_token_payload
    for i, token in enumerate(access_tokens):
        result = await regenerate_access_token(token, {"bar": "baz"})
        assert result is not None
        assert (
            result.session.handle == session_handles[i]
        )  # Session handle should remain the same

        # Confirm that update worked:
        info = await get_session_information(result.session.handle)
        assert info is not None
        assert info.access_token_payload == {"bar": "baz"}

    # Try updating invalid handles:
    is_updated = await update_access_token_payload("invalidHandle", {"foo": "bar"})
    assert is_updated is False
    is_updated = await update_session_data("invalidHandle", {"foo": "bar"})
    assert is_updated is False


@fixture(scope="function")
async def driver_config_client():
    app = FastAPI()
    app.add_middleware(get_middleware())

    @app.get("/")
    async def home(_request: Request):  # type: ignore
        return {"hello": "world"}

    @app.post("/create")
    async def create_api(request: Request):  # type: ignore
        await async_create_new_session(request, "test-user", {}, {})
        return ""

    return TestClient(app)


async def test_signout_api_works_even_if_session_is_deleted_after_creation(
    driver_config_client: TestClient,
):
    init(
        supertokens_config=SupertokensConfig("http://localhost:3567"),
        app_info=InputAppInfo(
            app_name="SuperTokens Demo",
            api_domain="https://api.supertokens.io",
            website_domain="supertokens.io",
        ),
        framework="fastapi",
        recipe_list=[session.init(anti_csrf="VIA_TOKEN")],
    )
    start_st()

    s = SessionRecipe.get_instance()
    if not isinstance(s.recipe_implementation, RecipeImplementation):
        raise Exception("Should never come here")
    user_id = "user_id"

    response = await create_new_session(s.recipe_implementation, user_id, {}, {})

    session_handle = response["session"]["handle"]

    revoked = await asyncio_revoke_session(session_handle)
    assert revoked

    signout_response = driver_config_client.post(
        url="/auth/signout",
        cookies={
            "sAccessToken": response["accessToken"]["token"],
            "sIdRefreshToken": response["idRefreshToken"]["token"],
        },
        headers={"anti-csrf": response.get("antiCsrfToken", "")},
    )

    assert signout_response.json() == {"status": "OK"}

    assert (
        signout_response.headers["set-cookie"]
        == """sAccessToken=""; expires=Thu, 01 Jan 1970 00:00:00 GMT; HttpOnly; Path=/; SameSite=lax; Secure, sIdRefreshToken=""; expires=Thu, 01 Jan 1970 00:00:00 GMT; HttpOnly; Path=/; SameSite=lax; Secure, sRefreshToken=""; expires=Thu, 01 Jan 1970 00:00:00 GMT; HttpOnly; Path=/auth/session/refresh; SameSite=lax; Secure"""
    )


async def test_should_use_override_functions_in_session_container_methods():
    def override_session_functions(oi: RecipeInterface) -> RecipeInterface:
        oi_get_session_information = oi.get_session_information

        async def get_session_information(
            session_handle: str, user_context: Dict[str, Any]
        ):
            info = await oi_get_session_information(session_handle, user_context)
            assert info is not None
            info.session_data["foo"] = "bar"
            return info

        oi.get_session_information = get_session_information

        return oi

    init(
        supertokens_config=SupertokensConfig("http://localhost:3567"),
        app_info=InputAppInfo(
            app_name="SuperTokens Demo",
            api_domain="https://api.supertokens.io",
            website_domain="supertokens.io",
        ),
        framework="fastapi",
        recipe_list=[
            session.init(
                anti_csrf="VIA_TOKEN",
                override=InputOverrideConfig(
                    functions=override_session_functions,
                ),
            )
        ],
    )
    start_st()

    s = SessionRecipe.get_instance()
    if not isinstance(s.recipe_implementation, RecipeImplementation):
        raise Exception("Should never come here")

    mock_response = MagicMock()

    my_session = await async_create_new_session(mock_response, "test_id")
    data = await my_session.get_session_data()

    assert data == {"foo": "bar"}


from supertokens_python.recipe.session.exceptions import raise_unauthorised_exception
from supertokens_python.recipe.session.interfaces import APIInterface, APIOptions
from tests.utils import extract_all_cookies, get_st_init_args


async def test_revoking_session_during_refresh_with_revoke_session_with_200(
    driver_config_client: TestClient,
):
    def session_api_override(oi: APIInterface) -> APIInterface:
        oi_refresh_post = oi.refresh_post

        async def refresh_post(api_options: APIOptions, user_context: Dict[str, Any]):
            s = await oi_refresh_post(api_options, user_context)
            await s.revoke_session()
            return s

        oi.refresh_post = refresh_post
        return oi

    init_args = get_st_init_args(
        [
            session.init(
                anti_csrf="VIA_TOKEN",
                override=session.InputOverrideConfig(apis=session_api_override),
            )
        ]
    )
    init(**init_args)
    start_st()

    response = driver_config_client.post("/create")
    cookies = extract_all_cookies(response)

    assert "sAccessToken" in cookies
    assert "sIdRefreshToken" in cookies
    assert "sRefreshToken" in cookies

    assert "anti-csrf" in response.headers
    assert "id-refresh-token" in response.headers
    assert "front-token" in response.headers

    response = driver_config_client.post(
        "/auth/session/refresh",
        cookies={
            "sRefreshToken": cookies["sRefreshToken"]["value"],
            "sIdRefreshToken": cookies["sIdRefreshToken"]["value"],
        },
        headers={"anti-csrf": response.headers["anti-csrf"]},
    )

    assert response.status_code == 200
    cookies = extract_all_cookies(response)

    assert cookies["sAccessToken"]["value"] == ""
    assert cookies["sRefreshToken"]["value"] == ""
    assert cookies["sIdRefreshToken"]["value"] == ""

    assert (
        "anti-csrf" not in response.headers
    )  # remove_cookies = True because of revoke. So new anti-csrf is generated but not set
    assert response.headers["id-refresh-token"] == "remove"

    assert cookies["sAccessToken"]["expires"] == "Thu, 01 Jan 1970 00:00:00 GMT"
    assert cookies["sIdRefreshToken"]["expires"] == "Thu, 01 Jan 1970 00:00:00 GMT"
    assert cookies["sRefreshToken"]["expires"] == "Thu, 01 Jan 1970 00:00:00 GMT"

    assert cookies["sAccessToken"]["domain"] == ""
    assert cookies["sIdRefreshToken"]["domain"] == ""
    assert cookies["sRefreshToken"]["domain"] == ""
    assert (
        "front-token" not in response.headers
    )  # revoke_cookies = True because of revoke. So not set


async def test_revoking_session_during_refresh_with_revoke_session_sending_401(
    driver_config_client: TestClient,
):
    def session_api_override(oi: APIInterface) -> APIInterface:
        oi_refresh_post = oi.refresh_post

        async def refresh_post(api_options: APIOptions, user_context: Dict[str, Any]):
            s = await oi_refresh_post(api_options, user_context)
            await s.revoke_session()
            api_options.response.set_status_code(401)  # type: ignore
            api_options.response.set_json_content({})  # type: ignore
            return s

        oi.refresh_post = refresh_post
        return oi

    init_args = get_st_init_args(
        [
            session.init(
                anti_csrf="VIA_TOKEN",
                override=session.InputOverrideConfig(apis=session_api_override),
            )
        ]
    )
    init(**init_args)
    start_st()

    response = driver_config_client.post("/create")
    assert response.status_code == 200

    cookies = extract_all_cookies(response)

    assert "sAccessToken" in cookies
    assert "sIdRefreshToken" in cookies
    assert "sRefreshToken" in cookies

    assert "anti-csrf" in response.headers
    assert "id-refresh-token" in response.headers
    assert "front-token" in response.headers

    response = driver_config_client.post(
        "/auth/session/refresh",
        cookies={
            "sRefreshToken": cookies["sRefreshToken"]["value"],
            "sIdRefreshToken": cookies["sIdRefreshToken"]["value"],
        },
        headers={"anti-csrf": response.headers["anti-csrf"]},
    )

    assert response.status_code == 401
    cookies = extract_all_cookies(response)

    assert cookies["sAccessToken"]["value"] == ""
    assert cookies["sRefreshToken"]["value"] == ""
    assert cookies["sIdRefreshToken"]["value"] == ""

    assert "anti-csrf" not in response.headers
    assert response.headers["id-refresh-token"] == "remove"

    assert cookies["sAccessToken"]["expires"] == "Thu, 01 Jan 1970 00:00:00 GMT"
    assert cookies["sIdRefreshToken"]["expires"] == "Thu, 01 Jan 1970 00:00:00 GMT"
    assert cookies["sRefreshToken"]["expires"] == "Thu, 01 Jan 1970 00:00:00 GMT"

    assert cookies["sAccessToken"]["domain"] == ""
    assert cookies["sIdRefreshToken"]["domain"] == ""
    assert cookies["sRefreshToken"]["domain"] == ""
    assert "front-token" not in response.headers


async def test_revoking_session_during_refresh_and_throw_unauthorized(
    driver_config_client: TestClient,
):
    def session_api_override(oi: APIInterface) -> APIInterface:
        oi_refresh_post = oi.refresh_post

        async def refresh_post(api_options: APIOptions, user_context: Dict[str, Any]):
            await oi_refresh_post(api_options, user_context)
            return raise_unauthorised_exception("unauthorized")

        oi.refresh_post = refresh_post
        return oi

    init_args = get_st_init_args(
        [
            session.init(
                anti_csrf="VIA_TOKEN",
                override=session.InputOverrideConfig(apis=session_api_override),
            )
        ]
    )
    init(**init_args)
    start_st()

    response = driver_config_client.post("/create")
    assert response.status_code == 200

    cookies = extract_all_cookies(response)

    assert "sAccessToken" in cookies
    assert "sIdRefreshToken" in cookies
    assert "sRefreshToken" in cookies

    assert "anti-csrf" in response.headers
    assert "id-refresh-token" in response.headers
    assert "front-token" in response.headers

    response = driver_config_client.post(
        "/auth/session/refresh",
        cookies={
            "sRefreshToken": cookies["sRefreshToken"]["value"],
            "sIdRefreshToken": cookies["sIdRefreshToken"]["value"],
        },
        headers={"anti-csrf": response.headers["anti-csrf"]},
    )

    assert response.status_code == 401
    cookies = extract_all_cookies(response)

    assert cookies["sAccessToken"]["value"] == ""
    assert cookies["sRefreshToken"]["value"] == ""
    assert cookies["sIdRefreshToken"]["value"] == ""

    assert "anti-csrf" not in response.headers
    assert response.headers["id-refresh-token"] == "remove"

    assert cookies["sAccessToken"]["expires"] == "Thu, 01 Jan 1970 00:00:00 GMT"
    assert cookies["sIdRefreshToken"]["expires"] == "Thu, 01 Jan 1970 00:00:00 GMT"
    assert cookies["sRefreshToken"]["expires"] == "Thu, 01 Jan 1970 00:00:00 GMT"

    assert cookies["sAccessToken"]["domain"] == ""
    assert cookies["sIdRefreshToken"]["domain"] == ""
    assert cookies["sRefreshToken"]["domain"] == ""
    assert "front-token" not in response.headers


async def test_revoking_session_during_refresh_fails_if_just_sending_401(
    driver_config_client: TestClient,
):
    def session_api_override(oi: APIInterface) -> APIInterface:
        oi_refresh_post = oi.refresh_post

        async def refresh_post(api_options: APIOptions, user_context: Dict[str, Any]):
            s = await oi_refresh_post(api_options, user_context)
            api_options.response.set_status_code(401)  # type: ignore
            api_options.response.set_json_content({})  # type: ignore
            return s

        oi.refresh_post = refresh_post
        return oi

    init_args = get_st_init_args(
        [
            session.init(
                anti_csrf="VIA_TOKEN",
                override=session.InputOverrideConfig(apis=session_api_override),
            )
        ]
    )
    init(**init_args)
    start_st()

    response = driver_config_client.post("/create")
    assert response.status_code == 200

    cookies = extract_all_cookies(response)

    assert "sAccessToken" in cookies
    assert "sIdRefreshToken" in cookies
    assert "sRefreshToken" in cookies

    assert "anti-csrf" in response.headers
    assert "id-refresh-token" in response.headers
    assert "front-token" in response.headers

    response = driver_config_client.post(
        "/auth/session/refresh",
        cookies={
            "sRefreshToken": cookies["sRefreshToken"]["value"],
            "sIdRefreshToken": cookies["sIdRefreshToken"]["value"],
        },
        headers={"anti-csrf": response.headers["anti-csrf"]},
    )

    assert response.status_code == 401
    cookies = extract_all_cookies(response)

    assert cookies["sAccessToken"]["value"] != ""
    assert cookies["sRefreshToken"]["value"] != ""
    assert cookies["sIdRefreshToken"]["value"] != ""

    assert response.headers["anti-csrf"] != ""
    assert response.headers["id-refresh-token"] != "remove"

    assert cookies["sAccessToken"]["expires"] != "Thu, 01 Jan 1970 00:00:00 GMT"
    assert cookies["sIdRefreshToken"]["expires"] != "Thu, 01 Jan 1970 00:00:00 GMT"
    assert cookies["sRefreshToken"]["expires"] != "Thu, 01 Jan 1970 00:00:00 GMT"

    assert response.headers["front-token"] != ""
