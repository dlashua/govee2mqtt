import asyncio
import goveeapi

import paho.mqtt.client as mqtt
import time
import json
import logging

_LOGGER = logging.getLogger(__name__)


class GoveeMqtt(object):

    def __init__(self, config):
        self.mqtt_config = config['mqtt']
        self.govee_config = config['govee']

        self.devices = {}
        self.running = False

        self.boosted = []

        self.mqttc = None
        self.mqtt_connect_time = None

        self.mqttc_create()

        self.goveec = goveeapi.GoveeAPI(self.govee_config['api_key'])

        self.device_update_interval = config['govee'].get('device_interval', 30)
        self.device_update_boosted_interval = config['govee'].get('device_boost_interval', 5)
        self.device_list_update_interval = config['govee'].get('device_list_interval', 300)

        self.mqtt_from_govee_field_map = {
            'state': ['powerState', lambda x: 'ON' if x == 'on' else 'OFF'],
            # 'kelvin': ['colorTemInKelvin', int],
            'brightness': ['brightness', int],
            'color': ['color', lambda x: {'r': x['r'], 'g': x['g'], 'b': x['b']}],
            'availability': ['online', lambda x: 'online' if x is True else 'offline'],
        }

        self.govee_from_mqtt_field_map = {
            'turn': ['state', lambda x: 'on' if x == 'ON' else 'off'],
            'brightness': ['brightness', lambda x: round(x/254*100)],
            'color': ['color', lambda x: {'r': x['r'], 'g': x['g'], 'b': x['b']}],
        }


        asyncio.run(self.start_govee_loop())


    # MQTT Functions
    ################################
    def mqtt_on_connect(self, client, userdata, flags, rc):
        if rc != 0:
            _LOGGER.debug("MQTT Connection Issue")
            exit()
        _LOGGER.debug('MQTT CONNECTED')
        client.subscribe(self.get_sub_topic())

    def mqtt_on_disconnect(self, client, userdata, rc):
        _LOGGER.debug("MQTT Disconnected")
        if time.time() > self.mqtt_connect_time + 10:
            self.mqttc_create()
        else:
            exit()

    def mqtt_on_message(self, client, userdata, msg):
        topic = msg.topic
        payload = json.loads(msg.payload)
        device_id = topic[(len(self.mqtt_config['prefix']) + 1):-4]
        _LOGGER.debug('got a message {}: {}'.format(device_id, payload))

        self.send_command(device_id, payload)

    def mqtt_on_subscribe(self, *args, **kwargs):
        _LOGGER.debug('subscribed')


    # Topic Helpers
    ########################################
    def get_sub_topic(self):
        return "{}/+/set".format(self.mqtt_config['prefix'])

    def get_pub_topic(self, device, attribute):
        return "{}/{}/{}".format(self.mqtt_config['prefix'], device, attribute)

    def get_state_topic(self, device_id):
        return "{}/{}".format(self.mqtt_config['prefix'], device_id)

    def get_set_topic(self, device_id):
        return "{}/{}/set".format(self.mqtt_config['prefix'], device_id)


    def get_homeassistant_config_topic(self, device_id):
        formatted_device_id = "govee_" + device_id.replace(':','')
        return "{}/light/{}/config".format(self.mqtt_config['homeassistant'], formatted_device_id)


    # MQTT Helpers
    #########################################
    def mqttc_create(self):
        self.mqttc = mqtt.Client(client_id="govee")
        self.mqttc.username_pw_set(
            username=self.mqtt_config.get("username"),
            password=self.mqtt_config.get("password"),
        )
        _LOGGER.debug("CALLING MQTT CONNECT")
        self.mqttc.on_connect = self.mqtt_on_connect
        self.mqttc.on_disconnect = self.mqtt_on_disconnect
        self.mqttc.on_message = self.mqtt_on_message
        self.mqttc.on_subscribe = self.mqtt_on_subscribe
        self.mqttc.connect(
            self.mqtt_config.get("host"), self.mqtt_config.get("port",1883), keepalive=60
        )
        self.mqtt_connect_time = time.time()
        self.mqttc.loop_start()

        self.running = True

    def homeassistant_config(self, device_id):
        if 'homeassistant' not in self.mqtt_config:
            return

        config = {
            # 'availability_topic': self.get_pub_topic(device_id, 'availability'),
            'brightness': True,
            'brightness_scale': 255,
            # 'color_temp': True,
            'rgb': True,
            'command_topic': self.get_set_topic(device_id),
            'device': {
                "identifiers": "govee_" + device_id.replace(':',''),
                "manufacturer": "Govee",
                "model": self.devices[device_id]['model'],
                "name": self.devices[device_id]['name'],
                "sw_version": 'govee2mqtt v0.0.1',
            },
            'schema': 'json',
            'state_topic': self.get_state_topic(device_id),
            'json_attributes_topic': self.get_state_topic(device_id),
            'unique_id': "govee_light_" + device_id.replace(':',''),
            'name': self.devices[device_id]['name'],
        }
        
        self.mqttc.publish(self.get_homeassistant_config_topic(device_id), json.dumps(config), retain=True)


    # Govee Helpers
    ###########################################

    def refresh_device_list(self):
        data = self.goveec.get_device_list()
        if 'devices' not in data:
            return

        for device in data['devices']:
            device_id = device['device']

            if device['controllable'] is True:
                first = False
                if device_id not in self.devices:
                    first = True
                    self.devices[device_id] = {}
                    self.devices[device_id]['model'] = device['model']

                self.devices[device_id]['name'] = device['deviceName']
                self.devices[device_id]['supported_commands'] = device['supportCmds']

                if first:
                    _LOGGER.info('NEW DEVICE {} ({})'.format(self.devices[device_id]['name'],device_id))
                    self.homeassistant_config(device_id)

                _LOGGER.debug('saw {}'.format(device_id))
            else:
                _LOGGER.debug('saw but not controlable {}'.format(device_id))

        _LOGGER.debug(self.devices)

    def refresh_all_devices(self):
        for device_id in self.devices:
            if device_id not in self.boosted:
                self.refresh_device(device_id)

    def refresh_boosted_devices(self):
        for device_id in self.boosted:
            self.refresh_device(device_id)

    def refresh_device(self, device_id):
        model = self.devices[device_id]['model']
        data = self.goveec.get_device(device_id, model)
        _LOGGER.debug('original data {} {}'.format(device_id, data))

        self.publish_attributes(device_id, data)

    def publish_attributes(self, device_id, orig_data):
        changed = False
        data = self.convert_mqtt_from_govee(orig_data)
        _LOGGER.debug('converted data {} {}'.format(device_id, data))
        for attribute in data:
            if attribute not in self.devices[device_id] or self.devices[device_id][attribute] != data[attribute]:
                changed = True
                self.publish_handler(device_id, attribute, data[attribute])

        if changed:
            self.publish_state_handler(device_id)

    def convert_mqtt_from_govee(self, data):
        return self.convert_with_map(data, self.mqtt_from_govee_field_map)


    def convert_govee_from_mqtt(self, data):
        return self.convert_with_map(data, self.govee_from_mqtt_field_map)

    def convert_with_map(self, data, field_map):
        new_data = {}

        for new_key in field_map:
            map_value = list(field_map[new_key])
            orig_key = map_value.pop(0)
            if orig_key not in data:
                continue
            new_value = data[orig_key]
            for converter in map_value:
                new_value = converter(new_value)
            new_data[new_key] = new_value

        return new_data

    def send_command(self, device_id, data):
        cmd = self.convert_govee_from_mqtt(data)

        _LOGGER.debug('command {} = {}'.format(device_id, cmd))
        model = self.devices[device_id]['model']

        if 'brightness' in cmd and 'turn' in cmd:
            del cmd['turn']

        if 'color' in cmd and 'turn' in cmd:
            del cmd['turn']

        first = True
        for key in cmd:
            if not first:
                time.sleep(1)
            _LOGGER.info('TO DEVICE {} ({}) {} = {}'.format(self.devices[device_id]['name'], device_id, key, cmd[key]))
            self.goveec.send_command(device_id, model, key, cmd[key])
            first = False

        if device_id not in self.boosted:
            self.boosted.append(device_id)


    def publish_handler(self, device_id, attribute, value):
        self.mqttc.publish(self.get_pub_topic(device_id, attribute), json.dumps(value), retain=True)
        self.devices[device_id][attribute] = value
        name = self.devices[device_id]['name']
        _LOGGER.info("UPDATE: {} ({}): {} = {}".format(name, device_id, attribute, value))

    def publish_state_handler(self, device_id):
        self.mqttc.publish(self.get_state_topic(device_id), json.dumps(self.devices[device_id]), retain=True)
        _LOGGER.debug("Published {}: {}".format(device_id, self.devices[device_id]))
        if device_id in self.boosted:
            self.boosted.remove(device_id)

    async def start_govee_loop(self):
        await asyncio.gather(
            self.device_list_loop(),
            self.device_loop(),
            self.device_boosted_loop(),
        )

    async def device_list_loop(self):
        while self.running == True:
            self.refresh_device_list()
            await asyncio.sleep(self.device_list_update_interval)

    async def device_loop(self):
        while self.running == True:
            self.refresh_all_devices()
            await asyncio.sleep(self.device_update_interval)

    async def device_boosted_loop(self):
        while self.running == True:
            self.refresh_boosted_devices()
            await asyncio.sleep(self.device_update_boosted_interval)
    
    
