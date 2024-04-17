# A script to render a 3D model from the ShapeNetSem dataset using Blender.
# The render simulates a kinect RGBD camera and outputs in the same data format.
# The model is rendered from multiple viewpoints, and optiopnaly from canonical viewpoints.
#
# Written for Blender 2.9.0 (https://download.blender.org/release/Blender2.90/)
# (Blender uses its own Python distribution, so you don't need to install anything else to run this script.
# Just run it from the Blender installation directory.)
# Tested on windows 10
#
# Example (run from the Blender installation directory):
# blender --background --python /path/to/render_blender.py -- --output_folder /path/to/outputs --up 0\,0\,1 --front 1\,0\,0 --aligned_dims 1.0\,1.0\,1.0 --unit 1.0 /path/to/my.obj
#
# Author: Ricardo Reis Pedreiras Cardoso, IST, 2024
# Forked from: https://github.com/panmari/stanford-shapenet-renderer

import argparse, sys, os, math
import bpy
import mathutils

# Parse command line arguments
parser = argparse.ArgumentParser(description='Renders given obj file by rotating a camera around it.')
parser.add_argument('--up', type=str, default = '0\\,-1\\,0',
                    help='Normalized vector in original model space coordinates indicating semantic "upright" orientation of model.')
parser.add_argument('--front', type=str, default = '-1\\,0\\,0',
                    help='Normalized vector in original model space coordinates indicating semantic "front" orientation of model.')
parser.add_argument('--unit', type=float, default = 1.0,
                    help='The scale unit converting model virtual units to meters.')
parser.add_argument('--aligned_dims', type=str, default = '1.000000\,1.000000\,1.000000',
                    help='Aligned dimensions of model after rescaling to meters and upright-front realignment (X-right, Y-back, Z-up).')
parser.add_argument('--views', type=int, default=8,
                    help='How many equally-spaced turntable positions (increments of the camera azimuth angle) to render.')
parser.add_argument('--camera_angle', type=float, default=30,
                    help='Camera elevation in degrees from horizontal (ground) plane.')
parser.add_argument('--canonical_views', type=bool, default=True,
                    help='Whether to render top, bottom, left, right, front and back views in addition to turntable views.')
parser.add_argument('--model_distance_scale', type=float, default=2.1,
                    help='Scaling factor used to compute the distance from the the model to the camera.')
parser.add_argument('obj', type=str,
                    help='Path to the obj file to be rendered.')
parser.add_argument('--output_folder', type=str, default='/tmp',
                    help='The path the output will be dumped to.')
parser.add_argument('--remove_doubles', type=bool, default=True,
                    help='Remove double vertices to improve mesh quality.')
parser.add_argument('--edge_split', type=bool, default=True,
                    help='Adds edge split filter.')
parser.add_argument('--engine', type=str, default='BLENDER_EEVEE',
                    help='Blender internal engine for rendering. E.g. CYCLES, BLENDER_EEVEE, ...')

argv = sys.argv[sys.argv.index("--") + 1:]
args = parser.parse_args(argv)

# Camera intrinsics (for a kinect camera)
ImageWidth = 640
ImageHeight = 480
ox = ImageWidth/2
oy = ImageHeight/2
CameraFOV = 57
fx = 588
fy = 588
K = mathutils.Matrix(((fx, 0, ox), (0, fy, oy), (0, 0, 1)))
Kinv = K.inverted()

# Camera clipping (in meters)
Clip_start = 0.1
Clip_end = 10

# Image with the conversion factor from point projection to plane projection
# (Blender captures the depth to the camera center, so we need to convert it to the depth to the camera plane
# in order to simulate the depth map that would be obtained by a real camera)
projection_image = [[0]*ImageWidth for _ in range(ImageHeight)]
for w in range(ImageWidth):
    for h in range(ImageHeight):
        # Back-project pixel to 3D space
        pixel_vector = mathutils.Vector((w, h, 1)) # homogeneous coordinates
        world_vector = Kinv @ pixel_vector
        world_vector.normalize()
        projection_image[ImageHeight - 1 - h][w] = world_vector.z

# Convert the projection_image to a flat array in RGBA, column-major format
# since Blender uses column-major format for images
projection_image_flat = [item for sublist in projection_image for item in sublist]
projection_image_rgba_flat = []
if args.engine == 'CYCLES':
    for value in projection_image_flat:
        projection_image_rgba_flat.extend([value, value, value, 1.0])
else:
    for value in projection_image_flat:
        projection_image_rgba_flat.extend([1.0, 1.0, 1.0, 1.0])

# Set up rendering
context = bpy.context
scene = bpy.context.scene
render = bpy.context.scene.render

render.engine = args.engine
render.image_settings.color_mode = 'RGBA' # ('RGB', 'RGBA', ...)
render.image_settings.color_depth = '8' # ('8', '16')
render.image_settings.file_format = 'PNG' # ('PNG', 'OPEN_EXR', 'JPEG, ...)
render.resolution_x = ImageWidth
render.resolution_y = ImageHeight
render.resolution_percentage = 100
render.film_transparent = True

scene.use_nodes = True
scene.view_layers["View Layer"].use_pass_normal = True
scene.view_layers["View Layer"].use_pass_diffuse_color = True
scene.unit_settings.system = 'METRIC'
scene.unit_settings.system_rotation = 'RADIANS'

# Set up compositing nodes
nodes = bpy.context.scene.node_tree.nodes
links = bpy.context.scene.node_tree.links

# Clear default nodes
for n in nodes:
    nodes.remove(n)

# Create input render layer node
render_layers = nodes.new('CompositorNodeRLayers')

# Create a node with the projection_image_rgba_flat as the image
projection_image_object = bpy.data.images.new("OutputImage", width=ImageWidth, height=ImageHeight)
projection_image_object.pixels = projection_image_rgba_flat # Blender always stores pixel data as 32-bit floating point numbers
projection_image_texture_node = nodes.new('CompositorNodeImage')
projection_image_texture_node.image = projection_image_object

# Create an RGB to BW node to convert the projection image to grayscale
rgb_to_bw_node = nodes.new('CompositorNodeRGBToBW')

# Create Math node for creating a mask where depth is less than Clip_end - 0.1
# i.e. the background has value 1 and the object has value 0
compare_node = nodes.new(type="CompositorNodeMath")
compare_node.operation = 'GREATER_THAN'
compare_node.inputs[1].default_value = Clip_end - 0.1

# Create Invert node to invert the mask, such that the background has value 0 and the object has value 1
invert_node = nodes.new(type="CompositorNodeInvert")

# Create Math node for multiplication between the depth to camera center and the projection factor to
# get the depth to camera plane
multiply_node_1 = nodes.new(type="CompositorNodeMath")
multiply_node_1.operation = 'MULTIPLY'

# Create Math node for multiplication between the mask and the depth to camera plane
multiply_node_2 = nodes.new(type="CompositorNodeMath")
multiply_node_2.operation = 'MULTIPLY'

# Create depth output nodes to save the depth map to a file
depth_file_output = nodes.new(type="CompositorNodeOutputFile")
depth_file_output.label = 'Depth Output'
depth_file_output.base_path = ''
depth_file_output.file_slots[0].use_node_format = True
depth_file_output.format.file_format = 'OPEN_EXR'
depth_file_output.format.color_mode = 'RGB'
depth_file_output.format.color_depth = '32'

# Link nodes to produce the depth map with distance to camera plane
# and save it to a file
links.new(render_layers.outputs['Depth'], compare_node.inputs[0])
links.new(compare_node.outputs[0], invert_node.inputs[1])
links.new(projection_image_texture_node.outputs[0], rgb_to_bw_node.inputs[0])
links.new(render_layers.outputs['Depth'], multiply_node_1.inputs[0])
links.new(rgb_to_bw_node.outputs[0], multiply_node_1.inputs[1])
links.new(multiply_node_1.outputs[0], multiply_node_2.inputs[0])
links.new(invert_node.outputs[0], multiply_node_2.inputs[1])
links.new(multiply_node_2.outputs[0], depth_file_output.inputs[0])

# Delete default cube
context.active_object.select_set(True)
bpy.ops.object.delete()

# Import textured mesh
bpy.ops.object.select_all(action='DESELECT')

bpy.ops.import_scene.obj(filepath=args.obj)

obj = bpy.context.selected_objects[0]
context.view_layer.objects.active = obj

# Get model orientation
# Split the string by '\\,' and convert each element to float
up_model = mathutils.Vector(list(map(float, args.up.split('\\,'))))
front_model = mathutils.Vector(list(map(float, args.front.split('\\,'))))
up_blender = mathutils.Vector((0.0, 0.0, 1.0))
front_blender = mathutils.Vector((0.0, -1.0, 0.0))

# Compute rotation to align up_model and front_model with up_blender and front_blender
rotation_up = up_model.rotation_difference(up_blender)
front_model_rotated = rotation_up @ front_model
rotation_front = front_model_rotated.rotation_difference(front_blender)
rotation = rotation_front @ rotation_up
rotation_matrix = rotation.to_matrix().to_4x4()

# Apply the rotation to the object's matrix world
obj.matrix_world = rotation_matrix @ obj.matrix_world

# Possibly disable specular shading
for slot in obj.material_slots:
    node = slot.material.node_tree.nodes['Principled BSDF']
    node.inputs['Specular'].default_value = 0.05

# Scale the object
bpy.ops.transform.resize(value=(args.unit,args.unit,args.unit))
bpy.ops.object.transform_apply(scale=True)

if args.remove_doubles:
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.remove_doubles()
    bpy.ops.object.mode_set(mode='OBJECT')
if args.edge_split:
    bpy.ops.object.modifier_add(type='EDGE_SPLIT')
    context.object.modifiers["EdgeSplit"].split_angle = 1.32645
    bpy.ops.object.modifier_apply(modifier="EdgeSplit")

'''
# Compute the geometric center of the object
center = sum((mathutils.Vector(vertex.co) for vertex in obj.data.vertices), mathutils.Vector()) / len(obj.data.vertices)
# Center the object's geometry
for vertex in obj.data.vertices:
    vertex.co -= center
# Update the scene
bpy.context.view_layer.update()
'''

# Compute the geometric center of the object's bounding box
local_bbox_center = 0.125 * sum((mathutils.Vector(b) for b in obj.bound_box), mathutils.Vector())
# Translate the mesh
bpy.ops.object.mode_set(mode='EDIT')
bpy.ops.mesh.select_all(action='SELECT')
bpy.ops.transform.translate(value=-local_bbox_center)
bpy.ops.object.mode_set(mode='OBJECT')

# Make light just directional, disable shadows.
light = bpy.data.lights['Light']
light.type = 'SUN'
light.use_shadow = False
# Possibly disable specular shading:
light.specular_factor = 1.0
light.energy = 10.0

# Add another light source so stuff facing away from light is not completely dark
bpy.ops.object.light_add(type='SUN')
light2 = bpy.data.lights['Sun']
light2.use_shadow = False
light2.specular_factor = 1.0
light2.energy = 0.015
bpy.data.objects['Sun'].rotation_euler = bpy.data.objects['Light'].rotation_euler
bpy.data.objects['Sun'].rotation_euler[0] += 180

# Place camera
cam = scene.objects['Camera']
aligned_dims = mathutils.Vector(list(map(float, args.aligned_dims.split('\\,'))))
max_model_dimension = max(aligned_dims) / 100.0 # in meters
cam.location = (0.0, args.model_distance_scale * max_model_dimension, 0.0)
cam.data.type = 'PERSP'
cam.data.lens_unit = 'FOV'
cam.data.angle = math.radians(CameraFOV)
cam.data.sensor_fit = 'AUTO'
cam.data.lens = 35
cam.data.sensor_width = 32
cam.data.clip_start = Clip_start  # meters
cam.data.clip_end = Clip_end  # meters

cam_constraint = cam.constraints.new(type='TRACK_TO')
cam_constraint.track_axis = 'TRACK_NEGATIVE_Z'
cam_constraint.up_axis = 'UP_Y'

cam_empty = bpy.data.objects.new("Empty", None)
cam_empty.location = (0, 0, 0)
cam_empty.rotation_euler = (math.radians(args.camera_angle), 0.0, 0.0)
cam.parent = cam_empty

scene.collection.objects.link(cam_empty)
context.view_layer.objects.active = cam_empty
cam_constraint.target = cam_empty

stepsize = 360.0 / args.views
rotation_mode = 'XYZ'

model_identifier = os.path.split(args.obj)[1].split('.')[0]
fp = os.path.join(os.path.abspath(args.output_folder), model_identifier, model_identifier)

def render_stil(render_file_path):
    scene.render.filepath = render_file_path
    depth_file_output.file_slots[0].path = render_file_path + "_depth"
    bpy.ops.render.render(write_still=True)

for i in range(0, args.views):
    print("Rotation {}, {}".format((stepsize * i), math.radians(stepsize * i)))
    render_file_path = fp + '_r_{0:03d}'.format(int(i * stepsize))
    render_stil(render_file_path)
    cam_empty.rotation_euler[2] += math.radians(stepsize)

if args.canonical_views:
    # Top
    cam_empty.rotation_euler = (math.radians(90), 0.0, 0.0)
    render_file_path = fp + '_top'
    render_stil(render_file_path)

    # Bottom
    cam_empty.rotation_euler = (math.radians(-90), 0.0, 0.0)
    render_file_path = fp + '_bottom'
    render_stil(render_file_path)

    # Left
    cam_empty.rotation_euler = (0.0, 0.0, math.radians(90))
    render_file_path = fp + '_left'
    render_stil(render_file_path)

    # Right
    cam_empty.rotation_euler = (0.0, 0.0, math.radians(-90))
    render_file_path = fp + '_right'
    render_stil(render_file_path)

    # Front
    cam_empty.rotation_euler = (0.0, 0.0, 0.0)
    render_file_path = fp + '_front'
    render_stil(render_file_path)

    # Back
    cam_empty.rotation_euler = (0.0, 0.0, math.radians(180))
    render_file_path = fp + '_back'
    render_stil(render_file_path)

# For debugging the workflow
#bpy.ops.wm.save_as_mainfile(filepath='debug.blend')
