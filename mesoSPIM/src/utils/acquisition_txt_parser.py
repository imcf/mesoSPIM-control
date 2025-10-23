"""
Parser for mesoSPIM TXT acquisition files (block/section format).

This module provides a function `parse_mesospim_txt(text: str) -> AcquisitionList`
that parses the provided text and returns an AcquisitionList of Acquisition objects.

Example usage:
        from mesoSPIM.src.utils.acquisition_txt_parser import parse_mesospim_txt
        with open('acq.txt') as f:
                acq_list = parse_mesospim_txt(f.read())
"""

import os

from .acquisitions import Acquisition, AcquisitionList
from .bdv_metadata_writer import write_bdv_metadata_only


def parse_mesospim_txt(text: str) -> AcquisitionList:
    """
    Parse a mesoSPIM TXT file (block/section format) into an AcquisitionList.

    Parameters
    ----------
    text : str
            The contents of the TXT file.

    Returns
    -------
    AcquisitionList
            List of Acquisition objects populated from the file.

    # Example usage:
    # txt = "[Metadata for file] /path/to/file.h5\n[CFG]\n[Laser] 488 nm\n...\n[===================== END OF ACQUISITION ======================]"
    # al = parse_mesospim_txt(txt)
    # assert isinstance(al, AcquisitionList)
    """

    def norm_key(k: str) -> str:
        return (
            k.strip()
            .lower()
            .replace(" ", "_")
            .replace("-", "_")
            .replace("(", "")
            .replace(")", "")
        )

    # Split into blocks by END OF ACQUISITION marker
    blocks = []
    current = []
    for line in text.splitlines():
        if line.strip().startswith("[===================== END OF ACQUISITION"):
            if current:
                blocks.append("\n".join(current))
                current = []
            continue
        if line.strip() == "" and not current:
            continue
        current.append(line)
    if current:
        blocks.append("\n".join(current))

    acq_list = []
    for block in blocks:
        data = {}
        folder = None
        filename = None
        for raw in block.splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or line.startswith(";"):
                continue
            if not line.startswith("["):
                continue
            try:
                close = line.index("]")
            except ValueError:
                continue
            key = line[1:close].strip()
            value = line[close + 1 :].strip()
            k = norm_key(key)

            # Metadata file path -> folder + filename
            if k.startswith("metadata_for") or k == "metadata_for_file":
                path = value
                if path:
                    folder = os.path.dirname(path) or "."
                    filename = os.path.basename(path)
                continue

            if "laser" == k:
                data["laser"] = value
                continue
            if "intensity" in k:
                try:
                    data["intensity"] = int(float(value))
                except Exception:
                    pass
                continue
            if k == "zoom":
                data["zoom"] = value
                continue
            if "filter" == k:
                data["filter"] = value
                continue
            if k in ("shutter", "shutterconfig"):
                data["shutterconfig"] = value
                continue

            # Position block keys
            if k in ("x_pos", "y_pos", "f_start", "f_end", "z_start", "z_end", "rot"):
                try:
                    data[k] = float(value)
                except Exception:
                    pass
                continue
            if k in ("z_stepsize", "z_step", "z_step_size"):
                try:
                    data["z_step"] = float(value)
                except Exception:
                    pass
                continue
            if k in ("z_planes", "zplane", "planes"):
                try:
                    data["planes"] = int(float(value))
                except Exception:
                    pass
                continue

            # ETL parameters
            if k.startswith("etl_l_offset") or k == "etl_l_offset":
                try:
                    data["etl_l_offset"] = float(value)
                except Exception:
                    pass
                continue
            if k.startswith("etl_l_amplitude"):
                try:
                    data["etl_l_amplitude"] = float(value)
                except Exception:
                    pass
                continue
            if k.startswith("etl_r_offset"):
                try:
                    data["etl_r_offset"] = float(value)
                except Exception:
                    pass
                continue
            if k.startswith("etl_r_amplitude"):
                try:
                    data["etl_r_amplitude"] = float(value)
                except Exception:
                    pass
                continue

        # assemble kwargs for Acquisition
        if folder is not None:
            data["folder"] = folder
        if filename is not None:
            data["filename"] = filename

        # convert rot -> theta_pos param accepted in Acquisition constructor
        if "rot" in data:
            data["theta_pos"] = data.pop("rot")

        # create Acquisition object
        try:
            acq = Acquisition(**data)
        except Exception:
            acq = Acquisition()
            for kk, vv in data.items():
                try:
                    acq[kk] = vv
                except Exception:
                    pass

        # ensure planes is set
        if "planes" in data:
            acq["planes"] = int(data["planes"])
        else:
            acq["planes"] = acq.get_image_count()

        acq_list.append(acq)

    return AcquisitionList(acq_list)


# Optional: main for quick manual test
if __name__ == "__main__":
    import sys

    with open(sys.argv[1]) as f:
        al = parse_mesospim_txt(f.read())
    print(f"Parsed {len(al)} acquisitions.")
    write_bdv_metadata_only(al, px_size_um=0.85, z_step=5.0)
