# mkdd-track-editor
An editor for Mario Kart Double Dash's race tracks. Work in progress.

This is a fork of the editor that has a bunch of QOL updates. All updates from the main branch are merged, except for those that conflict with design choices in this branch

design choices:
object routes and camera routes are split at file load, and only combined at file save. unused routes are removed at load. this means that you can open a file, do nothing, and the saved file will be different from the original file.
for areas, a separate "chase" field is specified, unique from the camera type
rotations are done in terms of euler angles instead of vectors

further qol updates:
the use of side buttons to make the 'add object' button as obsolete as possible
on the bottom, if a single object is selected, its height and distance from the ground will also be shown. 

