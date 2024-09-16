# KiCad_PCBmerge
# A python library for merging multiple KiCad PCBs
#
# Author: Florian Kauer <florian.kauer@koalo.de>
#
# Do not start this directly, instead use a merge script, for example
#
# from pcbnew import *
# import pcbmerge
#
# mypcb = LoadBoard("example_power/power.kicad_pcb")
# pcbmerge.merge(pcb = mypcb,
#                base_anchor = "OUTPUT",
#                addon_anchor = "IN",
#                filename = "example_led/led.kicad_pcb")
#
# pcbmerge.combine_all_areas(mypcb)
# pcbmerge.fill_all_areas(mypcb)
#
# SaveBoard("simple.kicad_pcb", mypcb)
#
#########################################################################
#
# This is free and unencumbered software released into the public domain.
#
# Anyone is free to copy, modify, publish, use, compile, sell, or
# distribute this software, either in source code form or as a compiled
# binary, for any purpose, commercial or non-commercial, and by any
# means.
#
# In jurisdictions that recognize copyright laws, the author or authors
# of this software dedicate any and all copyright interest in the
# software to the public domain. We make this dedication for the benefit
# of the public at large and to the detriment of our heirs and
# successors. We intend this dedication to be an overt act of
# relinquishment in perpetuity of all present and future rights to this
# software under copyright law.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
# IN NO EVENT SHALL THE AUTHORS BE LIABLE FOR ANY CLAIM, DAMAGES OR
# OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE,
# ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR
# OTHER DEALINGS IN THE SOFTWARE.
#
# For more information, please refer to <http://unlicense.org>

from collections import namedtuple
from pcbnew import *
import tempfile
import os
from contextlib import contextmanager

def find_module_by_value(pcb, value):
    modules = list(filter(lambda m: m.GetValue() == value, pcb.GetFootprints()))
    assert len(modules) > 0, "%s not found" % value
    assert len(modules) == 1, "%s is not unique" % value
    return modules[0]

Displacement = namedtuple("Displacement", "delta anchor rot")

def calculate_displacement(a, b):
    return Displacement(
            delta = b.GetPosition() - a.GetPosition(),
            anchor = a.GetPosition(),
            rot = b.GetOrientation() - a.GetOrientation())

def move(element, displacement):
    element.Move(displacement.delta)
    element.Rotate(displacement.anchor, displacement.rot)

@contextmanager
def tempfilename():
    f = tempfile.NamedTemporaryFile(delete=False)
    try:
        f.close()
        yield f.name
    finally:
        try:
            os.unlink(f.name)
        except OSError:
            pass

def fill_all_areas(pcb):
    for i in range(pcb.GetAreaCount()):
        area = pcb.GetArea(i)
        area.ClearFilledPolysList()
        area.UnFill()
        if area.GetIsKeepout():
            continue
        area.BuildFilledSolidAreasPolygons(pcb)

def combine_all_areas(pcb):
    for i in range(pcb.GetNetCount()):
        pcb.CombineAllAreasInNet(None, i, False)

def merge(pcb, base_anchor, addon_anchor, pcb_tmp):
    base_anchor_module = find_module_by_value(pcb, base_anchor)
    addon_anchor_module = find_module_by_value(pcb_tmp, addon_anchor)

    displacement = calculate_displacement(base_anchor_module, addon_anchor_module)
    reverse_displacement = calculate_displacement(addon_anchor_module, base_anchor_module)

    # Remember existing elements in base
    tracks = pcb.GetTracks()
    footprints = pcb.GetFootprints()
    drawings = pcb.GetDrawings()
    zonescount = pcb.GetAreaCount()

    # Remove anchor
    # pcb_tmp.Remove(addon_anchor_module)

    with tempfilename() as fname:
        # Write addon to temporary file
        SaveBoard(fname, pcb_tmp)

        # Replace net names in file
        pcbtext = None
        with open(fname) as fp:
            pcbtext = fp.read()

        with open(fname,'w') as fp:
            fp.write(pcbtext)

        # Append new board file with modified net names
        plugin = IO_MGR.PluginFind(IO_MGR.KICAD_SEXP)
        plugin.Load(fname, pcb)

    # Move the objects of the pcb (but not the pcb_tmp) board so that the anchors line up
    for track in tracks:
        move(track, displacement)
    for footprint in footprints:
        move(footprint, displacement)
    for drawing in drawings:
        move(drawing, displacement)
    for i in range(zonescount):
        move(pcb.GetArea(i), displacement)

    # Move all objects by reverse_displacement so that the pcb board is back to its original position
    for track in pcb.GetTracks():
        move(track, reverse_displacement)
    for footprint in pcb.GetFootprints():
        move(footprint, reverse_displacement)
    for drawing in pcb.GetDrawings():
        move(drawing, reverse_displacement)
    for i in range(pcb.GetAreaCount()):
        move(pcb.GetArea(i), reverse_displacement)

def rename_board(pcb, renamerFunction, renameFootprints):
    if renameFootprints:
        for footprint in pcb.GetFootprints():
            referenceName = footprint.Reference().GetShownText()
            footprint.Reference().SetText(renamerFunction(referenceName))

    for i in range(1, pcb.GetNetCount()):
        net = pcb.FindNet(i)
        net.SetNetname(renamerFunction(net.GetNetname()))
