import sys

from oba_deployer.aws import prepare_new
from oba_deployer.gtfs import validate_gtfs, update
from oba_deployer.oba import install, start, deploy_webapps, install_and_start_watchdog


def run_all():
    '''A single script to deploy OBA in one command to a new EC2 instance
    '''
    
    # dl gtfs and validate it
    if not validate_gtfs():
        print('GTFS Validation Failed')
        sys.exit()
    
    # setup new EC2 instance
    instance = prepare_new()
    
    public_dns_name = instance.public_dns_name
    
    # install OBA
    install(public_dns_name)
    
    # update GTFS, make new bundle
    update(public_dns_name)
    
    # start server
    start(public_dns_name)
    
    # install watchdog python script
    install_and_start_watchdog(public_dns_name)
    
    print('Deployment of new server has finished.  Please follow steps: OneBusAway Setup and xWiki Setup')
