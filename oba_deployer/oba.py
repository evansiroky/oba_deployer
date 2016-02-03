try:
    input = raw_input
except NameError: 
    pass
import os

from deploy_utils.config import ConfigHelper
from deploy_utils.fab import AmazonLinuxFab, unix_path_join
from fab_deploy import crontab_update
from fabric.api import run, put, cd, sudo
from fabric.contrib.files import exists

from oba_deployer import CONFIG_DIR, CONFIG_TEMPLATE_DIR


conf_helper = ConfigHelper(CONFIG_DIR, CONFIG_TEMPLATE_DIR)


class OBAFab(AmazonLinuxFab):

    def __init__(self, host_name, aws_conf, gtfs_conf=None, oba_conf=None):
        super(OBAFab, self).__init__(aws_conf, host_name)
        self.aws_conf = aws_conf
        self.gtfs_conf = gtfs_conf
        self.oba_conf = oba_conf

        self.data_dir = unix_path_join('/home', self.user, 'data')
        self.bundle_dir = unix_path_join(self.data_dir, 'bundle')
        self.script_dir = unix_path_join('/home', self.user, 'scripts')
        self.config_dir = unix_path_join('/home', self.user, 'conf')

        if oba_conf:
            self.oba_base_folder = oba_conf.get('oba_base_folder')


class ObaInstallFab(OBAFab):
    
    def clone_repo(self):
        '''Clone the repo and upload some files.
        '''
        
        # clone the repo
        run('git clone {0}'.format(self.oba_conf.get('oba_git_repo')))
        
        with cd(self.oba_base_folder):
            run('git checkout {0}'.format(self.oba_conf.get('oba_git_branch')))
            run('/usr/local/maven/bin/mvn clean install')
        
    def build_webapp(self, data_dict, config_template_file, webapp):
        '''Build a webapp using maven.
        
        Args:
            data_dict (dict): A dict to set the stuff in the config template.
            config_template_file (string): filename of the config template file.
            webapp (string): The name of the webapp to build.
        '''
                   
        # upload the data sources file to the project
        destination = unix_path_join(self.oba_base_folder,
                                     webapp,
                                     'src',
                                     'main',
                                     'resources')
        self.populate_and_upload_template_file(data_dict,
                                               conf_helper,
                                               config_template_file,
                                               destination,
                                               out_filename='data-sources.xml')

        # build the project using maven
        with cd(self.oba_base_folder):
            run('/usr/local/maven/bin/mvn -am -pl {0} package'.format(webapp))

    def make_params_from_datasource_file(self, filename):
        '''Helper to make config for a filename.
        '''

        template_filename = os.path.join(CONFIG_TEMPLATE_DIR, filename)
        return self.oba_conf.make_params_for_template(template_filename)
        
    def install_api_webapp(self):
        '''Installs the api-webapp.
        '''
        
        if self.oba_conf.get('allow_api_test_key').lower() == 'true':
            api_test_xml = '<bean class="org.onebusaway.users.impl.CreateApiKeyAction"><property name="key" value="TEST"/></bean>'
        else:
            api_test_xml = ''
        
        api_config = self.make_params_from_datasource_file('api-webapp-data-sources.xml')

        api_config['api_testing'] = api_test_xml
        api_config['elastic_ip'] = self.aws_conf.get('elastic_ip')
        
        self.build_webapp(api_config, 
                          'api-webapp-data-sources.xml',
                          'onebusaway-api-webapp')
        
    def install_federation_webapp(self):
        '''Installs the transit-data-federation-webapp.
        '''

        transit_fed_config = self.make_params_from_datasource_file('transit-data-federation-webapp-data-sources.xml')
        
        transit_fed_config['data_bundle_path'] = unix_path_join('/home', self.user, 'data', 'bundle')
        for k in ['gtfs_rt_trip_updates_url', 'gtfs_rt_vehicle_positions_url', 'gtfs_rt_service_alerts_url']:
            transit_fed_config[k] = self.gtfs_conf.get(k)
        
        self.build_webapp(transit_fed_config, 
                          'transit-data-federation-webapp-data-sources.xml',
                          'onebusaway-transit-data-federation-webapp')
        
    def install_sms_webapp(self):
        '''Installs the sms-webapp.
        '''

        sms_config = self.make_params_from_datasource_file('sms-webapp-data-sources.xml')
        
        self.build_webapp(sms_config,
                          'sms-webapp-data-sources.xml',
                          'onebusaway-sms-webapp')
        
    def install_webapp(self):
        '''Installs the webapp.
        '''

        webapp_config = self.make_params_from_datasource_file('webapp-data-sources.xml')
        webapp_config['elastic_ip'] = self.aws_conf.get('elastic_ip')
        
        self.build_webapp(webapp_config, 
                          'webapp-data-sources.xml',
                          'onebusaway-webapp')
        
    def deploy_all(self):
        '''Deploys each webapp (copies to tomcat webapps).
        '''
        
        # copy the war files to tomcat for each webapp
        tomcat_webapp_dir = unix_path_join('/home',
                                           self.user,
                                           'tomcat',
                                           'webapps')
        for webapp in ['onebusaway-transit-data-federation-webapp',
                       'onebusaway-api-webapp',
                       'onebusaway-sms-webapp',
                       'onebusaway-webapp']:
            run('cp {0} {1}'.format(unix_path_join('/home',
                                                   self.user,
                                                   self.oba_base_folder,
                                                   webapp,
                                                   'target',
                                                   webapp + '.war'),
                                    tomcat_webapp_dir))
            
    def start_servers(self):
        '''Starts tomcat and xwiki servers.
        '''
        
        # start servers
        run('set -m; /home/{0}/tomcat/bin/startup.sh'.format(self.user))
        # writing output to /dev/null because logs are already written to /usr/local/xwiki/data/logs
        sudo('set -m; sudo nohup /usr/local/xwiki/start_xwiki.sh -p 8081 > /dev/null &')
        
    def stop_servers(self):
        '''Stops tomcat and xwiki servers.
        '''
        
        # stop servers immediately
        run('set -m; /home/{0}/tomcat/bin/shutdown.sh'.format(self.user))
        sudo('set -m; /usr/local/xwiki/stop_xwiki.sh -p 8081')
        
    def install_watchdog(self):
        '''Configures and uploads watchdog script.  Adds cron task to run it.
        '''
        
        # ensure watchdog .py file is in config directory
        oba_script_file = os.path.join(CONFIG_DIR, 'check_oba.py')
        if not os.path.exists(oba_script_file):
            print('Watchdog python script does not exist in config directory.')
            print('Please create it and set the appropriate location of the watchdog.ini file.')
            return
        
        # ensure script and config folder exists
        if not exists(self.config_dir):
            run('mkdir {0}'.format(self.config_dir))
            
        if not exists(self.script_dir):
            run('mkdir {0}'.format(self.script_dir))
            
        # upload watchdog script (remove it if needed)
        remote_script_file = unix_path_join(self.script_dir, 'check_oba.py')
        if exists(remote_script_file):
            sudo('rm -rf {0}'.format(remote_script_file))
            
        put(oba_script_file, self.script_dir)
        
        # upload watchdog config (remove it if needed)
        remote_config_file = unix_path_join(self.config_dir, 'watchdog.ini')
        if exists(remote_config_file):
            sudo('rm -rf {0}'.format(remote_config_file))
            
        put(os.path.join(CONFIG_DIR, 'watchdog.ini'), self.config_dir)
        
        # update/insert cron to run script
        with open(os.path.join(CONFIG_TEMPLATE_DIR, 'watchdog_crontab')) as f:
            refresh_cron_template = f.read()
            
        cron_settings = dict(cron_email=self.aws_conf.get('cron_email'),
                             watchdog_script=remote_script_file)
        cron = refresh_cron_template.format(**cron_settings)
            
        crontab_update(cron, 'watchdog_cron')        
                    

def get_new_install_fab(instance_dns_name):
    '''Helper method to get a new ObaInstallFab instance.
    '''

    if not instance_dns_name:
        instance_dns_name = input('Enter EC2 public dns name: ')

    return ObaInstallFab(instance_dns_name,
                         conf_helper.get_config('aws'),
                         conf_helper.get_config('gtfs'),
                         conf_helper.get_config('oba'))


def install(instance_dns_name=None):
    '''Installs OBA on the EC2 instance.
    
    Args:
        instance_dns_name (string, default=None): The EC2 instance to deploy to.
    '''
    
    oba_fab = get_new_install_fab(instance_dns_name)
    oba_fab.clone_repo()
    oba_fab.install_federation_webapp()
    oba_fab.install_api_webapp()
    oba_fab.install_sms_webapp()
    oba_fab.install_webapp()
    oba_fab.install_watchdog()
    oba_fab.deploy_all()


def start(instance_dns_name=None):
    '''Start the OBA server on the EC2 instance.

    Args:
        instance_dns_name (string, default=None): The EC2 instance to deploy to.
    '''

    oba_fab = get_new_install_fab(instance_dns_name)
    oba_fab.start_servers()


def install_and_start_watchdog(instance_dns_name=None):
    '''Installs OBA on the EC2 instance.

    Args:
        instance_dns_name (string, default=None): The EC2 instance to deploy to.
    '''

    # ensure watchdog config exists by fetching it
    conf_helper.get_config('watchdog')

    oba_fab = get_new_install_fab(instance_dns_name)
    oba_fab.install_watchdog()
