# OneBusAway-RVTD Deployer

Script(s) to deploy and manage OneBusAway on Amazon EC2

## Table of Contents

* [Installation](#installation)
* [EC2 Setup](#ec2-setup)
* [Config Files](#config-files)
    * [aws.ini](#awsini)
    * [gtfs.ini](#gtfsini)
    * [oba.ini](#obaini)
* [Running Scripts](#running-scripts)
* [Watchdog Setup](#watchdog-setup)
* [OneBusAway Setup](#onebusaway-setup)
* [xWiki Setup](#xwiki-setup)
* [EC2 Instance Notes](#ec2-instance-notes)

## Installation

The project is based of off python 2.7, but is best used with the `virtualenv` development scheme.

1. Install Python 2.7
2. Install virtualenv: `$ [sudo] pip install virtualenv`
3. Clone the github project: `$ git clone https://github.com/trilliumtransit/oba_rvtd_deployer.git`
4. Instantiate the virtual python environment for the project using python 2.7: 
  - Windows: `virtualenv --python=C:\Python27\python.exe oba_rvtd_deployer`
  - Linux: `virtualenv -p /path/to/python27 oba_rvtd_deployer`
5. Browse to project folder `cd oba_rvtd_deployer`
6. Activate the virtualenv: 
  - Windows: `.\Scripts\activate`
  - Linux: `bin/activate`
7. (Windows only) Manually install the `pycrypto` library.  The followin command assumes you have 32 bit python 2.7 installed: `pip install http://www.voidspace.org.uk/python/pycrypto-2.6.1/pycrypto-2.6.1-cp27-none-win32.whl`  If 64 bit python 2.7 is installed, run the following command instaed:  `pip install http://www.voidspace.org.uk/python/pycrypto-2.6.1/pycrypto-2.6.1-cp27-none-win_amd64.whl`
8. Install the python project using develop mode: `python setup.py develop`

## EC2 Setup

You will need to do the following for automatically launching Amazon EC2 instances using the scripts:

- Create AWS account
 - Get the access key
 - Get the secret access key
- Create security group
 - Add your IP to list of allowed inbound traffic [(see aws docs)](http://docs.aws.amazon.com/AWSEC2/latest/UserGuide/authorizing-access-to-an-instance.html).
- Create key pair [(see aws docs)](http://docs.aws.amazon.com/AWSEC2/latest/UserGuide/ec2-key-pairs.html).
 - Download .pem file to computer
- (Windows only) instally PuTTY and PuTTYgen
 - [Download from here](http://www.chiark.greenend.org.uk/~sgtatham/putty/download.html).
 - Create .ppk file [(see aws docs)](http://docs.aws.amazon.com/AWSEC2/latest/UserGuide/putty.html).

## Config Files

You'll need to create a bunch of config files before running the deployment scripts.  Run the script `setup_config` to be prompted for each setting, or create a new folder called `config` and add the files manually.  All config files are .ini files and have a single section called 'DEFAULT'.

### aws.ini

| Setting Name | Description |
| --- | --- |
| ami_id | The base ami to start from.  Use Amazon Linux and find the appropriate AMI ID depending on your AWS region. |
| aws_access_key_id | Access key for account. |
| aws_secret_access_key | Secret access key for account. |
| block_device_map | Where to attach storage to EC2 unit.  Use `/dev/xvda` for Amazon Linux. |
| cron_email | An email address to send cron errors to. |
| delete_volumes_on_tear_down | When tearing down instance, also delete volumes.  If using CentOS, you should set this to `true`.  Defaults to `false`. |
| elastic_ip | The AWS elastic ip for the onebusaway-webapp to refenece when making xwiki calls.  Note that you'll still need to manually associate an elastic IP in the AWS console. |
| key_filename | The filename of your .pem file. |
| key_pair_name | The key pair name for the EC2 instance to use. |
| instance_name | The name to tag the instance with. |
| instance_type | The EC2 instance type.  [(See instance types)](http://aws.amazon.com/ec2/pricing/).  It is recommended to use at least `t2.medium`. |
| region | The AWS region to connect to. |
| security_groups | Security groups to grant to the instance.  If more than one, seperate with commas. |
| timezone | The linux timezone to set the machine to.  Use a path on the machine such as `/usr/share/zoneinfo/America/Los_Angeles`. |
| user | The user to login as when connecting via ssh.  Use `ec2-user` with Amazon Linux. |
| volume_size | Size of the AWS Volume for the new instance in GB.  It is recommended to use at least `12`. |

### gtfs.ini

| Setting Name | Description |
| --- | --- |
| gtfs_static_url | The url where the gtfs static file can be found. |
| gtfs_rt_trip_updates_url | The url for the gtfs-rt trip updates. |
| gtfs_rt_service_alerts_url | The url for the gtfs-rt service alerts. |
| gtfs_rt_vehicle_positions_url | The url for the gtfs-rt vehicle positions. |
| extra_bundle_build_args | Extra arguments to provide when building a bundle.  Example: `-P tripEntriesFactory.throwExceptionOnInvalidStopToShapeMappingException=false` |

### oba.ini

| Setting Name | Description |
| --- | --- |
| allow_api_test_key | Whether or not to set a test key for the api-webapp.  Set to `true` if desired. |
| oba_base_folder | OneBusAway based folder.  Recommended value: `onebusaway-application-modules`. |
| oba_git_branch | OneBusAway git branch to checkout.  Example: `1.1.12`. |
| oba_git_repo | OneBusAway git repo to checkout from.  Example:  `https://github.com/OneBusAway/onebusaway-application-modules.git`. |
| pg_username | The user that OneBusAway will use when connecting to postgresql. |
| pg_password | The password that OneBusAway will use when connecting to postgresql. |
| pg_role | Role to assign the OneBusAway user during db setup. |
| geocode_center_lat  | Center latitude to use for OBA instance. |
| geocode_center_lon  | Center longitude to use for OBA instance. |
| geocode_center_city  | Center city to use for OBA instance. |
| geocode_center_state  | Center state to use for OBA instance. |
| geocode_center_zip  | Center zip code to use for OBA instance. |
| service_area_bounds_min_lat  | Service area boundary for OBA instance. |
| service_area_bounds_min_lon  | .. |
| service_area_bounds_max_lat  | .. |
| service_area_bounds_max_lon  | .. |

## Running Scripts

If using linux, the executable files to run scripts will be in the `bin` folder instead of `Scripts`.  In the remainder of the docs, whenever it says "run script `script_name`", you'll run the script by doing `bin/script_name` or `.\Scripts\script_name` on linux and windows respectively.

| Script Name | Description |
| --- | --- |
| clean_config | Deletes the "config" folder. |
| setup_config | Helper script to create configuration files for AWS, OneBusAway and updating and validating GTFS. |
| prepare_new_oba_ec2 | Launches a new Amazon EC2 instance and installs the essential software to run OneBusAway. |
| install_oba | Installs OneBusAway on server by building webapps with maven. |
| validate_gtfs | Downloads and validates the static GTFS. |
| update_gtfs | Creates a new data bundle for OneBusAway on the EC2 instance. Validate the GTFS if no GTFS file found. |
| start_oba | Starts Tomcat and xWiki Servers. |
| install_and_start_watchdog | Installs and starts watchdog on the EC2 instance. |
| deploy_new_oba | Combines following scripts in order: `prepare_new_oba_ec2`, `install_oba`, `update_gtfs`, `start_oba`, `install_and_start_watchdog`.  Be sure to manually setup OneBusAway and xWiki after the server is ready. |

## Watchdog Setup

Just before the master deployment script finishes, it will install OneBusAway Watchdog on the instance.  If you haven't configured the watchdog.ini file, the script will help you build the config file.  Also, you'll need to copy over the check_oba.py script to the config folder and change the path to the watchdog config file on the instance.  Usually this should be `/home/ec2-user/config/watchdog.ini`.  To see a full list of config params, see [this list](https://github.com/djstroky/onebusaway-watchdog-rvtd#setup).

## OneBusAway Setup

After installing OneBusAway, the webapp will need to be configured manually.  Get the public dns name of the instance and add to the url so you get `ec2-###-###-###-###.us-west-2.compute.amazonaws.com:8080/onebusaway-webapp`.  Upon starting, you'll be prompted to add an admin account.

## xWiki Setup

After installing and starting xWiki for the first time, it will be blank.  It is best to import a backup to have all needed pages.  Follow these steps to import the backup:

1.  Download a backup from [here](https://drive.google.com/file/d/0B1ueEUCcTtKoYjF0X2g3S05nOXM/view?usp=sharing).
2.  Remote onto machine.
3.  Stop xWiki server using command `sudo /usr/local/xwiki/stop_xwiki.sh -p 8081`.
4.  Edit the file `/usr/local/xwiki/webapps/xwiki/WEB-INF/xwiki.cfg`.
5.  Uncomment the line `xwiki.superadminpassword=PASSWORD`.
6.  Start xWiki server using command `sudo nohup /usr/local/xwiki/start_xwiki.sh -p 8081 > /dev/null &`.
7.  Open browser and go to `ec2-###-###-###-###.us-west-2.compute.amazonaws.com:8081`.
8.  Login using username `superadmin` and the password you defined.
9.  Browse to import tool.  Click on `Home` > `Administer Wiki`.   Then click `Content`.  Then click `Import`.
10.  Upload file (the backup file you downloaded in step 1).
11.  Select the file and select option `Replace the document history with the history from the package`.  Then click `Import`.
12.  Stop xWiki server using command `sudo /usr/local/xwiki/stop_xwiki.sh -p 8081`.
13.  Edit the file `/usr/local/xwiki/webapps/xwiki/WEB-INF/xwiki.cfg` and comment out the superadmin line.
14.  Start xWiki server using command `sudo nohup /usr/local/xwiki/start_xwiki.sh -p 8081 > /dev/null &`.

## EC2 Instance Notes

Here is a complete list of stuff that this script install/does on the instance:

* Launches a new EC2 instance
* Disables IPV6.
* Installs Postgresql.
* Updates system using `yum update`.
* Changes the timezone of the machine.
* Installs [AWS Cloudwatch Monitoring Scripts](http://docs.aws.amazon.com/AmazonCloudWatch/latest/DeveloperGuide/mon-scripts-perl.html). (starts via cron)
* Installs git
* Installs java-1.7.0-openjdk and java-1.7.0-openjdk-devel
* Installs maven (to /usr/local/)
* Installs tomcat
  - to /home/{user}/tomcat/
  - Adds a startup script to start tomcat on reboot
* Installs xWiki
  - to /usr/local/xwiki
  - Adds a startup script to start xwiki on reboot
  - This process downloads a 700mb package, so it may take a while.
* Clones [onebusaway-application-modules](https://github.com/OneBusAway/onebusaway-application-modules) repo as specified in config.
* Builds the following webapps from source using maven:
  - onebusaway-transit-data-federation-webapp
  - onebusaway-api-webapp
  - onebusaway-webapp
  - onebusaway-sms-webapp
* Builds a bundle.
* Sets a cron to automatically update the bundle and restart Tomcat nightly at 3am server time.
* Copies compiled .war files for each of the webapps into Tomcat for it to run.  
* Starts tomcat
* Starts xWiki
* Installs [onebusaway-watchdog-rvtd](https://github.com/djstroky/onebusaway-watchdog-rvtd) (runs via cron)
