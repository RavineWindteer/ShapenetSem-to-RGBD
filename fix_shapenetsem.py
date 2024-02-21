# A script to fix the transparency of the .mtl files in the ShapeNetSem dataset.
# This script reads all .mtl files in the given directory and changes the transparency value to 1 - transparency.
#
# Tested on windows 10
#
# Save the modified files to a new directory (suggested):
# Usage: python fix_shapenetsem.py --directory /path/to/ShapeNetSem/models-OBJ/models/ --output_folder /path/to/output/
#
# Overwrite of the original files:
# Usage: python fix_shapenetsem.py --directory /path/to/ShapeNetSem/models-OBJ/models/
#
# Author: Ricardo Reis Pedreiras Cardoso, IST, 2024

import argparse, os

# Parse command line arguments
parser = argparse.ArgumentParser(description='Renders given obj file by rotating a camera around it.')
parser.add_argument('--directory', type=str,
                    help='Directory containing the .mtl files.')
parser.add_argument('--output_folder', type=str, default=None,
                    help='The output directory to save the modified .mtl files. If not specified, the original files will be overwritten.')
args = parser.parse_args()

# Iterate over all files in the directory
for filename in os.listdir(args.directory):
    # Check if the file is a .mtl file
    if filename.endswith('.mtl'):
        # Construct the full file path to the input file
        filepath_input = os.path.join(args.directory, filename)

        # Read the file
        with open(filepath_input, 'r') as file:
            lines = file.readlines()

        # Modify the lines
        # lines = ['d 1\n' if line.startswith('d 0') else line for line in lines]
        new_lines = []
        for line in lines:
            components = line.split()
            if components[0] == 'd':
                components[1] = str(1.0 - float(components[1]))
            new_lines.append(' '.join(components) + '\n')
        lines = new_lines

        # Construct the full file path to the output file
        if args.output_folder is None:
            filepath_output = filepath_input
        else:
            # Check if the output folder exists
            if not os.path.exists(args.output_folder):
                os.makedirs(args.output_folder)
            filepath_output = os.path.join(args.output_folder, filename)
        
        # Write the modified content back to a file
        with open(filepath_output, 'w') as file:
            file.writelines(lines)
        print('fixed and saved ', filepath_output)
print('\n\ndone')