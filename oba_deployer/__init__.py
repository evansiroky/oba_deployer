import os

__import__('pkg_resources').declare_namespace(__name__)


# assumes running from root oba_deployer folder
BASE_DIR = os.getcwd()
CONFIG_TEMPLATE_DIR = os.path.join(BASE_DIR, 'config_templates')
CONFIG_DIR = os.path.join(BASE_DIR, 'config')
DATA_DIR = os.path.join(BASE_DIR, 'data')
DL_DIR = os.path.join(DATA_DIR, 'downloads')
REPORTS_DIR = os.path.join(DATA_DIR, 'reports')
GTFS_FILES_CSV = os.path.join(CONFIG_DIR, 'gtfs_urls.csv')
