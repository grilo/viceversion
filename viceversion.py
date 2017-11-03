#!/usr/bin/env python

import logging
import argparse
import os
import subprocess
import shlex
import json
import urlparse
import plistlib
import re


def shell_command(command):
    logging.debug("Running command: %s", command)

    p = subprocess.Popen(shlex.split(command),
                         stdout=subprocess.PIPE,
                         stderr=subprocess.PIPE)
    out, err = p.communicate()
    if p.returncode != 0:
        logging.debug("Unable to execute (rc: %i): %s", p.returncode, command)
        return
    return out


def find_files(directory, pattern):
    regex = re.compile(pattern)
    found = []
    for root, dirs, files in os.walk(directory):
        for f in files:
            path = os.path.join(root, f)
            if regex.match(path):
                found.append(path)
    return found


def maven(directory):
    pom = find_files(directory, '.*pom.xml$')[0]
    cmd = "mvn -f %s org.apache.maven.plugins:maven-help-plugin:2.1.1:evaluate  -Dexpression=project.version" % (pom)
    out = shell_command(cmd)
    for line in out.splitlines():
        if line.startswith('['):
            pass
        return line


def setup_py(directory):
    setuppy = find_files(directory, '.*setup.py$')[0]
    cmd = "python '%s' --version" % (setuppy)
    return shell_command(cmd)


def package_json(directory):
    setuppy = find_files(directory, '.*package.json$')[0]
    contents = json.loads(open(filepath, 'r').read())
    return contents['version']


def build_gradle(directory):
    task_path = os.path.join(directory, 'viceversion.task')
    gradlew = os.path.join(directory, 'gradlew')
    if not 'ANDROID_HOME' in os.environ:
        logging.warning("ANDROID_HOME is not set, android detection WILL fail.")

    task = """
        allprojects {
            task printViceVersion {
                doLast {
                    if (project.hasProperty('android') && project.android.defaultConfig.versionCode != null) {
                        println project.name + ":" + project.android.defaultConfig.versionCode + "-" + project.android.defaultConfig.versionName
                    } else if (project.version != 'unspecified') {
                        println project.name + ":" + project.version
                    }
                }
            }
        }
    """

    t = open(task_path, 'w')
    t.write(task)
    t.close()
    logging.info("Wrote: %s", task_path)

    cmd = "gradle"
    if os.path.isfile(gradlew):
        cmd = os.path.join('.', gradlew)
    cmd += ' -b "%s"' % (find_files(directory, '.*build.gradle$')[0])
    cmd += ' -q -I "%s"' "printViceVersion" % (task_path)

    if 'http_proxy' in os.environ:
        result = urlparse.urlparse(os.environ['http_proxy'])
        host, port = result.netloc.split(':')
        cmd += " -Dhttp.proxyHost=%s" % (host)
        cmd += " -Dhttp.proxyPort=%s" % (port)
        cmd += " -DsystemProp.http.proxyHost=%s" % (host)
        cmd += " -DsystemProp.http.proxyPort=%s" % (port)
    if 'https_proxy' in os.environ:
        result = urlparse.urlparse(os.environ['https_proxy'])
        host, port = result.netloc.split(':')
        cmd += " -Dhttps.proxyHost=%s" % (host)
        cmd += " -Dhttps.proxyPort=%s" % (port)
        cmd += " -DsystemProp.https.proxyHost=%s" % (host)
        cmd += " -DsystemProp.https.proxyPort=%s" % (port)

    out = shell_command(cmd)
    if not out:
        logging.error("Unable to run ./gradlew, attempting gradle from $PATH.")
        cmd = cmd.replace(gradlew, 'gradle')
    out = shell_command(cmd)
    out = out.splitlines()
    if len(out) > 1:
        logging.warning("Several versions found...")
    elif len(out) < 1:
        logging.critical("No versions found...")
        return None
    logging.info("Found version: %s", out[0])
    version = out[0].split(':')[1]
    os.unlink(task_path)
    return version


def info_plist(directory):
    plist_files = find_files(directory, '.*Info.plist$')
    short = None
    version = None
    for f in plist_files:
        try:
            pl = plistlib.readPlist(f)
        except:
            logging.warning("Invalid Info.plist file.")
            continue
        s, v = pl['CFBundleShortVersionString'], pl['CFBundleVersion']
        if not short:
            short, version = s, v
        elif short == '1.0':
            short, version = s, v
    if version:
        return short + '-' + version
    return short

def best_match(build_files):
    if len(build_files) == 0:
        raise IOError("No build files found.")
    elif len(build_files) == 1:
        return build_files[0]
    # If multiple are found, return the latest modified file
    mod_time = {}
    for f in build_files:
        mtime = os.path.getmtime(f)
        mod_time[mtime] = f
    return sorted(mod_time.iterkeys())[0]


def get_driver(directory):
    drivers = {
        'pom.xml': maven,
        'setup.py': setup_py,
        'package.json': package_json,
        'build.gradle': build_gradle,
        'Info.plist': info_plist,
    }

    for f in find_files(directory, '.*'):
        basename = os.path.basename(f)
        if not basename in drivers:
            continue
        logging.debug("Found driver (%s) for file: %s", drivers[basename].__name__, f)
        return drivers[basename]

def get_version(directory):
    logging.debug("Looking for build files in: %s", directory)
    driver = get_driver(directory)
    version = driver(directory)
    logging.info("Version: %s", version)
    return version


if __name__ == '__main__':

    desc = 'Generate a shell script that runs a build.'
    parser = argparse.ArgumentParser(description=desc)

    parser.add_argument("-v", "--verbose", action="store_true",
                        help="Increase output verbosity")
    parser.add_argument("-d", "--directory", default=os.getcwd(),
                        help="The directory to look for a build file.")

    args = parser.parse_args()

    logging.basicConfig(format='%(asctime)s::%(levelname)s::%(message)s')
    logging.getLogger().setLevel(getattr(logging, 'INFO'))

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    print get_version(args.directory)
