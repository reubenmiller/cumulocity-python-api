# Copyright (c) 2020 Software AG,
# Darmstadt, Germany and/or Software AG USA Inc., Reston, VA, USA,
# and/or its subsidiaries and/or its affiliates and/or their licensors.
# Use, reproduction, transfer, publication or disclosure is prohibited except
# as specifically provided for in your License Agreement with Software AG.

import sys
from typing import Union

import requests
import collections


class CumulocityRestApi:
    """Cumulocity base REST API.

    Provides REST access to a Cumulocity instance.
    """

    ACCEPT_MANAGED_OBJECT = 'application/vnd.com.nsn.cumulocity.managedobject+json'
    CONTENT_MEASUREMENT_COLLECTION = 'application/vnd.com.nsn.cumulocity.measurementcollection+json'

    def __init__(self, base_url, tenant_id, username, password, tfa_token=None, application_key=None):
        self.base_url = base_url
        self.tenant_id = tenant_id
        self.username = username
        self.password = password
        self.tfa_token = tfa_token
        self.application_key = application_key
        self.__auth = f'{tenant_id}/{username}', password
        self.__default_headers = {}
        if self.tfa_token:
            self.__default_headers['tfatoken'] = self.tfa_token
        if self.application_key:
            self.__default_headers['X-Cumulocity-Application-Key'] = self.application_key
        self.session = self._create_session()

    def _create_session(self) -> requests.Session:
        s = requests.Session()
        s.auth = self.__auth
        s.headers = {'Accept': 'application/json'}
        if self.application_key:
            s.headers.update({'X-Cumulocity-Application-Key': self.application_key})
        return s

    def prepare_request(self, method, resource, body=None, additional_headers=None):
        hs = self.__default_headers
        if additional_headers:
            hs.update(additional_headers)
        rq = requests.Request(method=method, url=self.base_url + resource, headers=hs, auth=self.__auth)
        if body:
            rq.json = body
        return rq.prepare()

    def get(self, resource, params=None, accept=None, ordered=False) -> dict:
        """Generic HTTP GET wrapper, dealing with standard error returning a JSON body object."""
        additional_headers = self._prepare_headers(accept=accept)
        r = self.session.get(self.base_url + resource, params=params, headers=additional_headers)
        if r.status_code == 404:
            raise KeyError(f"No such object: {resource}")
        if 500 <= r.status_code <= 599:
            raise SyntaxError(f"Invalid GET request. Status: {r.status_code} Response:\n" + r.text)
        if r.status_code != 200:
            raise ValueError(f"Unable to perform GET request. Status: {r.status_code} Response:\n" + r.text)
        if r.content:
            return r.json() if not ordered else r.json(object_pairs_hook=collections.OrderedDict)
        return {}

    def post(self, resource, json, accept=None, content_type=None) -> dict:
        """Generic HTTP POST wrapper, dealing with standard error returning a JSON body object."""
        assert isinstance(json, dict)
        additional_headers = self._prepare_headers(accept=accept, content_type=content_type)
        r = self.session.post(self.base_url + resource, json=json, headers=additional_headers)
        if 500 <= r.status_code <= 599:
            raise SyntaxError(f"Invalid POST request. Status: {r.status_code} Response:\n" + r.text)
        if r.status_code != 201 and r.status_code != 200:
            raise ValueError(f"Unable to perform POST request. Status: {r.status_code} Response:\n" + r.text)
        if r.content:  # todo: do we need to test this?
            return r.json()
        return {}

    def post_file(self, resource, file, binary_meta_information):
        """Generic POST wrapper.

        Used for posting binary data.
        """
        assert isinstance(binary_meta_information, Binary)
        assert file is not None

        headers = {'Accept': 'application/json', **self.__default_headers}

        payload = {
            'object': (None, str(binary_meta_information._to_full_json()).replace("'", '"')),
            'filesize': (None, sys.getsizeof(file)),
            'file': (None, file.read())
        }

        r = self.session.post(self.base_url + resource, files=payload, auth=self.__auth, headers=headers)
        if 500 <= r.status_code <= 599:
            raise SyntaxError(f"Invalid POST request. Status: {r.status_code} Response:\n" + r.text)
        if r.status_code != 201:
            raise ValueError("Unable to perform POST request.", ("Status", r.status_code), ("Response", r.text))
        return r.json()

    def put(self, resource, json, accept=None, content_type=None) -> dict:
        """Generic HTTP PUT wrapper, dealing with standard error returning a JSON body object."""
        assert isinstance(json, dict)
        additional_headers = self._prepare_headers(accept=accept, content_type=content_type)
        r = self.session.put(self.base_url + resource, json=json, headers=additional_headers)
        if r.status_code == 404:
            raise KeyError(f"No such object: {resource}")
        if 500 <= r.status_code <= 599:
            raise SyntaxError(f"Invalid PUT request. Status: {r.status_code} Response:\n" + r.text)
        if r.status_code != 200:
            raise ValueError(f"Unable to perform PUT request. Status: {r.status_code} Response:\n" + r.text)
        if r.content:  # todo: do we need to test this?
            return r.json()
        return {}

    def put_file(self, resource, file, media_type):
        headers = {'Content-Type': media_type, **self.__default_headers}
        r = self.session.put(self.base_url + resource, data=file.read(), auth=self.__auth, headers=headers)
        if r.status_code == 404:
            raise KeyError(f"No such object: {resource}")
        if 500 <= r.status_code <= 599:
            raise SyntaxError(f"Invalid PUT request. Status: {r.status_code} Response:\n" + r.text)
        if r.status_code != 201:
            raise ValueError(f"Unable to perform PUT request. Status: {r.status_code} Response:\n" + r.text)

    def delete(self, resource):
        """Generic HTTP DELETE wrapper, dealing with standard error returning a JSON body object."""
        r = self.session.delete(self.base_url + resource)
        if r.status_code == 404:
            raise KeyError(f"No such object: {resource}")
        if 500 <= r.status_code <= 599:
            raise SyntaxError(f"Invalid DELETE request. Status: {r.status_code} Response:\n" + r.text)
        if r.status_code != 204 and r.status_code != 200:
            raise ValueError(f"Unable to perform DELETE request. Status: {r.status_code} Response:\n" + r.text)

    @classmethod
    def _prepare_headers(cls, **kwargs) -> Union[dict, None]:
        """Format a set of named arguments into a header dictionary.

        This will format the argument name into Header-Case (from snake_case).

        Params:
            kwargs: A list of named header values, each can be None

        Returns:
            dict: A properly formatted header dictionary for use with requests
            None: If not of the arguments have an actual value
        """
        if not any(kwargs.values()):
            return None

        def format_key(key):
            # split by '_', uppercase the first character, lowercase the rest and join with '-'
            return '-'.join([part[0].upper() + part[1:].lower() for part in key.split('_')])

        return {format_key(key): value for key, value in kwargs.items() if value}