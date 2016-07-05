from functools import partial
import re
import subprocess
import sys


def run_in_docker(command):
    check_output = partial(subprocess.check_output, shell=True)
    ps = check_output('docker-compose ps', shell=True).decode('utf8')
    image_name = re.search(r'\b(\w+_crawler_1)\b', ps).groups()[0]
    try:
        print(check_output(
            'docker exec -it {} {} {}'.format(
                image_name, command, ' '.join(sys.argv[1:])),
            shell=True).decode('utf8'))
    except subprocess.CalledProcessError as e:
        print('Error({}): {}'.format(e.returncode, e.output.decode('utf8')),
              file=sys.stderr)
