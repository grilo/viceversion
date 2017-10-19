#!/usr/bin/env python

import logging
import argparse
import os
import subprocess
import shlex
import json


def shellcommand(command):
    logging.debug("Running command: %s", command)

    error = subprocess.PIPE
    p = subprocess.Popen(shlex.split(command), \
        stdout=subprocess.PIPE, \
        stderr=subprocess.PIPE)
    out, err = p.communicate()
    if p.returncode != 0:
        logging.debug("Unable to execute (rc: %i): %s", p.returncode, command)
        return
    return out

def maven(filepath):
    cmd = "mvn -f %s org.apache.maven.plugins:maven-help-plugin:2.1.1:evaluate  -Dexpression=project.version" % (filepath)
    out = shellcommand(cmd)
    for line in out.splitlines():
        if line.startswith('['):
            pass
        return line

def setuppy(filepath):
    cmd = "python setup.py --version"
    return shellcommand(cmd)

def packagejson(filepath):
    contents = json.loads(open(filepath, 'r').read())
    return contents['version']

def buildgradle(filepath):
    basedir = os.path.dirname(filepath)
    gradlew = os.path.join(basedir, 'gradlew')
    cmd = "gradle"
    if os.path.isfile(gradlew):
        cmd = os.path.join('.', gradlew)
    out = shellcommand(cmd + " properties")
    for line in out.splitlines():
        if line.startswith('version: '):
            return line[9:]

def plistipa(filepath):
    pass

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

def get_driver(filepath):
    drivers = {
        'pom.xml': maven,
        'setup.py': setuppy,
        'package.json': packagejson,
        'build.gradle': buildgradle,
        'Info.plist': plistipa,
    }
    f = os.path.basename(filepath)
    if f in drivers.keys():
        logging.debug("Found driver (%s) for file: %s", drivers[f].__name__, filepath)
        return drivers[f]

def get_version(directory):
    build_files = []
    logging.debug("Looking for build files in: %s", directory)
    for root, dirs, files in os.walk(directory):
        for f in files:
            path = os.path.join(root, f)
            if get_driver(path):
                build_files.append(path)
        break # Only search the root dir
    logging.debug("Found build files: %s", ','.join(build_files))
    build_file = best_match(build_files)
    logging.debug("Best match: %s", build_file)
    version = get_driver(build_file)(build_file)
    logging.debug("Version: %s", version)
    return version

if __name__ == '__main__':

    desc = 'Generate a shell script that runs a build.'
    parser = argparse.ArgumentParser(description=desc)

    parser.add_argument("-v", "--verbose", action="store_true", \
        help="Increase output verbosity")
    parser.add_argument("-d", "--directory", default=os.getcwd(), \
        help="The directory to look for a build file.")

    args = parser.parse_args()

    logging.basicConfig(format='%(asctime)s::%(levelname)s::%(message)s')
    logging.getLogger().setLevel(getattr(logging, 'INFO'))

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    print get_version(args.directory)
