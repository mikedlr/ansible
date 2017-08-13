#
# (c) 2017 Michael De La Rue
#
# This file is part of Ansible
#
# Ansible is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Ansible is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Ansible.  If not, see <http://www.gnu.org/licenses/>.

# Make coding more python3-ish
from __future__ import (absolute_import, division, print_function)

from nose.plugins.skip import SkipTest
import ansible.modules.cloud.amazon.lambda_policy as lambda_policy
from ansible.modules.cloud.amazon.lambda_policy import setup_module_object
from ansible.module_utils.aws.core import HAS_BOTO3
from ansible.module_utils import basic
from ansible.module_utils.basic import to_bytes
from ansible.compat.tests.mock import MagicMock
import json
import copy

from botocore.exceptions import ClientError
# try:
#     from botocore import ResourceNotFoundException
# except:
#     pass # will be protected by HAS_BOTO3

if not HAS_BOTO3:
    raise SkipTest("test_api_gateway.py requires the `boto3` and `botocore` modules")

base_module_args = {
    "region": "us-west-1",
    "function_name": "this_is_a_test_function",
    "state": "present",
    "statement_id": "test-allow-lambda",
    "principal": 123456,
    "action": "lambda:*"
}


def set_module_args(mod_args):
    args = json.dumps({'ANSIBLE_MODULE_ARGS': mod_args})
    basic._ANSIBLE_ARGS = to_bytes(args)


def test_module_is_created_sensibly():
    set_module_args(base_module_args)
    module = setup_module_object()
    assert module.params['function_name'] == 'this_is_a_test_function'


module_double = MagicMock()
module_double.fail_json_aws.side_effect = Exception("unexpected call to fail_json_aws")
module_double.check_mode = False

fake_module_params_present = {
    "state": "present",
    "statement_id": "test-allow-lambda",
    "principal": "apigateway.amazonaws.com",
    "action": "lambda:InvokeFunction",
    "source_arn": u'arn:aws:execute-api:us-east-1:123456789:efghijklmn/authorizers/*',
    "version": 0,
    "alias": None
}
fake_module_params_different = copy.deepcopy(fake_module_params_present)
fake_module_params_different["action"] = "lambda:api-gateway"
fake_module_params_absent = copy.deepcopy(fake_module_params_present)
fake_module_params_absent["state"] = "absent"

fake_policy_return = {
    u'Policy': (
        u'{"Version":"2012-10-17","Id":"default","Statement":[{"Sid":"1234567890abcdef1234567890abcdef",'
        u'"Effect":"Allow","Principal":{"Service":"apigateway.amazonaws.com"},"Action":"lambda:InvokeFunction",'
        u'"Resource":"arn:aws:lambda:us-east-1:123456789:function:test_authorizer",'
        u'"Condition":{"ArnLike":{"AWS:SourceArn":"arn:aws:execute-api:us-east-1:123456789:abcdefghij/authorizers/1a2b3c"}}},'
        u'{"Sid":"2234567890abcdef1234567890abcdef","Effect":"Allow","Principal":{"Service":"apigateway.amazonaws.com"},'
        u'"Action":"lambda:InvokeFunction","Resource":"arn:aws:lambda:us-east-1:123456789:function:test_authorizer",'
        u'"Condition":{"ArnLike":{"AWS:SourceArn":"arn:aws:execute-api:us-east-1:123456789:klmnopqrst/authorizers/4d5f6g"}}},'
        u'{"Sid":"1234567890abcdef1234567890abcdef","Effect":"Allow","Principal":{"Service":"apigateway.amazonaws.com"},'
        u'"Action":"lambda:InvokeFunction","Resource":"arn:aws:lambda:us-east-1:123456789:function:test_authorizer",'
        u'"Condition":{"ArnLike":{"AWS:SourceArn":"arn:aws:execute-api:eu-west-1:123456789:uvwxyzabcd/authorizers/7h8i9j"}}},'
        u'{"Sid":"test-allow-lambda","Effect":"Allow","Principal":{"Service":"apigateway.amazonaws.com"},'
        u'"Action":"lambda:InvokeFunction","Resource":"arn:aws:lambda:us-east-1:123456789:function:test_authorizer",'
        u'"Condition":{"ArnLike":{"AWS:SourceArn":"arn:aws:execute-api:us-east-1:123456789:efghijklmn/authorizers/*"}}},'
        u'{"Sid":"1234567890abcdef1234567890abcdef","Effect":"Allow","Principal":{"Service":"apigateway.amazonaws.com"},'
        u'"Action":"lambda:InvokeFunction","Resource":"arn:aws:lambda:us-east-1:123456789:function:test_authorizer",'
        u'"Condition":{"ArnLike":{"AWS:SourceArn":"arn:aws:execute-api:us-east-1:123456789:opqrstuvwx/authorizers/0k1l2m"}}}]}'),
    'ResponseMetadata': {
        'RetryAttempts': 0,
        'HTTPStatusCode': 200,
        'RequestId': 'abcdefgi-1234-a567-b890-123456789abc',
        'HTTPHeaders': {
            'date': 'Sun, 13 Aug 2017 10:54:17 GMT',
            'x-amzn-requestid': 'abcdefgi-1234-a567-b890-123456789abc',
            'content-length': '1878',
            'content-type': 'application/json',
            'connection': 'keep-alive'}}}

error_response = {'Error': {'Code': 'ResourceNotFoundException', 'Message': 'Fake Testing Error'}}
operation_name = 'FakeOperation'
resource_not_found_e = ClientError(error_response, operation_name)


def test_manage_state_adds_missing_permissions():
    lambda_client_double = MagicMock()
    # Policy actually: not present  Requested State: present  Should: create
    lambda_client_double.get_policy.side_effect = resource_not_found_e
    fake_module_params = copy.deepcopy(fake_module_params_present)
    module_double.params = fake_module_params
    lambda_policy.manage_state(module_double, lambda_client_double)
    lambda_client_double.get_policy.assert_called_once()
    lambda_client_double.add_permission.assert_called_once()
    lambda_client_double.remove_permission.assert_not_called()


def test_manage_state_leaves_existing_permissions():
    lambda_client_double = MagicMock()
    # Policy actually: present   Requested State: present  Should: do nothing
    lambda_client_double.get_policy.return_value = fake_policy_return
    fake_module_params = copy.deepcopy(fake_module_params_present)
    module_double.params = fake_module_params
    lambda_policy.manage_state(module_double, lambda_client_double)
    lambda_client_double.get_policy.assert_called_once()
    lambda_client_double.add_permission.assert_not_called()
    lambda_client_double.remove_permission.assert_not_called()


def test_manage_state_updates_nonmatching_permissions():
    lambda_client_double = MagicMock()
    # Policy actually: present   Requested State: present  Should: do nothing
    lambda_client_double.get_policy.return_value = fake_policy_return
    fake_module_params = copy.deepcopy(fake_module_params_different)
    module_double.params = fake_module_params
    lambda_policy.manage_state(module_double, lambda_client_double)
    lambda_client_double.get_policy.assert_called_once()
    lambda_client_double.add_permission.assert_called_once()
    lambda_client_double.remove_permission.assert_called_once()


def test_manage_state_removes_unwanted_permissions():
    lambda_client_double = MagicMock()
    # Policy actually: present  Requested State: not present  Should: remove
    lambda_client_double.get_policy.return_value = fake_policy_return
    fake_module_params = copy.deepcopy(fake_module_params_absent)
    module_double.params = fake_module_params
    lambda_policy.manage_state(module_double, lambda_client_double)
    lambda_client_double.get_policy.assert_called_once()
    lambda_client_double.add_permission.assert_not_called()
    lambda_client_double.remove_permission.assert_called_once()


def test_manage_state_leaves_already_removed_permissions():
    lambda_client_double = MagicMock()
    # Policy actually: absent   Requested State: absent  Should: do nothing
    lambda_client_double.get_policy.side_effect = resource_not_found_e
    fake_module_params = copy.deepcopy(fake_module_params_absent)
    module_double.params = fake_module_params
    lambda_policy.manage_state(module_double, lambda_client_double)
    lambda_client_double.get_policy.assert_called_once()
    lambda_client_double.add_permission.assert_not_called()
    lambda_client_double.remove_permission.assert_not_called()
