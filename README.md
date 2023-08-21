# avi-python-scripts

Collection of useful Avi Python scripts. The scripts are intended to standalone as single files that can be easily shared rather than needing multiple files/libraries etc. to be included, hence utility functions (such as the get_all() function) are defined within each script as needed. Please don't think ill of me - it was a conscious decision!

I have tried to keep package dependencies to a minimum - see requirements.txt. You can install dependencies with:

`pip install -r /path/to/requirements.txt`

See `<script_name>.py --help` for details on usage and parameters.

## template.py

Used as a template for script creation. Includes the generic argument parser and session creation code with automatic discovery of API version.

## backup_restore.py

Script to backup Virtual Services and their related referenced objects allowing selective restore in future. This is useful in scenarios where major changes are being made to Virtual Service configuration and the user needs a way to quickly revert one or more Virtual Services to the previous "known-good" state.

*Examples:*

This will backup all Virtual Services whose names begin with "rc-" in all tenants to the file my_backup.json:

`backup_restore.py -c <controller> -v rc-* -i -t * backup my_backup.json`

This will restore the specific VS called "rc-demo" in the tenant "demo-tenant" from the backup file:

`backup_restore.py -c <controller> -v rc-demo -t demo-tenant restore my_backup.json`

## vrf_map.py

Script to output the mapping between Avi VRF name and local Linux network namespace on a given Service Engine.

## licenses.py

Script to list and delete licenses from the Controller. This is particularly useful for deleting ENTERPRISE licenses (including evaluation licenses) that are still present in the system after the Controller has been switched to ENTERPRISE with CLOUD SERVICES tier.

## vmac.py

This simple script outputs the virtual MAC address that the system would use when Virtual MAC is enabled in the network service for floating IP addresses.

## inventory_report.py

This script uses the Inventory APIs to export summary information about VS, Pool or Service Engines to the screen in tabular form, or to a CSV file that can then be used for reporting purposes.

*Example:*

This will export the inventory of all pools in the tenant "example_tenant" as well as each pool's member servers to a CSV file "output.csv":

`inventory_report.py -c <controller> -t example_tenant -i pooldetail -f output.csv`

## csv_metrics.py

Exports specified VirtualService metrics to the screen or to a simple CSV file for analysis, graphing etc (e.g. using Excel!).

*Example:*

This will display the last three days' worth of hourly metrics of the specified three metrics from the Virtual Service "example_vs" in the tenant "example_tenant":

`csvmetrics.py -c <controller> -t example_tenant -v example_vs -t admin -v rc-demo -m l4_client.avg_rx_bytes,l4_client.avg_tx_bytes,l7_client.avg_ssl_handshakes_new  -g hour -l 3d`

## unused_objects.py

Lists objects within the Controller that are not used or referenced by any other objects, with the option to delete such objects.

*Example:*

This will list all orphaned objects in any tenant of type Pool,PoolGroup,HTTPPolicySet or L4PolicySet and prompt the user whether to delete each orphaned object that is found:

`unused_objects.py -c <controller> -t * -o pool,poolgroup,httppolicyset,l4policyset -d`
