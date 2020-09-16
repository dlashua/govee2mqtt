import requests
import asyncio
import logging
import json

_LOGGER = logging.getLogger(__name__)


class GoveeAPI(object):
    def __init__(self, api_key):
        self.api_key = api_key

    def get_device(self, device_id, model):
        _LOGGER.debug('getting device {}'.format(device_id))
        headers = self.get_headers()

        params = {
            'device': device_id,
            'model': model
        }

        try:
            r = requests.get('https://developer-api.govee.com/v1/devices/state', headers=headers, params=params)
            if r.status_code >= 400:
                _LOGGER.error('BAD RESPONSE CODE GETTING DEVICE {}'.format(device_id))
                return {}
            data = r.json()
        except:
            _LOGGER.error('ERROR GETTING DEVICE {}'.format(device_id))
            return {}

        _LOGGER.debug(data)

        device = data['data']['device']

        new_attributes = {}
        for attribute_data in data['data']['properties']:
            for key in attribute_data:
                new_attributes[key] = attribute_data[key]

        return new_attributes


    def get_device_list(self):
        _LOGGER.debug('getting devices list')
        headers = self.get_headers()

        try:
            r = requests.get('https://developer-api.govee.com/v1/devices', headers=headers)
            if r.status_code >= 400:
                _LOGGER.error('BAD RESPONSE CODE GETTING DEVICE LIST')
                return {}
            data = r.json()
        except:
            _LOGGER.error('ERROR GETTING DEVICE LIST')
            return {}

        _LOGGER.debug(data)
        return data['data']

 
    def get_headers(self):
        return {
            'Content-Type': "application/json",
            'Govee-API-Key': self.api_key
        }


    def send_command(self, device_id, model, cmd, value):
        data = {
            "device": device_id,
            "model": model,
            "cmd": {
                "name": cmd,
                "value": value
            },
        }

        headers = self.get_headers()
        try:
            r = requests.put('https://developer-api.govee.com/v1/devices/control', headers=headers, data=json.dumps(data))
            if r.status_code >= 400:
                _LOGGER.error('BAD RESPONSE CODE SENDING COMMAND {} {}'.format(device_id, data))
                return {}
        except:
            _LOGGER.error('ERROR SENDING DEVICE COMMAND')
            
        _LOGGER.debug(r)
