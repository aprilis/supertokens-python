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
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from supertokens_python.recipe.session.interfaces import APIInterface, APIOptions

from supertokens_python.utils import default_user_context, send_200_response


async def handle_signout_api(api_implementation: APIInterface, api_options: APIOptions):
    if (
        api_implementation.disable_signout_post
        or api_implementation.signout_post is None
    ):
        return None
    user_context = default_user_context(api_options.request)

    session = await api_options.recipe_implementation.get_session(
        request=api_options.request,
        anti_csrf_check=None,
        session_required=False,
        user_context=user_context,
    )

    response = await api_implementation.signout_post(session, api_options, user_context)
    if api_options.response is None:
        raise Exception("Should never come here")
    return send_200_response(response.to_json(), api_options.response)
