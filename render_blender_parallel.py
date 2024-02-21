# A script to execute the commands in parallel. It is used to render the .obj files in the ShapeNetSem dataset
# with the render_blender.py script in parallel.
#
# Similar to the render_blender.py script, this script is executed from the Blender installation directory.
# Usage: python /path/to/render_blender_parallel.py --file /path/to/commands.txt
#
# Author: Ricardo Reis Pedreiras Cardoso, IST, 2024

import subprocess
from concurrent.futures import ThreadPoolExecutor
import argparse

# Parse command line arguments
parser = argparse.ArgumentParser(description='Renders given obj file by rotating a camera around it.')
parser.add_argument('--file', type=str,
                    help='The file containing the list of commands to be executed. Default is commands.txt.')
parser.add_argument('--max_workers', type=int, default=5,
                    help='The maximum number of workers to use. Default is 5.')
args = parser.parse_args()

def execute_command(command):
    try:
        subprocess.run(command, shell=True, check=True)
    except subprocess.CalledProcessError as e:
        print(f"Error executing command '{command}': {e}")

def execute_commands_in_parallel(commands_file, max_workers=args.max_workers):
    with open(commands_file, 'r') as file:
        commands = file.readlines()

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        executor.map(execute_command, commands)

if __name__ == "__main__":
    commands_file = args.file
    execute_commands_in_parallel(commands_file)