"""
Utility to generate BDV metadata XML for a given AcquisitionList, without writing image data.

This will loop through all combinations of illumination, channel, angle, and tile, and call append_view for each.
"""

import os

import npy2bdv
import numpy as np


def write_bdv_metadata_only(acq_list, px_size_um=1.0, z_step=None, out_path=None):
    """
    Write BDV XML metadata for the given AcquisitionList, without writing image data.

    Parameters
    ----------
    acq_list : AcquisitionList
        List of Acquisition objects.
    px_size_um : float
        Pixel size in microns (default 1.0). If you have a config, use cfg.pixelsize[acq['zoom']].
    z_step : float or None
        Z step size in microns. If None, uses acq['z_step'] from the first acquisition.
    out_path : str or None
        Output .h5 file path. If None, uses folder/filename from the first acquisition.
    """
    acq0 = acq_list[0]
    if out_path is None:
        folder = acq0["folder"]
        filename = acq0["filename"]
        out_path = os.path.realpath(os.path.join(folder, filename))
    if z_step is None:
        z_step = acq0["z_step"]

    nilluminations = acq_list.get_n_shutter_configs()
    nchannels = acq_list.get_n_lasers()
    nangles = acq_list.get_n_angles()
    ntiles = acq_list.get_n_tiles()  # If not all tiles were acquired, this will be less than total combinations and will need to be set manually
    blockdim = ((1, 256, 256),)
    subsamp = ((1, 1, 1),)
    compression = None

    bdv_writer = npy2bdv.BdvWriter(
        out_path,
        nilluminations=nilluminations,
        nchannels=nchannels,
        nangles=nangles,
        ntiles=ntiles,
        blockdim=blockdim,
        subsamp=subsamp,
        compression=compression,
    )

    # Get unique values for each axis
    shutterconfigs = acq_list.get_unique_attr_list("shutterconfig")
    lasers = acq_list.get_unique_attr_list("laser")
    rots = acq_list.get_unique_attr_list("rot")
    tiles = []
    for a in acq_list:
        tile_str = f"{a['x_pos']}{a['y_pos']}{a['z_start']}{a['rot']}"
        if tile_str not in tiles:
            tiles.append(tile_str)

    flip_flags = (True, True, False)  # Default flip flags for mesoSPIM

    # For each acquisition, call append_view with correct indices and affine
    for acq in acq_list:
        x_pixels = 5056
        y_pixels = 2960
        x_binning = 1
        y_binning = 1
        shape = (
            acq.get_image_count(),
            int(x_pixels / x_binning),
            int(y_pixels / y_binning),
        )  # dummy shape, not used
        # Affine matrix as in ImageWriter
        x = acq["x_pos"]
        y = acq["y_pos"]
        z = acq["z_start"]
        rot = acq["rot"]
        tile_index = acq_list.get_tile_index(acq)
        px = px_size_um
        sign_xyz = (1 - np.array(flip_flags)) * 2 - 1

        tile_translation = (
            sign_xyz[0] * x / px,
            sign_xyz[1] * y / px,
            sign_xyz[2] * z / z_step,
        )
        affine_matrix = np.array(
            (
                (1.0, 0.0, 0.0, tile_translation[0]),
                (0.0, 1.0, 0.0, tile_translation[1]),
                (0.0, 0.0, 1.0, tile_translation[2]),
            )
        )

        bdv_writer.append_view(
            stack=None,
            virtual_stack_dim=shape,
            illumination=acq_list.find_value_index(
                acq["shutterconfig"], "shutterconfig"
            ),
            channel=acq_list.find_value_index(acq["laser"], "laser"),
            angle=acq_list.find_value_index(acq["rot"], "rot"),
            tile=tile_index,
            voxel_units="um",
            voxel_size_xyz=(px, px, z_step),
            calibration=(1.0, 1.0, z_step / px),
            m_affine=affine_matrix,
            name_affine="Translation to Regular Grid",
        )

    # Set attribute labels and write XML
    bdv_writer.set_attribute_labels("channel", tuple(lasers))
    bdv_writer.set_attribute_labels("illumination", tuple(shutterconfigs))
    bdv_writer.set_attribute_labels("angle", tuple(rots))
    bdv_writer.write_xml()
    bdv_writer.close()
    return out_path
