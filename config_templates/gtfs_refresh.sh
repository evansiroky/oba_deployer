#!/bin/bash
#
# downloads the latest static gtfs file
# then makes OBA build a bundle using that file

{gtfs_wgets}
cd {federation_builder_folder} && java -classpath .:target/* org.onebusaway.transit_data_federation.bundle.FederatedTransitDataBundleCreatorMain {bundle_xml} {bundle_dir} {extra_args}
i=0

while netstat -tulpn 2> /dev/null | grep java
do
  /home/{user}/tomcat/bin/shutdown.sh
  sleep 5
  i=$(($i+1))
  if test $i -gt 4
  then
    echo "Failed to properly shutdown 5 times."
    echo -e "Subject: Error Restarting Tomcat\nFrom: {from_mailer}\nTo: {cron_email}\n\nI tried 5 times" | sendmail -t
    exit 1
  fi
done
/home/{user}/tomcat/bin/startup.sh
