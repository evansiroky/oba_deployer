from setuptools import setup, find_packages
 
setup(
    name='oba_deployer',
    packages=find_packages(),
    install_requires=[
        'deploy_utils>=0.3.0',
        'django-fab-deploy>=0.7.5',
        'fabric>=1.10.1',
        'requests>=2.5.3',
        'transitfeed>=1.2.14'
    ],
    entry_points={
        'console_scripts': [
            # config scripts
            'clean_config=oba_deployer.config:clean',
            'setup_config=oba_deployer.config:setup_all',
            
            # aws/oba installation
            'prepare_new_oba_ec2=oba_deployer.aws:prepare_new',
            'install_oba=oba_deployer.oba:install',

            # oba/gtfs activation
            'validate_gtfs=oba_deployer.gtfs:validate_gtfs',
            'update_gtfs=oba_deployer.gtfs:update',
            'start_oba=oba_deployer.oba:start',
            'install_and_start_watchdog=oba_deployer.oba:install_and_start_watchdog',

            # one command new deployment
            'deploy_new_oba=oba_deployer.master:run_all'
        ]
    }
)
