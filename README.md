# avi-python-scripts

Collection of useful Avi Python scripts. The scripts are intended to standalone as single files that can be easily shared rather than needing multiple files/libraries etc. to be included, hence utility functions (such as the get_all() function) are defined within each script as needed. Please don't think ill of me - it was a conscious decision!

I have tried to keep package dependencies to a minimum - see requirements.txt. You can install dependencies with:

`pip install -r /path/to/requirements.txt`

See `<script_name>.py --help` for details on usage and parameters.

Note: For any parameter that supports a wildcard syntax using the `*` character, this will result in "globbing" in most Linux shells (the shell will treat the `*` as filename completion by default). You can prevent globbing by escaping the `*` character (usually with `\`), or by disabling globbing before running the command (in most Linux shells, this is achieved using `set -f`).

## template.py

Used as a template for script creation. Includes the generic argument parser and session creation code with automatic discovery of API version.

## backup_restore.py

Script to backup Virtual Services and their related referenced objects allowing selective restore in future. This is useful in scenarios where major changes are being made to Virtual Service configuration and the user needs a way to quickly revert one or more Virtual Services to the previous "known-good" state.

*Examples:*

This will backup all Virtual Services whose names begin with "rc-" in all tenants to the file my_backup.json:

`backup_restore.py -c <controller> -v rc-* -i -t * backup my_backup.json`

This will restore the specific VS called "rc-demo" in the tenant "demo-tenant" from the backup file:

`backup_restore.py -c <controller> -v rc-demo -t demo-tenant restore my_backup.json`

## bulk_change_seg.py

Bulk updates Virtual Services assigned to a source Service Engine Group to a different destination Service Engine Group.

*Examples:*

This will reconfigure all Virtual Services within the specified tenant that are currently using the SE Group "Default-Group" to use the SE Group "DMZ-Group":

`bulk_change_seg.py -c <controller> -t demo-tenant Default-Group DMZ-Group`

This will reconfigure all Virtual Services *except* "specialvs1" and "specialvs2" within the specified tenant that are currently using the SE Group "Default-Group" to use the SE Group "DMZ-Group":

`bulk_change_seg.py -c <controller> -t demo-tenant -e "specialvs1","specialvs2" Default-Group DMZ-Group`

This will reconfigure *only* the Virtual Services named "specialvs1" and "specialvs2" within the specified tenant that are currently using the SE Group "Default-Group" to use the SE Group "DMZ-Group":

`bulk_change_seg.py -c <controller> -t demo-tenant -i "specialvs1","specialvs2" Default-Group DMZ-Group`

## csv_metrics.py

Exports specified VirtualService, Pool or SE metrics to the screen or to a CSV file for analysis, graphing etc (e.g. using Excel!).

Metrics can be aggregated at the Service Engine level by specifying the -a/--aggregate flag.

Metrics can be broken down for specific objects such as Pool Server or WAF Rule by specifying the -o/--objid parameter.

*Examples:*

This will display the last three days' worth of hourly metrics of the specified three metrics from the Virtual Service "example_vs" in the tenant "example_tenant":

`csvmetrics.py -c <controller> -t example_tenant -vs example_vs -m l4_client.avg_rx_bytes,l4_client.avg_tx_bytes,l7_client.avg_ssl_handshakes_new -g hour -l 3d`

This will display the last minute's worth of aggregated real-time metrics for new SSL handshakes across all Virtual Services on the Service Engine "avi-se-example":

`csvmetrics.py -c <controller> -t example_tenant -a -se avi-se-example -m l7_client.avg_ssl_handshakes_new -g realtime -l 1m`

This will display the last hour's worth of total HTTP responses for the Virtual Service "example_vs" broken down by each Pool Server in the Pool "example_pool" (note the wildcard * character may need to be escaped:

`csv_metrics.py -c <controller> -t example_tenant -vs example_vs -pl example_pool -m l7_server.sum_total_responses -g 5min -l 1h -o *`

This will display the last minute's worth of total HTTP 2xx and 4xx responses for the Virtual Service "example_vs" filtered only for the two specified Pool Servers and then aggregated, output to the file "server_metrics.csv":

`csv_metrics.py -c <controller> -t example_tenant -vs example_vs -pl example_pool -m l7_server.sum_resp_2xx,l7_server.sum_resp_4xx -g realtime -l 1m -o 10.10.10.1:80,10.10.10.2:80 -ao -f server_metrics.csv`

This will display the last minute's worth of real-time metrics for WAF rule hits on the rules with rule IDs 941170 and 941171 for the Virtual Service "avi-example":

`csv_metrics.py -c <controller> -t example_tenant -vs example_vs -m waf_rule.sum_matched -g realtime -l 1m -o 941170,941171`

## inventory_report.py

This script uses the Inventory APIs to export summary information about VS, Pool or Service Engines to the screen in tabular form, or to a CSV file that can then be used for reporting purposes.

*Example:*

This will export the inventory of all pools in the tenant "example_tenant" as well as each pool's member servers to a CSV file "output.csv":

`inventory_report.py -c <controller> -t example_tenant -i pooldetail -f output.csv`

## licenses.py

Script to list and delete licenses from the Controller. This is particularly useful for deleting ENTERPRISE licenses (including evaluation licenses) that are still present in the system after the Controller has been switched to ENTERPRISE with CLOUD SERVICES tier.

## logs_to_csv.py

Script to export Virtual Service logs from the Controller to a CSV file. Supports retrieving more than 10,000 logs by iteratively querying the Controller.

The `startdatetime` and `enddatetime` parameters are provided in [ISO8601](https://dencode.com/en/date/iso8601) format. If no timezone offset is provided, the UTC offset from the system on which the script is running will be used. Note that logs entries themselves are always timestamped as UTC.

*Examples:*

This will export logs for the Virtual Service `example_vs` in the tenant `example_tenant` from 1st July 2024 12:00AM EDT (UTC -4 hours) to 15th July 2024 12:00PM EDT to the file `./log_export.csv`:

`logs_to_csv.py -c <controller> -t example_tenant example_vs 2024-07-01T00:00-04:00 2024-07-15T12:00-04:00`

## object_to_hcl.py and object_to_hcl2.py

Scripts to generate Terraform HCL from an existing object or objects. When using Terraform for automation, rather than building the Terraform resource from scratch, it is often easier to create an example of the desired configuration via the UI and then export the configured object directly to Terraform HCL which can then be tweaked to create a templatized resource.

object_to_hcl.py makes use of `terraform import` and `terraform show` commands and should work in older version of Terraform.

object_to_hcl2.py makes use of import blocks and the experimental config generation feature of `terraform plan` introduced in Terraform version 1.5.

Both scripts take the same parameters.

Note 1: These scripts require that the terraform executable is in the execution search path.

Note 2: By default, these scripts will assume the version of the `vmware/avi` Terraform Provider should match the Avi REST API version being used. The Terraform Provider version can be specified explicitly using the `-tx` parameter if required.

*Examples:*

This will export all Virtual Services in the tenant "example_tenant" to a Terraform HCL file "example_vs.tf":

`object_to_hcl.py -c <controller> -t example_tenant virtualservice example_vs.tf`

This will export the Virtual Services named "example_vs1" and "example_vs2" in the tenant "example_tenant" to a Terraform HCL file "example_vs.tf":

`object_to_hcl.py -c <controller> -t example_tenant virtualservice -n example_vs,example_vs2 example_vs.tf`

This will export all Application Profiles whose names containthe string "System-" in the admin tenant to a Terraform HCL file "app_profiles.tf":

`object_to_hcl.py -c <controller> applicationprofile -c System- app_profiles.tf`

## remove_ciphers.py

Removes any ciphers that are classed as unsafe or inadequate according to [Appendix A of RFC7450](https://datatracker.ietf.org/doc/html/rfc7540#appendix-A).

These are the ciphers that would trigger the Controller Fault warning "Unsafe ciphers used in SSL Profile: \[xxx\]"

## replace_certificates.py

Replaces certificates in Virtual Services.

*Example:*

This will replace references to "System-Default-Cert" with "My-Wildcard-Cert" and "System-Default-Cert-EC" with "My-Wildcard-Cert-EC"

`replace_certificates.py -c <controller> -t example_tenant System-Default-Cert,System-Default-Cert-EC My-Wildcard-Cert,My-Wildcard-Cert-EC`

Note: When running in all tenants (`-t *`) where certificates of the same name may exist in multiple tenants, it may be necessary to specify the certificates using their UUIDs rather than their names.

## reset_analytics_configs.py

Disables various expensive Analytics features in Virtual Services. This can be useful in cases where these features were enabled during a testing phase and should be disabled as best practice before going into production.

It is possible to exclude specific Virtual Services from processing if required. The script can be executed against all tenants by specifying `-t *`.

*Example:*

This will disable Client Insights, Non-Significant Logs and Real-Time Metrics in all Virtual Services in the tenant `example_tenant`, excluding the Virtual Services `special_vs1` and `special_vs2`:

`reset_analytics_configs.py -c <controller> -t example_tenant -e special_vs1 special_vs2 -a clientinsights realtimemetrics nonsiglogs`

## unused_objects.py

Lists objects within the Controller that are not used or referenced by any other objects, with the option to delete such objects.

*Example:*

This will list all orphaned objects in any tenant of type Pool,PoolGroup,HTTPPolicySet or L4PolicySet and prompt the user whether to delete each orphaned object that is found:

`unused_objects.py -c <controller> -t * -o pool,poolgroup,httppolicyset,l4policyset -d`

## upgrade_history.py

Outputs the upgrade and patch history for Controller, Service Engine Groups and Service Engines.

*Examples:*

This will output the upgrade and patch history of the given Controller:

`upgrade_history.py -c <controller>`

This will output the upgrade and patch history of the given Controller, Service Engine Groups and Service Engines:

`upgrade_history.py -c <controller> -a`

## user_tokens.py

Lists, creates or deletes user API authentication tokens. This script requires SuperUser privileges.

When creating a token, omitting expiry time will create a one-time-use token.
When listing tokens, omitting a user name will list all tokens for all users.

*Examples:*

This will list any authentication tokens for user "example-user":

`user_tokens.py -c <controller> list -u example-user`

This will delete a specific token (obtain the token's UUID using the list operation):

`user_tokens.py -c <controller> delete <token-uuid>`

This will create a new token for user "example-user" time-limited to 3 hours:

`user_tokens.py -c <controller> create example-user -e 3`

## vmac.py

Script to calculate the Virtual MACs used for floating IPs in Network Services.

*Example:*

This will print out the VMAC corresponding to all Floating IPs defined in Network Service "example_ns" in tenant "example_tenant":

`vmac.py -c <controller> -t example_tenant -n example_ns`

## vrf_map.py

Script to output the mapping between Avi VRF name and local Linux network namespace on a given Service Engine.

## waf_report.py

Prints a table of configured WAF Policies, which VSs use each policy and the policy mode (enforcement/detection) and paranoia level.

`waf_report.py -c <controller> -t <tenant>`
