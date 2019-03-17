try:
    input = raw_input
except NameError:
    pass

import csv
import os
import shutil

from deploy_utils.config import ConfigHelper
from deploy_utils.fab import unix_path_join

from oba_deployer import CONFIG_DIR, CONFIG_TEMPLATE_DIR, GTFS_FILES_CSV

conf_helper = ConfigHelper(CONFIG_DIR, CONFIG_TEMPLATE_DIR)

def yes_no_input(prompt):
    '''Make a prompt and checks if the answer is yes

    Returns:
        boolean: true if the answer to the prompt is yes
    '''
    return input('{0} (Y/N)? '.format(prompt)).lower() == 'y'

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

    if not os.path.exists(os.path.join(CONFIG_DIR, '{0}.ini'.format(config_type))):
        conf_helper.setup(config_type)

def setup_gtfs_bundle():
    '''Prompts user to enter the repective GTFS data including urls for static schedule data, GTFS-RT and OBA nicknames
    for each agency. Writes the bundle.xml file and a CSV file with this data.
    '''

    oba_conf = conf_helper.get_config('oba')

    while oba_conf.get('use_stop_consolidation') != 'false' and \
            not os.path.exists(os.path.join(CONFIG_DIR, 'stop-consolidation.txt')):
        input('Please create `stop-consolidation.txt` file in config dir. Press any key when done')

    if os.path.exists(os.path.join(CONFIG_DIR, 'bundle.xml')):
        return

    gtfs_bundles = []

    print('Adding bundles for various transit agencies...')
    # run a loop asking for GTFS bundles
    while True:
        bundle_name = input('Bundle name: ')
        static_url = input('static gtfs url: ')
        has_trip_updates = False
        has_vehicle_positions = False
        has_service_alerts = False
        if yes_no_input('Has trip updates GTFS-RT?'):
            has_trip_updates = True
            trip_updates_url = input('Trip updates url: ')
        if yes_no_input('Has vehicle positions GTFS-RT?'):
            has_vehicle_positions = True
            vehicle_positions_url = input('Vehicle positions url: ')
        if yes_no_input('Has service alerts GTFS-RT?'):
            has_service_alerts = True
            service_alerts_url = input('Service alerts url: ')

        # get agency mappings
        agency_mappings = []
        print('Adding agency_mapping info...')
        while True:
            agency_mappings.append({'agency_id': input('agency_id in GTFS: '), 'mapped_agency_id': input('Mapped agency ID: ') })
            if not yes_no_input('Has more agencies?'):
                break

        gtfs_bundles.append({
            'bundle_name': bundle_name,
            'static_url': static_url,
            'has_trip_updates': has_trip_updates,
            'has_vehicle_positions': has_vehicle_positions,
            'has_service_alerts': has_service_alerts,
            'trip_updates_url': trip_updates_url if has_trip_updates else '',
            'vehicle_positions_url': vehicle_positions_url if has_service_alerts else '',
            'service_alerts_url': service_alerts_url if has_service_alerts else '',
            'agency_mappings': agency_mappings,
            'mapped_agency_ids': ','.join([agency_map['mapped_agency_id'] for agency_map in agency_mappings])
        })

        if not yes_no_input('Enter another GTFS bundle?'):
            break

    # create CSV file of static gtfs feed urls
    writer = csv.DictWriter(
        open(GTFS_FILES_CSV, 'wb'),
        extrasaction='ignore',
        fieldnames=['bundle_name', 'static_url', 'trip_updates_url', 'vehicle_positions_url', 'service_alerts_url', 'mapped_agency_ids']
    )
    writer.writeheader()
    writer.writerows(gtfs_bundles)

    # create bundle.xml file
    bundle_beans_definition = '''<bean id="gtfs-bundles" class="org.onebusaway.transit_data_federation.bundle.model.GtfsBundles">
        <property name="bundles">
            <list>'''
    bundle_beans_definition += '\n'.join([
      '<ref bean="{0}" />'.format(bundle['bundle_name']) for bundle in gtfs_bundles
    ])
    bundle_beans_definition += '''</list>
        </property>
    </bean>'''

    user = conf_helper.get_config('aws').get('non_root_user')
    remote_data_dir = unix_path_join('/home', user, 'data')
    bundle_beans = []

    for bundle in gtfs_bundles:
        first_agency_id = bundle['agency_mappings'][0]['mapped_agency_id']
        bundle_beans.append('''<bean id="{0}" class="org.onebusaway.transit_data_federation.bundle.model.GtfsBundle">
            <property name="path" value="{1}" />
            <property name="defaultAgencyId" value="{2}" />
            <property name="agencyIdMappings">
            <map>
            {3}
        </map>
        </property>
        </bean>'''.format(
            bundle['bundle_name'],
            unix_path_join(remote_data_dir, '{0}-gtfs.zip'.format(bundle['bundle_name'])),
            first_agency_id,
            '\n'.join(
                ['<entry key="{0}" value="{1}" />'.format(
                    mapping['agency_id'],
                    mapping['mapped_agency_id']
                ) for mapping in bundle['agency_mappings']]
            )
        ))

    # add stop consolidation bean if needed
    if oba_conf.get('use_stop_consolidation') != 'false':
        bundle_beans.append('''<bean id="entityReplacementStrategyFactory" class="org.onebusaway.transit_data_federation.bundle.tasks.EntityReplacementStrategyFactory">
            <property name="entityMappings">
            <map>
            <entry key="org.onebusaway.gtfs.model.Stop" value="{0}" />
            </map>
            </property>
            </bean>
            <bean id="entityReplacementStrategy" factory-bean="entityReplacementStrategyFactory" factory-method="create"/>'''.format(
                unix_path_join(remote_data_dir, 'stop-consolidation.txt')
            )
        )

    # write bundle.xml file
    conf_helper.write_template(
        {
            'bundle_beans': '\n\n'.join(bundle_beans),
            'bundle_beans_definition': bundle_beans_definition
        },
        'bundle-template.xml',
        'bundle.xml'
    )


def setup_all():
    '''Calls the setup of all config Items
    '''
    setup('aws')
    setup('gtfs')
    setup('oba')
    setup_gtfs_bundle()
    setup('watchdog')