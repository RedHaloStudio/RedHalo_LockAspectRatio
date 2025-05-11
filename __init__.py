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
from bpy.types import PropertyGroup
from bpy.props import (
    BoolProperty, FloatProperty, IntProperty, PointerProperty
)
# --- Global flag to prevent recursive updates ---
_is_internally_updating_resolution = False

# --- Unique owner for message bus subscriptions for this add-on ---
MSGBUS_OWNER = object() #(bpy.types.RenderSettings) 

# --- Properties ---
class LockAspectRatioProperties(PropertyGroup):
    is_locked: bpy.props.BoolProperty(
        name="Lock Aspect Ratio",
        description="Keep the aspect ratio constant when changing resolution X or Y",
        default=False,
        update=lambda self, context: on_lock_toggle(self, context.scene) # Pass scene
    )# type: ignore
    
    locked_ratio: FloatProperty(
        name="Locked Aspect Ratio",
        description="The aspect ratio that is being maintained",
        default=1.0, # Default to 1:1
        precision=5 
    )# type: ignore

    # Store previous values to detect which one was changed by the user
    prev_res_x: IntProperty(
        description="Internal: Previous resolution X value for comparison"
    ) # type: ignore
    prev_res_y: IntProperty(
        description="Internal: Previous resolution Y value for comparison"
    ) # type: ignore

# --- Callback for when the lock is toggled ---
def on_lock_toggle(props, scene):
    """Called when the is_locked checkbox is changed."""
    global _is_internally_updating_resolution
    if _is_internally_updating_resolution: # Avoid re-triggering during internal updates
        return

    if props.is_locked:
        # Lock engaged: store current aspect ratio
        _is_internally_updating_resolution = True
        if scene.render.resolution_y != 0:
            props.locked_ratio = scene.render.resolution_x / scene.render.resolution_y
        else:
            props.locked_ratio = 1.0 # Avoid division by zero, default to 1:1
            if scene.render.resolution_x != 0: # If X is set, make Y match for 1:1
                # _is_internally_updating_resolution = True
                scene.render.resolution_y = scene.render.resolution_x
                # _is_internally_updating_resolution = False
                    
    props.prev_res_x = scene.render.resolution_x
    props.prev_res_y = scene.render.resolution_y

# --- Callback for when resolution_x or resolution_y changes ---
def resolution_changed(*args):
    scene = bpy.context.scene
    if not scene:
        return
    
    if not hasattr(scene, "lock_aspect_ratio_props"):
        return

    props = scene.lock_aspect_ratio_props
    if not props.is_locked:
        # If not locked, just update prev_res values for the next time the lock might be engaged.
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
                new_y = max(1, new_y) # Ensure resolution is at least 1
                if render.resolution_y != new_y:
                    render.resolution_y = new_y
        elif user_changed_y: # User likely changed Y
            new_x = round(current_y * props.locked_ratio)
            new_x = max(1, new_x) # Ensure resolution is at least 1
            if render.resolution_x != new_x:
                render.resolution_x = new_x
    except Exception as e:
        print(f"Lock Render Aspect Ratio: Error during resolution update: {e}")

    # Update previous values to the new, possibly adjusted, state
    # This must be done AFTER adjustments to correctly detect next user change
    props.prev_res_x = render.resolution_x
    props.prev_res_y = render.resolution_y

def redhalo_register_msgbus_handler():
    # Clear previous subscriptions by this owner
    bpy.msgbus.clear_by_owner(MSGBUS_OWNER)

    subcribe_to_x = (bpy.types.RenderSettings, "resolution_x")
    subcribe_to_y = (bpy.types.RenderSettings, "resolution_y")

    bpy.msgbus.subscribe_rna(
        key = subcribe_to_x,
        owner = MSGBUS_OWNER,
        args = (),
        notify = resolution_changed,
    )

    bpy.msgbus.subscribe_rna(
        key = subcribe_to_y,
        owner = MSGBUS_OWNER,
        args = (),
        notify = resolution_changed,
    )

def unregister_msgbus_handler():
    """Clear all message bus subscriptions for this add-on."""
    bpy.msgbus.clear_by_owner(MSGBUS_OWNER)

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
    bpy.types.Scene.lock_aspect_ratio_props = PointerProperty(type=LockAspectRatioProperties)
    bpy.types.RENDER_PT_format.prepend(resolution_lock_Menu)
    
    redhalo_register_msgbus_handler()

def unregister():
    unregister_msgbus_handler()

    bpy.types.RENDER_PT_format.remove(resolution_lock_Menu)
    del bpy.types.Scene.lock_aspect_ratio_props    
    bpy.utils.unregister_class(LockAspectRatioProperties)

if __name__ == "__main__":
    register()
