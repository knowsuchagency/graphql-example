"""Utility functions."""

import json
import eliot


def to_file(output_file, encoder=json.JSONEncoder):
    """
    Add a destination that writes a JSON message per line to the given file.
    @param output_file: A file-like object.
    """
    destination = eliot.FileDestination(file=output_file, encoder=encoder)

    eliot.Logger._destinations.add(
        destination
    )

    return destination
