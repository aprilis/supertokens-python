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

import json
from typing import Any, Dict, Union

import httpx
import requests
import requests_mock
import respx
from fastapi import FastAPI
from fastapi.requests import Request
from fastapi.testclient import TestClient
from pytest import fixture, mark
from supertokens_python import InputAppInfo, SupertokensConfig, init
from supertokens_python.framework.fastapi import get_middleware
from supertokens_python.ingredients.smsdelivery.service.supertokens import \
    SUPERTOKENS_SMS_SERVICE_URL
from supertokens_python.ingredients.smsdelivery.service.twilio import (
    GetContentResult, ServiceInterface, SMSDeliveryTwilioConfig,
    TwilioServiceConfig)
from supertokens_python.ingredients.smsdelivery.types import (
    SMSDeliveryConfig, SMSDeliveryInterface)
from supertokens_python.recipe import passwordless, session
from supertokens_python.recipe.passwordless.smsdelivery.services.twilio import \
    TwilioService
from supertokens_python.recipe.passwordless.types import \
    TypePasswordlessSmsDeliveryInput
from tests.utils import (clean_st, reset, setup_st, sign_in_up_request_phone,
                         start_st)

respx_mock = respx.MockRouter


def setup_function(_):
    reset()
    clean_st()
    setup_st()


def teardown_function(_):
    reset()
    clean_st()


@fixture(scope='function')
async def driver_config_client():
    app = FastAPI()
    app.add_middleware(get_middleware())

    @app.get('/login')
    async def login(_request: Request):  # type: ignore
        user_id = 'userId'
        # await create_new_session(request, user_id, {}, {})
        return {'userId': user_id}

    return TestClient(app)


@mark.asyncio
async def test_pless_login_default_backward_compatibility(driver_config_client: TestClient):
    "Passwordless login: test default backward compatibility api being called"
    app_name = ""
    phone_number = ""
    code_lifetime = 0
    url_with_link_code = ""
    user_input_code = ""
    api_key = ""

    init(
        supertokens_config=SupertokensConfig('http://localhost:3567'),
        app_info=InputAppInfo(
            app_name="ST",
            api_domain="http://api.supertokens.io",
            website_domain="http://supertokens.io",
            api_base_path="/auth"
        ),
        framework='fastapi',
        recipe_list=[passwordless.init(
            contact_config=passwordless.ContactPhoneOnlyConfig(),
            flow_type="USER_INPUT_CODE_AND_MAGIC_LINK",
        ), session.init()]
    )
    start_st()

    def api_side_effect(request: httpx.Request):
        nonlocal app_name, phone_number, code_lifetime, url_with_link_code, user_input_code, api_key
        body = json.loads(request.content)
        sms_input = body["smsInput"]

        app_name = sms_input["appName"]
        phone_number = sms_input["phoneNumber"]
        code_lifetime = sms_input["codeLifetime"]
        url_with_link_code = sms_input["urlWithLinkCode"]
        user_input_code = sms_input["userInputCode"]

        api_key = body.get("apiKey")

        return httpx.Response(200, json={})

    with respx_mock(assert_all_mocked=False) as mocker:
        mocker.route(host="localhost").pass_through()
        mocked_route = mocker.post(SUPERTOKENS_SMS_SERVICE_URL).mock(side_effect=api_side_effect)
        resp = sign_in_up_request_phone(driver_config_client, "+919909909998", True)

        assert resp.status_code == 200
        assert mocked_route.called

        assert app_name == "ST"
        assert phone_number == "+919909909998"
        assert all([url_with_link_code, user_input_code, code_lifetime])
        assert code_lifetime > 0
        assert api_key is None


@mark.asyncio
async def test_pless_login_default_backward_compatibility_no_suppress_error(driver_config_client: TestClient):
    "Passwordless login: test default backward compatibility api being called, error message sent back to user"
    # TODO: FIXME
    app_name = ""
    phone = ""
    code_lifetime = 0
    url_with_link_code = ""
    user_input_code = ""

    init(
        supertokens_config=SupertokensConfig('http://localhost:3567'),
        app_info=InputAppInfo(
            app_name="ST",
            api_domain="http://api.supertokens.io",
            website_domain="http://supertokens.io",
            api_base_path="/auth"
        ),
        framework='fastapi',
        recipe_list=[passwordless.init(
            contact_config=passwordless.ContactPhoneOnlyConfig(),
            flow_type="USER_INPUT_CODE_AND_MAGIC_LINK",
        ), session.init()]
    )
    start_st()

    def api_side_effect(request: httpx.Request):
        nonlocal app_name, phone, code_lifetime, url_with_link_code, user_input_code
        body = json.loads(request.content)
        sms_input = body["smsInput"]

        app_name = sms_input["appName"]
        phone = sms_input["phoneNumber"]
        code_lifetime = sms_input["codeLifetime"]
        url_with_link_code = sms_input["urlWithLinkCode"]
        user_input_code = sms_input["userInputCode"]

        return httpx.Response(500, json={"err": "CUSTOM_ERR"})

    with respx_mock(assert_all_mocked=False) as mocker:
        mocker.route(host="localhost").pass_through()
        mocked_route = mocker.post(SUPERTOKENS_SMS_SERVICE_URL).mock(side_effect=api_side_effect)
        resp = sign_in_up_request_phone(driver_config_client, "+919909909998", True)

        assert resp.status_code == 200
        assert resp.json() == {"status": "OK"}
        assert mocked_route.called

        assert app_name == "ST"
        assert phone == "+919909909998"
        assert all([url_with_link_code, user_input_code, code_lifetime])
        assert code_lifetime > 0


@mark.asyncio
async def test_pless_login_backward_compatibility(driver_config_client: TestClient):
    "Passwordless login: test backward compatibility"
    phone = ""
    code_lifetime = 0
    url_with_link_code = ""
    user_input_code = ""

    async def create_and_send_custom_text_message(input_: TypePasswordlessSmsDeliveryInput, _: Dict[str, Any]):
        nonlocal phone, code_lifetime, url_with_link_code, user_input_code
        phone = input_.phone_number
        code_lifetime = input_.code_life_time
        url_with_link_code = input_.url_with_link_code
        user_input_code = input_.user_input_code

    init(
        supertokens_config=SupertokensConfig('http://localhost:3567'),
        app_info=InputAppInfo(
            app_name="ST",
            api_domain="http://api.supertokens.io",
            website_domain="http://supertokens.io",
            api_base_path="/auth"
        ),
        framework='fastapi',
        recipe_list=[passwordless.init(
            contact_config=passwordless.ContactPhoneOnlyConfig(
                create_and_send_custom_text_message=create_and_send_custom_text_message,
            ),
            flow_type="USER_INPUT_CODE_AND_MAGIC_LINK",
        ), session.init()]
    )
    start_st()

    resp = sign_in_up_request_phone(driver_config_client, "+919909909998", True)

    assert resp.status_code == 200

    assert phone == "+919909909998"
    assert all([url_with_link_code, user_input_code, code_lifetime])
    assert code_lifetime > 0


@mark.asyncio
async def test_pless_login_custom_override(driver_config_client: TestClient):
    "Passwordless login: test custom override"
    phone = ""
    code_lifetime = 0
    url_with_link_code = ""
    user_input_code = ""
    app_name = ""

    def sms_delivery_override(oi: SMSDeliveryInterface[TypePasswordlessSmsDeliveryInput]):
        oi_send_sms = oi.send_sms

        async def send_sms(input_: TypePasswordlessSmsDeliveryInput, user_context: Dict[str, Any]):
            nonlocal phone, url_with_link_code, user_input_code, code_lifetime
            phone = input_.phone_number
            url_with_link_code = input_.url_with_link_code
            user_input_code = input_.user_input_code
            code_lifetime = input_.code_life_time

            await oi_send_sms(input_, user_context)

        oi.send_sms = send_sms
        return oi

    init(
        supertokens_config=SupertokensConfig('http://localhost:3567'),
        app_info=InputAppInfo(
            app_name="ST",
            api_domain="http://api.supertokens.io",
            website_domain="http://supertokens.io",
            api_base_path="/auth"
        ),
        framework='fastapi',
        recipe_list=[passwordless.init(
            contact_config=passwordless.ContactPhoneOnlyConfig(),
            flow_type="USER_INPUT_CODE_AND_MAGIC_LINK",
            sms_delivery=SMSDeliveryConfig(
                service=None,
                override=sms_delivery_override,
            )
        ), session.init()]
    )
    start_st()

    def api_side_effect(request: httpx.Request):
        nonlocal app_name
        sms_input = json.loads(request.content)["smsInput"]
        app_name = sms_input["appName"]

        return httpx.Response(200, json={})

    with respx_mock(assert_all_mocked=False) as mocker:
        mocker.route(host="localhost").pass_through()
        mocked_route = mocker.post(SUPERTOKENS_SMS_SERVICE_URL).mock(side_effect=api_side_effect)
        resp = sign_in_up_request_phone(driver_config_client, "+919909909998", True)

        assert resp.status_code == 200
        assert mocked_route.called

        assert phone == "+919909909998"
        assert app_name == "ST"
        assert all([url_with_link_code, user_input_code, code_lifetime])
        assert code_lifetime > 0


@mark.asyncio
async def test_pless_login_smtp_service(driver_config_client: TestClient):
    "Passwordless login: test smtp service"
    phone = ""
    code_lifetime = 0
    user_input_code = ""
    get_content_called, send_raw_email_called, outer_override_called = False, False, False
    twilio_api_called = False

    def twilio_service_override(oi: ServiceInterface[TypePasswordlessSmsDeliveryInput]):

        oi_send_raw_sms = oi.send_raw_sms

        async def send_raw_email_override(
            get_content_result: GetContentResult,
            _user_context: Dict[str, Any],
            from_: Union[str, None] = None,
            sid: Union[str, None] = None,
        ):
            nonlocal send_raw_email_called, phone, user_input_code
            send_raw_email_called = True

            assert get_content_result.body == user_input_code
            assert get_content_result.to_phone == "+919909909998"
            phone = get_content_result.to_phone

            await oi_send_raw_sms(get_content_result, _user_context, from_, sid)

        async def get_content_override(input_: TypePasswordlessSmsDeliveryInput, _user_context: Dict[str, Any]) -> GetContentResult:
            nonlocal get_content_called, user_input_code, code_lifetime
            get_content_called = True

            user_input_code = input_.user_input_code or ""
            code_lifetime = input_.code_life_time

            return GetContentResult(
                body=user_input_code,
                to_phone=input_.phone_number
            )

        oi.send_raw_sms = send_raw_email_override
        oi.get_content = get_content_override

        return oi

    twilio_sms_delivery_service = TwilioService(
        config=SMSDeliveryTwilioConfig(
            twilio_settings=TwilioServiceConfig(
                account_sid="ACTWILIO_ACCOUNT_SID",
                auth_token="test-token",
                from_="+919909909999",
            ),
            override=twilio_service_override,
        )
    )

    def sms_delivery_override(oi: SMSDeliveryInterface[TypePasswordlessSmsDeliveryInput]) -> SMSDeliveryInterface[TypePasswordlessSmsDeliveryInput]:
        oi_send_sms = oi.send_sms

        async def send_sms_override(input_: TypePasswordlessSmsDeliveryInput, user_context: Dict[str, Any]):
            nonlocal outer_override_called
            outer_override_called = True
            await oi_send_sms(input_, user_context)

        oi.send_sms = send_sms_override
        return oi

    init(
        supertokens_config=SupertokensConfig('http://localhost:3567'),
        app_info=InputAppInfo(
            app_name="ST",
            api_domain="http://api.supertokens.io",
            website_domain="http://supertokens.io",
            api_base_path="/auth"
        ),
        framework='fastapi',
        recipe_list=[passwordless.init(
            contact_config=passwordless.ContactPhoneOnlyConfig(),
            flow_type="USER_INPUT_CODE_AND_MAGIC_LINK",
            sms_delivery=SMSDeliveryConfig(
                service=twilio_sms_delivery_service,
                override=sms_delivery_override,
            )
        ), session.init()]
    )
    start_st()

    def json_callback(_: requests.Request, _ctx: Any) -> Dict[str, Any]:
        nonlocal twilio_api_called
        twilio_api_called = True

        return {}

    m: requests_mock.Mocker
    with requests_mock.Mocker(real_http=True) as m:
        m.post("https://api.twilio.com/2010-04-01/Accounts/ACTWILIO_ACCOUNT_SID/Messages.json", json=json_callback)

        resp = sign_in_up_request_phone(driver_config_client, "+919909909998", True)

        assert resp.status_code == 200

        assert phone == "+919909909998"
        assert all([outer_override_called, get_content_called, send_raw_email_called])
        assert code_lifetime > 0
        assert twilio_api_called
