# avi-python-scripts

Collection of useful Avi Python scripts.

See `<script_name>.py --help` for details on parameters.

## template.py

Used as a template for script creation. Includes the generic argument parser and session creation code with automatic discovery of API version as well as helper functions such as `get_all()` which handles paged results to return a large result set.

## backup_restore.py

Script to backup Virtual Services and their related referenced objects allowing selective restore in future. This is useful in scenarios where major changes are being made to Virtual Service configuration and the user needs a way to quickly revert one or more Virtual Services to the previous "known-good" state.

## vrf_map.py

Script to output the mapping between Avi VRF name and local Linux network namespace on a given Service Engine.

## licenses.py

Script to list and delete licenses from the Controller. This is particularly useful for deleting ENTERPRISE licenses (including evaluation licenses) that are still present in the system after the Controller has been switched to ENTERPRISE with CLOUD SERVICES tier.

## vmac.py

This simple script outputs the virtual MAC address that the system would use when Virtual MAC is enabled in the network service for floating IP addresses.
