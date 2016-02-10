try:
    input = raw_input
except NameError: 
    pass
import os

from deploy_utils.config import ConfigHelper
from deploy_utils.ec2 import launch_new_ec2
from fabric.api import run, sudo, cd, put
from fabric.context_managers import settings

from oba_deployer import CONFIG_DIR, CONFIG_TEMPLATE_DIR
from oba_deployer.oba import OBAFab


conf_helper = ConfigHelper(CONFIG_DIR, CONFIG_TEMPLATE_DIR)


class AwsFab(OBAFab):
    
    def install_tomcat(self):
        '''Configures Tomcat on EC2 instance.
        
        Unlinke other items, this is placed in /home/{user} directory,
        so that it can be restarted with cron to refresh gtfs updates.
        '''
        
        # get tomcat from direct download
        run('wget http://www.eu.apache.org/dist/tomcat/tomcat-7/v7.0.67/bin/apache-tomcat-7.0.67.tar.gz')
        
        # move to a local area for better organization
        run('tar xzf apache-tomcat-7.0.67.tar.gz')
        run('rm -rf apache-tomcat-7.0.67.tar.gz')
        run('mv apache-tomcat-7.0.67 tomcat')
                    
        # add logging rotation for catalina.out
        self.populate_and_upload_template_file(dict(user=self.user),
                                               conf_helper,
                                               'tomcat_catalina_out',
                                               '/etc/logrotate.d',
                                               True)
        
        # add init.d script
        self.populate_and_upload_template_file(dict(user=self.user),
                                               conf_helper,
                                               'tomcat_init.d',
                                               '/etc/init.d',
                                               True)
        with cd('/etc/init.d'):
            sudo('mv tomcat_init.d tomcat')
            sudo('chmod 755 tomcat')
            sudo('chown root tomcat')
            sudo('chgrp root tomcat')
            sudo('chkconfig --add tomcat')
            
    def install_xwiki(self):
        
        run('wget http://download.forge.ow2.org/xwiki/xwiki-enterprise-jetty-hsqldb-7.3.zip')
        
        # move to a local area for better organization
        sudo('unzip xwiki-enterprise-jetty-hsqldb-7.3.zip -d /usr/local')
        run('rm xwiki-enterprise-jetty-hsqldb-7.3.zip')
        
        with cd('/usr/local'):
            sudo('ln -s xwiki-enterprise-jetty-hsqldb-7.3 xwiki')
            
        # add init.d script
        put(os.path.join(CONFIG_TEMPLATE_DIR, 'xwiki_init.d'), '/etc/init.d', True)
        with cd('/etc/init.d'):
            sudo('mv xwiki_init.d xwiki')
            sudo('chmod 755 xwiki')
            sudo('chown root xwiki')
            sudo('chgrp root xwiki')
            sudo('chkconfig --add xwiki')

    def turn_off_ipv6(self):
        '''Edits the networking settings to turn off ipv6.

        Credit to CDSU user on http://blog.acsystem.sk/linux/rhel-6-centos-6-disabling-ipv6-in-system
        '''

        # unfortunately, this requires sudo access
        with settings(warn_only=True):
            sudo('echo "net.ipv6.conf.default.disable_ipv6=1" >> /etc/sysctl.conf')
            sudo('echo "net.ipv6.conf.all.disable_ipv6 = 1" >> /etc/sysctl.conf')
            sudo('sysctl -p')


def prepare_new():
    '''Launch a new EC2 instance and install OBA requirements
    '''

    # connect to AWS and launch new instance
    aws_conf = conf_helper.get_config('aws')
    oba_conf = conf_helper.get_config('oba')
    instance = launch_new_ec2(aws_conf)

    # Now that the status is running, it's not yet launched.
    # The only way to tell if it's fully up is to try to SSH in.
    aws_system = AwsFab(instance.public_dns_name, aws_conf)

    # If we've reached this point, the instance is up and running.
    print('SSH working')
    aws_system.update_system()
    aws_system.set_timezone(aws_conf.get('timezone'))
    aws_system.install_custom_monitoring()
    aws_system.turn_off_ipv6()
    aws_system.install_git()
    aws_system.install_jdk()
    aws_system.install_maven()
    aws_system.install_tomcat()
    aws_system.install_xwiki()

    # install pg
    init_sql_params = dict(pg_username=oba_conf.get('pg_username'),
                           pg_password=oba_conf.get('pg_password'),
                           pg_role=oba_conf.get('pg_role'))
    init_sql_filename = 'init.sql'
    init_sql_path = os.path.join(CONFIG_DIR, init_sql_filename)
    conf_helper.write_template(init_sql_params, init_sql_filename)
    aws_system.install_pg(init_sql_path, init_sql_filename)

    return instance