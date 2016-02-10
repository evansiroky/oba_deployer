import os
import shutil

from deploy_utils.config import ConfigHelper

from oba_deployer import CONFIG_DIR, CONFIG_TEMPLATE_DIR


def clean():
    '''Deletes the config folder
    '''
    try:
        shutil.rmtree(CONFIG_DIR)
    except:
        pass


def setup(config_type):
    '''Master function for setting up each config type
    '''

    # create config dir if not exists
    try:
        os.makedirs(CONFIG_DIR)
    except:
        pass

    conf = ConfigHelper(CONFIG_DIR, CONFIG_TEMPLATE_DIR)
    conf.setup(config_type)


def setup_all():
    '''Calls the setup of all config Items
    '''
    setup('aws')
    setup('gtfs')
    setup('oba')
    setup('watchdog')