# A script to generate the list of commands to be executed to render the .obj files in the ShapeNetSem dataset
# with the render_blender.py script.
#
# This script reads the metadata file provided by ShapeNetSem and constructs the list of commands to be executed.
#
# Usage: python generate_commands.py --metadata /path/to/ShapeNetSem/metadata.txt --obj_directory /path/to/ShapeNetSem/models-OBJ/models/ --render_blender_path /path/to/render_blender.py --output_directory /path/to/output/
#
# Author: Ricardo Reis Pedreiras Cardoso, IST, 2024

import pandas as pd
import argparse, os

# Parse command line arguments
parser = argparse.ArgumentParser(description='Renders given obj file by rotating a camera around it.')
parser.add_argument('--metadata', type=str,
                    help='Path to the metadata file provided by ShapeNetSem.')
parser.add_argument('--obj_directory', type=str,
                    help='The absulute path to the directory containing the .obj files.')
parser.add_argument('--render_blender_path', type=str,
                    help='The absulute path to the render_blender.py file.')
parser.add_argument('--output_directory', type=str,
                    help='The absulute path to the output directory.')
args = parser.parse_args()

# Read the metadata file
df = pd.read_csv(args.metadata)

# Filter rows where the 'weight' column is not NaN
filtered_df = df[df['unit'].notna()]
number_elements = filtered_df.shape[0]

lines = []
for index, counter in zip(filtered_df.index, range(1, number_elements + 1)):
    # Construct the command
    line = 'blender --background --python ' + args.render_blender_path + ' -- --output_folder ' + args.output_directory
    
    # Up, front, aligned dimensions and unit of the object
    up = filtered_df['up'][index]
    if isinstance(up, str):
        line += ' --up ' + up
    front = filtered_df['front'][index]
    if isinstance(front, str):
        line += ' --front ' + front
    aligned_dims = filtered_df['aligned.dims'][index]
    if isinstance(aligned_dims, str):
        line += ' --aligned_dims ' + aligned_dims
    unit = str(filtered_df['unit'][index])
    if isinstance(unit, str):
        line += ' --unit ' + unit
    
    # Path to the .obj file
    filename = (filtered_df['fullId'][index]).split('.')[1]
    filepath = os.path.join(args.obj_directory, filename) + '.obj'
    line += ' ' + filepath + '\n'
    
    lines.append(line)
    print(counter, ' out of ', number_elements)

print('Save data')

# Write the modified content back to a file
with open('commands.txt', 'w') as file:
    file.writelines(lines)