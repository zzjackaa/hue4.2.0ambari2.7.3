#!/usr/bin/env python
import sys, os, pwd, grp, signal, time
from resource_management import *
from resource_management.core.exceptions import Fail
from resource_management.core.logger import Logger
from resource_management.core.resources.system import Execute, Directory, File
from resource_management.core.shell import call
from resource_management.core.system import System
from resource_management.libraries.functions.default import default

def setup_user():
  """
  Creates Hue user home directory and sets up the correct ownership.
  """
  __create_hue_user()
  __set_home_dir_ownership()

def __create_hue_user():
  import params
  try:
    grp.getgrnam(params.hue_group)
  except KeyError:
    Logger.info(format("Creating group '{params.hue_group}' for Hue Service"))
    Group(
      group_name = params.hue_group,
      ignore_failures = True
    )
  try:
    pwd.getpwnam(params.hue_user)
  except KeyError:
    Logger.info(format("Creating user '{params.hue_user}' for Hue Service"))
    User(
      username = params.hue_user,
      groups = [params.hue_group],
      ignore_failures = True
    )

def __set_home_dir_ownership():
  import params
  """
  Updates the Hue user home directory to be owned by hue:hue.
  """
  if not os.path.exists("/home/{0}".format(params.hue_user)):
    Directory(params.hue_local_home_dir,
            mode=0700,
            cd_access='a',
            owner=params.hue_user,
            group=params.hue_group,
            create_parents=True
    )

def explain(repo_file):
  groups_dict={}
  with open (repo_file,"rb") as f:
    for line in f:
      if line.startswith("#") or line.startswith(";") or len(line.strip()) == 0:
        continue
      if line.strip().find('[') == 0 and line.strip().find(']') == len(line.strip()) - 1:
        key = line.strip().lstrip('[').rstrip(']')
        groups_dict[key] = []
      else:
        if line.strip().find('baseurl') != -1:
          groups_dict[key].append(line.strip().split('=')[1])
  return groups_dict

def download_hue():
  import params
  """
  Download Hue to the installation directory
  """
  try:
    Execute('docker stop hue2')
    Execute('docker rm hue2') 
    Execute('docker rmi hue4.2-kyv4:v1')
    Execute('rm -rf /usr/local/hue')
    Execute('rm -rf /usr/hdp/current/hue-server')
    Execute('rm -rf /usr/local/HUE.tar')
    Execute('rm -rf /usr/local/my_hue.tar')
  except Exception as e:
    pass
  Download_url="".join(explain('/etc/yum.repos.d/hdp.repo')['HDP-3.1'])+'/my_hue.tar'
  Execute('wget -P /usr/local {0}'.format(Download_url))
  Download_zip="".join(explain('/etc/yum.repos.d/hdp.repo')['HDP-3.1'])+'/HUE.tar'
  Execute('wget -P /usr/local {0}'.format(Download_zip))
  Execute('tar -xvf /usr/local/HUE.tar -C /usr/local')
  #Execute('{0} | xargs wget -O hue.tgz'.format(params.download_url))
  Execute('/usr/bin/docker load -i /usr/local/my_hue.tar && sleep 5')
  Execute('/usr/bin/docker run -td -u root --name hue2 --net=host -v /etc/hosts:/etc/hosts -v /usr/local/hue:/usr/local/hue -v /usr/hdp:/usr/hdp -v /etc/passwd:/etc/passwd -v /etc/shadow:/etc/shadow  -v /etc/hive:/etc/hive --restart=always --privileged hue4.2-kyv4:v1 /bin/bash')
  Execute('/usr/bin/docker exec -u root hue2 /bin/bash -c \'mkdir /var/log/hue && chmod 777 /tmp \'')
  Execute('/usr/bin/docker exec -u root hue2 /bin/bash -c \'touch /var/log/hue/{access.log,runcpserver.log,supervisor.log,error.log,kt_renewer.log} && chmod -R 777 /var/log\'')
  #Execute('tar -zxvf /data/hue.tgz -C {0} && rm -f /data/hue.tgz'.format(params.hue_install_dir))

  #Execute('mkdir -p {0}'.format(params.hue_dir))
  # Ensure all Hue files owned by hue
  
  Execute('chown -R {0}:{1} {2}'.format(params.hue_user,params.hue_group,params.hue_dir))
  Execute('ln -s {0} /usr/hdp/current/hue-server'.format(params.hue_dir))
  #Execute('rm -rf {0}/*'.format(params.hue_dir))
  #Execute('cd /usr/local/hue-4.2.0 && make apps')
  Logger.info("Hue Service is installed")

def add_hdfs_configuration(if_ranger=False, security_enabled=False):
  import params
  services_configurations = {}
  services_configurations['core-site'] = {}
  services_configurations['core-site']['hadoop.proxyuser.hue.groups'] = '*'
  services_configurations['core-site']['hadoop.proxyuser.hue.hosts'] = '*'
  services_configurations['hdfs-site'] = {}
  services_configurations['hdfs-site']['dfs.namenode.acls.enabled'] = 'true'
  if params.hue_hbase_module_enabled == 'Yes':
    services_configurations['core-site']['hadoop.proxyuser.hbase.groups'] = '*'
    services_configurations['core-site']['hadoop.proxyuser.hbase.hosts'] = '*'
  if params.hue_hive_module_enabled == 'Yes':
    services_configurations['core-site']['hadoop.proxyuser.hive.groups'] = '*'
    services_configurations['core-site']['hadoop.proxyuser.hive.hosts'] = '*'
  if params.hue_spark_module_enabled == 'Yes':
    services_configurations['core-site']['hadoop.proxyuser.spark.groups'] = '*'
    services_configurations['core-site']['hadoop.proxyuser.spark.hosts'] = '*'
  if params.hue_oozie_module_enabled == 'Yes':
    services_configurations['core-site']['hadoop.proxyuser.oozie.groups'] = '*'
    services_configurations['core-site']['hadoop.proxyuser.oozie.hosts'] = '*'
  if params.dfs_ha_enabled:
    services_configurations['core-site']['hadoop.proxyuser.httpfs.groups'] = '*'
    services_configurations['core-site']['hadoop.proxyuser.httpfs.hosts'] = '*'
    #services_configurations['httpfs-site'] = {}
    #services_configurations['httpfs-site']['httpfs.proxyuser.hue.groups'] = '*'
    #services_configurations['httpfs-site']['httpfs.proxyuser.hue.hosts'] = '*'
  if security_enabled:
    services_configurations['core-site']['hadoop.proxyuser.HTTP.groups'] = '*'
    services_configurations['core-site']['hadoop.proxyuser.HTTP.hosts'] = '*'
    services_configurations['core-site']['hue.kerberos.principal.shortname'] = 'hue'
  add_configurations(services_configurations)

def add_hbase_configuration(if_ranger=False, security_enabled=False):
  import params
  services_configurations = {}
  services_configurations['hbase-site'] = {}
  if if_ranger:
    services_configurations['hbase-site']['hbase.regionserver.thrift.http'] = 'true'
    services_configurations['hbase-site']['hbase.thrift.support.proxyuser'] = 'true'
  if security_enabled:
    services_configurations['hbase-site']['hbase.thrift.security.qop'] = 'auth'
    services_configurations['hbase-site']['hbase.thrift.support.proxyuser'] = 'true'
    services_configurations['hbase-site']['hbase.regionserver.thrift.http'] = 'true'
    services_configurations['hbase-site']['hbase.thrift.kerberos.principal'] = params.HTTP_principal
    services_configurations['hbase-site']['hbase.thrift.keytab.file'] = params.HTTP_keytab
    services_configurations['hbase-site']['hbase.rpc.engine'] = 'org.apache.hadoop.hbase.ipc.SecureRpcEngine'
  add_configurations(services_configurations)

def add_hive_configuration(if_ranger=False, security_enabled=False):
  services_configurations = {}
  services_configurations['hive-site'] = {}
  services_configurations['hive-site']['hive.security.authorization.sqlstd.confwhitelist.append'] = 'hive.server2.logging.operation.verbose'
  services_configurations['webhcat-site'] = {}
  services_configurations['webhcat-site']['webhcat.proxyuser.hue.groups'] = '*'
  services_configurations['webhcat-site']['webhcat.proxyuser.hue.hosts'] = '*' 	
  if if_ranger:
    services_configurations['hive-site']['hive.server2.enable.impersonation'] = 'true'
  add_configurations(services_configurations)

def add_oozie_configuration(if_ranger=False, security_enabled=False):
  services_configurations = {}
  services_configurations['oozie-site'] = {}
  services_configurations['oozie-site']['oozie.service.ProxyUserService.proxyuser.hue.groups'] = '*'
  services_configurations['oozie-site']['oozie.service.ProxyUserService.proxyuser.hue.hosts'] = '*'
  add_configurations(services_configurations)

def add_spark_configuration(if_ranger=False, security_enabled=False):
  services_configurations = {}
  services_configurations['livy-conf'] = {}
  services_configurations['livy-conf']['livy.server.csrf_protection.enabled'] = 'false'
  add_configurations(services_configurations)

def add_configurations(services_configurations):
  """
  Run the script file to add configurations
  #/var/lib/ambari-server/resources/scripts/configs.sh set ambari-server-host \
   cluster_name core-site "hadoop.proxyuser.hbase.hosts" "*"

  services_configurations:{'configuration file1':{'key1':'value1','key2':'value2',...},
                           'configuration file2':{'key1':'value1','key2':'value2',...}
                           ...}
  """
  import params
  if isinstance(services_configurations, dict):
    for i in range(len(services_configurations)):
      key1 = services_configurations.keys()[i]
      value1 = services_configurations[key1]
      if isinstance(value1, dict):
        for j in range(len(value1)):
          key2 = value1.keys()[j]
          value2 = value1[key2]
          cmd = format(params.service_packagedir + "/files/configs.sh set " + params.ambari_server_hostname + " " + params.cluster_name + " " + key1 + " '" + key2 + "' '"+ value2 + "'")
          Execute(cmd)

  
