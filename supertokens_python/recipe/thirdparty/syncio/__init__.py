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
from typing import Any, Dict, List, Union

from supertokens_python.async_to_sync_wrapper import sync

from ..types import User


def get_user_by_id(
    user_id: str, user_context: Union[None, Dict[str, Any]] = None
) -> Union[User, None]:
    from supertokens_python.recipe.thirdparty.asyncio import get_user_by_id

    return sync(get_user_by_id(user_id, user_context))


def get_users_by_email(
    email: str, user_context: Union[None, Dict[str, Any]] = None
) -> List[User]:
    from supertokens_python.recipe.thirdparty.asyncio import get_users_by_email

    return sync(get_users_by_email(email, user_context))


def get_user_by_third_party_info(
    third_party_id: str,
    third_party_user_id: str,
    user_context: Union[None, Dict[str, Any]] = None,
):
    from supertokens_python.recipe.thirdparty.asyncio import (
        get_user_by_third_party_info,
    )

    return sync(
        get_user_by_third_party_info(third_party_id, third_party_user_id, user_context)
    )


def sign_in_up(
    third_party_id: str,
    third_party_user_id: str,
    email: str,
    user_context: Union[None, Dict[str, Any]] = None,
):
    from supertokens_python.recipe.thirdparty.asyncio import sign_in_up

    return sync(sign_in_up(third_party_id, third_party_user_id, email, user_context))
