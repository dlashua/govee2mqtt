import yaml
import argparse
import govee_mqtt

import logging



argparser = argparse.ArgumentParser()
argparser.add_argument(
    "-c",
    "--config",
    required=True,
    help="Directory holding config.yaml and application storage",
)
args = argparser.parse_args()

configdir = args.config
if not configdir.endswith("/"):
    configdir = configdir + "/"

with open(configdir + "config.yaml") as file:
    config = yaml.load(file, Loader=yaml.FullLoader)

if 'debug' in config and config['debug'] is True:
    logging.basicConfig(level=logging.DEBUG)
else:
    logging.basicConfig(level=logging.INFO)

logging.info('Starting Application')
govee_mqtt.GoveeMqtt(config)