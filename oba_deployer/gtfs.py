try: 
    input = raw_input
except NameError: 
    pass

import csv
from datetime import datetime
import os
import time

from deploy_utils.config import ConfigHelper
from deploy_utils.fab import unix_path_join
from fab_deploy.crontab import crontab_update
from fabric.api import env, run, put, cd
from fabric.contrib.files import exists
from transitfeed.gtfsfactory import GetGtfsFactory
from transitfeed.problems import ProblemReporter, TYPE_WARNING
import requests
import transitfeed

from oba_deployer import CONFIG_DIR, CONFIG_TEMPLATE_DIR, DL_DIR, GTFS_FILES_CSV, REPORTS_DIR
from oba_deployer.feedvalidator import HTMLCountingProblemAccumulator
from oba_deployer.oba import OBAFab


conf_helper = ConfigHelper(CONFIG_DIR, CONFIG_TEMPLATE_DIR)


class GtfsFab(OBAFab):

    def __init__(self, host_name, aws_conf, gtfs_conf, oba_conf):
        OBAFab.__init__(self, host_name, aws_conf, gtfs_conf, oba_conf)
        self.federation_builder_folder = unix_path_join('/home',
                                                        self.user,
                                                        self.oba_base_folder,
                                                        'onebusaway-transit-data-federation-builder')
        
    def update_gtfs(self):
        '''Uploads the downloaded gtfs zip files and bundle.xml to the server and builds a new bundle.
        '''
        
        # check if data folders exists
        if not exists(self.data_dir):
            run('mkdir {0}'.format(self.data_dir))

        reader = csv.DictReader(open(GTFS_FILES_CSV))
        for bundle in reader:
            gtfs_file_name = '{0}-gtfs.zip'.format(bundle['bundle_name'])
            remote_gtfs_file = unix_path_join(self.data_dir, gtfs_file_name)

            # remove old gtfs file (if needed)
            if exists(remote_gtfs_file):
                run('rm {0}'.format(remote_gtfs_file))

            # upload new file
            put(os.path.join(DL_DIR, gtfs_file_name), 'data')

        # upload bundle.xml
        put(os.path.join(CONFIG_DIR, 'bundle.xml'), 'data')
        
        # create new bundle
        bundle_main = 'org.onebusaway.transit_data_federation.bundle.FederatedTransitDataBundleCreatorMain'
        more_args = self.gtfs_conf.get('extra_bundle_build_args')
        with cd(self.federation_builder_folder):
            run('java -classpath .:target/* {0} {1} {2} {3}'.format(bundle_main,
                                                                    unix_path_join(self.data_dir, 'bundle.xml'),
                                                                    self.bundle_dir,
                                                                    more_args))
            
    def install_gtfs_update_crontab(self):
        '''Installs and starts a crontab to automatically dl and build a data bundle nightly.
        '''
        
        # prepare update script
        reader = csv.DictReader(open(GTFS_FILES_CSV))
        gtfs_wgets = '\n'.join([
            'wget -O {0} {1} -o {2}'.format(
                unix_path_join(self.data_dir, '{0}-gtfs.zip'.format(bundle['bundle_name'])),
                bundle['static_url'],
                '{0}_nightly_dl.out'.format(bundle['bundle_name'])
            ) for bundle in reader
        ])
        refresh_settings = dict(gtfs_wgets=gtfs_wgets,
                                federation_builder_folder=self.federation_builder_folder,
                                bundle_dir=self.bundle_dir,
                                bundle_xml=unix_path_join(self.data_dir, 'bundle.xml'),
                                extra_args=self.gtfs_conf.get('extra_bundle_build_args'),
                                user=self.user,
                                cron_email=self.aws_conf.get('cron_email'),
                                from_mailer=env.host_string)
        
        # check if script folders exists
        if not exists(self.script_dir):
            run('mkdir {0}'.format(self.script_dir))
            
        self.populate_and_upload_template_file(refresh_settings, conf_helper, 'gtfs_refresh.sh', self.script_dir)
        with cd(self.script_dir):
            run('chmod 755 gtfs_refresh.sh')
                
        # prepare update script
        with open(os.path.join(CONFIG_TEMPLATE_DIR, 'gtfs_refresh_crontab')) as f:
            refresh_cron_template = f.read()
            
        cron_settings = dict(cron_email=self.aws_conf.get('cron_email'),
                             logfile=unix_path_join(self.data_dir, 'nightly_bundle.out'),
                             script_folder=self.script_dir)
        gtfs_refresh_cron = refresh_cron_template.format(**cron_settings)
            
        crontab_update(gtfs_refresh_cron, 'gtfs_refresh_cron')
    

def validate_static_gtfs_files():
    '''Download and validate the latest static GTFS file(s) for each defined agency.
    
    Returns:
        boolean: True if no errors in any of the GTFS files.
    '''
    
    # Create the `downloads` directory if it doesn't exist
    if not os.path.exists(DL_DIR):
        os.makedirs(DL_DIR)
        
    # Create the `reports` directory if it doesn't exist
    if not os.path.exists(REPORTS_DIR):
        os.makedirs(REPORTS_DIR)

    reader = csv.DictReader(open(GTFS_FILES_CSV))
    return all([validate_local_gtfs_file(bundle) for bundle in reader])


def validate_local_gtfs_file(bundle):
    '''Downloads and validates a single GTFS file.

    Returns:
        boolean: True if no errors were found in the GTFS file.
    '''

    name = bundle['bundle_name']
    url = bundle['static_url']

    # download gtfs
    print '---------------------------------------'
    print('Validating GTFS for: {0}'.format(name))


    print('Downloading GTFS from {0}'.format(url))
    gtfs_file_name = os.path.join(DL_DIR, '{0}-gtfs.zip'.format(name))
    r = requests.get(url, stream=True)
    with open(gtfs_file_name, 'wb') as f:
        for chunk in r.iter_content(chunk_size=1024): 
            if chunk:  # filter out keep-alive new chunks
                f.write(chunk)
                f.flush()
                
    # load gtfs
    gtfs_factory = GetGtfsFactory()
    accumulator = HTMLCountingProblemAccumulator(limit_per_type=50)
    problem_reporter = ProblemReporter(accumulator)
    loader = gtfs_factory.Loader(gtfs_file_name, problems=problem_reporter)
    schedule = loader.Load()
    
    # validate gtfs
    schedule.Validate()
    
    # check for trips with a null value for trip_headsign
    for trip in schedule.GetTripList():
        if trip.trip_headsign == 'null':
            problem_reporter.InvalidValue('trip_headsign', 'null', type=TYPE_WARNING)
            
    # write GTFS report to file
    report_name = 'gtfs_validation_{0}.html'.format(datetime.now().strftime('%Y-%m-%d %H.%M'))
    report_filenmae = os.path.join(REPORTS_DIR, report_name)
    with open(report_filenmae, 'w') as f:
        accumulator.WriteOutput(gtfs_file_name, f, schedule, transitfeed)
        
    print('GTFS validation report written to {0}'.format(report_filenmae))
    
    # post-validation
    gtfs_validated = True
    num_errors = accumulator.ErrorCount()
    if num_errors > 0:
        gtfs_validated = False
        print('{0} errors in GTFS data'.format(num_errors))
        
    num_warnings = accumulator.WarningCount()
    if num_warnings > 0:
        print('{0} warnings about GTFS data'.format(num_warnings))
        
    if 'ExpirationDate' in accumulator.ProblemListMap(TYPE_WARNING).keys():
        start_date, end_date = schedule.GetDateRange()
        last_service_day = datetime(*(time.strptime(end_date, "%Y%m%d")[0:6]))
        if last_service_day < datetime.now():
            print('GTFS Feed has expired.')
            gtfs_validated = False

    print 'GTFS validation for {0} {1}'.format(name, 'passed' if gtfs_validated else 'failed')
    print '---------------------------------------'
    return gtfs_validated


def update(instance_dns_name=None):
    '''Updates the needed gtfs files and bundle.xml on the EC2 instance and tells OBA to create a new bundle.
    
    This assumes that onebusaway-transit-data-federation-builder has been installed on the server.
    It will also download the needed gtfs files if it does not find it in the local downloads folder.
    
    Args:
        instance_dns_name (string, default=None): The EC2 instance to upload the gtfs to.
    '''
    
    if not validate_static_gtfs_files():
        raise Exception('GTFS static file validation Failed.')
        
    if not instance_dns_name:
        instance_dns_name = input('Enter EC2 public dns name: ')
        
    gtfs_fab = GtfsFab(instance_dns_name,
                       conf_helper.get_config('aws'),
                       conf_helper.get_config('gtfs'),
                       conf_helper.get_config('oba'))
    gtfs_fab.update_gtfs()
    gtfs_fab.install_gtfs_update_crontab()
