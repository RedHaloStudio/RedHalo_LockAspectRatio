# ##### BEGIN GPL LICENSE BLOCK #####
#
#  This program is free software; you can redistribute it and/or
#  modify it under the terms of the GNU General Public License
#  as published by the Free Software Foundation; either version 2
#  of the License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software Foundation,
#  Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
#
# ##### END GPL LICENSE BLOCK #####

bl_info = {
    "name": "Lock Render Aspect Ratio",
    "author": "RedHaloStudio 发霉的红地蛋 <redhalostudio@outlook.com>",
    "version": (0, 1, 0),
    "blender": (4, 2, 0),
    "location": "Properties > Output Properties > Format Panel",
    "description": "Locks the render resolution aspect ratio. When locked, adjusting X or Y will proportionally adjust the other.",
    "warning": "",
    "doc_url": "",
    "category": "Render",
}

import bpy
from bpy.app.handlers import persistent # type: ignore

# --- Global flag to prevent recursive updates ---
# This is important because when we change resolution_x, it triggers an update,
# and if we then change resolution_y in response, that's another update.
_is_internally_updating_resolution = False

# --- Properties ---
class LockAspectRatioProperties(bpy.types.PropertyGroup):
    is_locked: bpy.props.BoolProperty(
        name="Lock Aspect Ratio",
        description="Keep the aspect ratio constant when changing resolution X or Y",
        default=False,
        update=lambda self, context: on_lock_toggle(self, context.scene) # Pass scene
    )# type: ignore
    
    locked_ratio: bpy.props.FloatProperty(
        name="Locked Aspect Ratio",
        description="The aspect ratio that is being maintained",
        default=1.0, # Default to 1:1
        precision=5 
    )# type: ignore

    # Store previous values to detect which one was changed by the user
    prev_res_x: bpy.props.IntProperty() # type: ignore
    prev_res_y: bpy.props.IntProperty() # type: ignore

# --- Callback for when the lock is toggled ---
def on_lock_toggle(props, scene):
    """Called when the is_locked checkbox is changed."""
    global _is_internally_updating_resolution
    if _is_internally_updating_resolution: # Avoid re-triggering during internal updates
        return

    if props.is_locked:
        # Lock engaged: store current aspect ratio and previous values
        if scene.render.resolution_y != 0:
            props.locked_ratio = scene.render.resolution_x / scene.render.resolution_y
        else:
            props.locked_ratio = 1.0 # Avoid division by zero, default to 1:1
            if scene.render.resolution_x != 0: # If X is set, make Y match for 1:1
                _is_internally_updating_resolution = True
                scene.render.resolution_y = scene.render.resolution_x
                _is_internally_updating_resolution = False

        props.prev_res_x = scene.render.resolution_x
        props.prev_res_y = scene.render.resolution_y

    # Ensure depsgraph handler is aware of the current state if it wasn't already
    if scene:
        props.prev_res_x = scene.render.resolution_x
        props.prev_res_y = scene.render.resolution_y

def RES_Change(*args):
    scene = bpy.context.scene
    props = scene.lock_aspect_ratio_props

    if not hasattr(props, "is_locked") or not props.is_locked:
        # If not locked, or properties not yet fully initialized,
        # just update prev values for when lock is engaged next.
        if hasattr(props, "prev_res_x"): # Check if props exist
            props.prev_res_x = scene.render.resolution_x
            props.prev_res_y = scene.render.resolution_y
        return

    render = scene.render
    current_x = render.resolution_x
    current_y = render.resolution_y

    # Determine if user changed X or Y
    user_changed_x = (current_x != props.prev_res_x)
    user_changed_y = (current_y != props.prev_res_y)

    if not user_changed_x and not user_changed_y:
        # No relevant change detected
        return

    _is_internally_updating_resolution = True # Set flag BEFORE making changes

    try:
        if user_changed_x: # User likely changed X
            if props.locked_ratio != 0:
                new_y = round(current_x / props.locked_ratio)
                if render.resolution_y != new_y:
                    render.resolution_y = new_y
        elif user_changed_y: # User likely changed Y
            new_x = round(current_y * props.locked_ratio)
            if render.resolution_x != new_x:
                render.resolution_x = new_x
    except Exception as e:
        print(f"Error")

    # Update previous values to the new, possibly adjusted, state
    # This must be done AFTER adjustments to correctly detect next user change
    props.prev_res_x = render.resolution_x
    props.prev_res_y = render.resolution_y

msgbus_owner = (bpy.types.RenderSettings)

def register_msgbus():
    bpy.msgbus.clear_by_owner(msgbus_owner)

    subcribe_to_x = (bpy.types.RenderSettings, "resolution_x")
    subcribe_to_y = (bpy.types.RenderSettings, "resolution_y")

    bpy.msgbus.subscribe_rna(
        key = subcribe_to_x,
        owner = msgbus_owner,
        args = ("resolution_x",),
        notify = RES_Change,
    )

    bpy.msgbus.subscribe_rna(
        key = subcribe_to_y,
        owner = msgbus_owner,
        args = ("resolution_y",),
        notify = RES_Change,
    )

# --- UI Panel ---
def resolution_lock_Menu(self, context):    
    scene = context.scene
    props = scene.lock_aspect_ratio_props

    layout = self.layout
    layout.use_property_split = True
    layout.use_property_decorate = False # No animation icons

    row = layout.row(align=True)
    row.prop(props, "is_locked", toggle = 0)
    if props.is_locked:
        row.label(text=f"Ratio: {props.locked_ratio:.4f}", icon='DECORATE_LOCKED')
    else:
        row.label(text="Unlocked", icon = "DECORATE_UNLOCKED")

def register():
    bpy.utils.register_class(LockAspectRatioProperties)
    bpy.types.Scene.lock_aspect_ratio_props = bpy.props.PointerProperty(type=LockAspectRatioProperties)
    bpy.types.RENDER_PT_format.prepend(resolution_lock_Menu)

    register_msgbus()

def unregister():
    bpy.msgbus.clear_by_owner(msgbus_owner)

    bpy.types.RENDER_PT_format.remove(resolution_lock_Menu)
    del bpy.types.Scene.lock_aspect_ratio_props    
    bpy.utils.unregister_class(LockAspectRatioProperties)

if __name__ == "__main__":
    register()
