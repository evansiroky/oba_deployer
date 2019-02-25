import sys

from oba_deployer.aws import prepare_new
from oba_deployer.gtfs import update, validate_static_gtfs_files
from oba_deployer.oba import install, start, install_and_start_watchdog


def run_all():
    '''A single script to deploy OBA in one command to a new EC2 instance
    '''

    # dl gtfs and validate it
    if not validate_static_gtfs_files():
        print('GTFS Validation Failed')
        sys.exit()

    # setup new EC2 instance
    instance_public_dns_name = prepare_new()

    # install OBA
    install(instance_public_dns_name)

    # update GTFS, make new bundle
    update(instance_public_dns_name)

    # start server
    start(instance_public_dns_name)

    # install watchdog python script
    install_and_start_watchdog(instance_public_dns_name)

    print('Deployment of new server has finished.  Please follow steps: OneBusAway Setup and xWiki Setup')
