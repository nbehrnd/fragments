#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-3-Clause
"""This script flattens .json files for structure templates of Avogadro."""

import argparse
import json
from pathlib import Path


def get_args():
    """Collect command-line arguments"""
    parser = argparse.ArgumentParser(
        description="script to flatten .json files for structure templates of Avogadro",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    parser.add_argument(
        "directory",
        help="directory of files to process",
        type=Path,
    )

    parser.add_argument(
        "-r",
        "--round_coords",
        help="number of decimals of atomic coordinates to round to",
        type=int,
        default=5,
    )

    parser.add_argument(
        "-v",
        "--validate",
        help="equally display intermediate results",
        action="store_true",
    )

    group = parser.add_argument_group(
        "mutually exclusive options",
        "if originally assigned, a processed CJSON file will either retain",
    )
    exclusive_group = group.add_mutually_exclusive_group(required=False)
    exclusive_group.add_argument(
        "-m",
        "--minimize",
        help="atoms, bonds, charges, and spin",
        action="store_true",
    )

    exclusive_group.add_argument(
        "-n",
        "--minimize2",
        help="atoms, bonds, charges, but no spin",
        action="store_true",
    )

    return parser.parse_args()


def recursive_search(path: Path):
    file_list = []
    file_list.extend([x for x in path.iterdir() if x.is_file()])
    for d in [x for x in path.iterdir() if x.is_dir()]:
        file_list.extend(recursive_search(d))
    return file_list


def flatten_arrays(data: dict) -> dict:
    """Turn any lists of simple items (not dicts or lists) into strings."""
    if isinstance(data, list):
        # Turn simple lists into flat strings
        if all(not isinstance(i, (dict, list)) for i in data):
            return json.dumps(data)
        # Recursively flatten any nested lists
        else:
            items = [flatten_arrays(i) for i in data]
            return items
    elif isinstance(data, dict):
        # Recursively flatten all entries
        new = {k: flatten_arrays(v) for k, v in data.items()}
        return new
    else:
        return data


def flatten_dumps(data: dict) -> str:
    """Do the same as json.dumps() but write simple lists on a single line."""
    flattened = flatten_arrays(data)
    # Lists are now strings, remove quotes to turn them back into lists
    output = json.dumps(flattened, indent=2).replace('"[', "[").replace(']"', "]")
    # Any strings within lists will have had their quotes escaped, so get rid of escapes
    output = output.replace(r"\"", '"')
    return output


def minimal(cjson: dict, minimize, minimize2) -> dict:
    """Reduce a CJSON to core geometry data.

    This retains the atoms with their coordinates, bonds, charges, and spin."""
    minimal_cjson = {
        "chemicalJson": cjson.get("chemicalJson", 1),
        "atoms": {
            "coords": {"3d": cjson["atoms"]["coords"]["3d"]},
            "elements": {"number": cjson["atoms"]["elements"]["number"]},
        },
        "bonds": {
            "connections": {"index": cjson["bonds"]["connections"]["index"]},
            "order": cjson["bonds"]["order"],
        },
    }
    # Formal charges are useful but may or may not be there
    if "formalCharges" in cjson["atoms"]:
        minimal_cjson["atoms"]["formalCharges"] = cjson["atoms"]["formalCharges"]
    # Keep total charge/spin if present
    if "properties" in cjson:
        minimal_cjson["properties"] = {}

        properties_to_retain = []
        if minimize:
            properties_to_retain = ["totalCharge", "totalSpinMultiplicity"]
        if minimize2:
            properties_to_retain = ["totalCharge"]

        for prop in properties_to_retain:
            if prop in cjson["properties"]:
                minimal_cjson["properties"][prop] = cjson["properties"][prop]

    return minimal_cjson


def round_coords(cjson: dict, places: int) -> dict:
    """Round atomic coordinates in a CJSON to a specified number of decimals"""
    coords = cjson["atoms"]["coords"]["3d"]
    rounded = [round(c, places) for c in coords]
    cjson["atoms"]["coords"]["3d"] = rounded
    return cjson


def flatten_all(
    cjson_list: list[Path],
    minimize: bool,
    minimize2: bool,
    round_coords_places: int | None = None,
    validate: bool = False,
):
    """Flatten CSON according to parameters set"""
    checks = {}

    # Read then write each cjson
    for file in cjson_list:
        with open(file, "r", encoding="utf-8") as source:
            cjson = json.load(source)
            if validate:
                print(f"\nread:\n{cjson}")

        if minimize or minimize2:
            cjson = minimal(cjson, minimize, minimize2)
            if validate:
                print(f"\nminimized:\n{cjson}")

        if round_coords_places:
            cjson = round_coords(cjson, round_coords_places)
            if validate:
                print(f"\nrounded:\n{cjson}")

        flattened = flatten_dumps(cjson)
        if validate:
            print(f"\nflattened:\n{cjson}")
            print(f"\noutput:\n{flattened}")

        with open(file, "w", encoding="utf-8") as new:
            new.write(flattened)

        if validate:
            # Test we get the same object back as we originally read
            check = cjson == json.loads(flattened)
            checks[file] = check
            if check is False:
                print(f"{file} was not validated")

    if validate:
        print(checks)


if __name__ == "__main__":
    args = get_args()

    # Get all CJSON files in dir
    file_list = recursive_search(args.directory)
    cjson_list = [f for f in file_list if f.suffix == ".cjson"]

    flatten_all(
        cjson_list, args.minimize, args.minimize2, args.round_coords, args.validate
    )
