# ControlScripts

Collection of useful ControlScripts

## disable_client_insights.py

This script can be run on a schedule using the in-built Controller scheduler and will automatically disable Client Insights on any Virtual Service where it has been enabled. This is because Client Insights is a tech preview feature that can have impact in production environments due to the large amount of data collected; customers may want to ensure users are not able to accidentally configure this feature.

Example scheduler configuration:

``` language=Text
+------------------+------------------------------------------------+
| Field            | Value                                          |
+------------------+------------------------------------------------+
| uuid             | scheduler-90571d70-d44a-4514-90f9-86c34be1317f |
| name             | Client-Insights-Checker                        |
| enabled          | False                                          |
| run_mode         | RUN_MODE_PERIODIC                              |
| start_date_time  | 2023-05-25T18:59:53.940521                     |
| frequency        | 60                                             |
| frequency_unit   | SCHEDULER_FREQUENCY_UNIT_MIN                   |
| run_script_ref   | disable_client_insights                        |
| scheduler_action | SCHEDULER_ACTION_RUN_A_SCRIPT                  |
| tenant_ref       | admin                                          |
+------------------+------------------------------------------------+
```

When the script is run, it will display output to the EVENTS log (including if there were no Virtual Services found with CI enabled or if there were any API errors), but you must enable the "Include Internal" filter to see these events

## clear_alerts.py

This ControlScript should be triggered to run on the VS_UP EVENT and will automatically clear any previous alerts generated for the VS_DOWN EVENT for that VS.

## sticky_pool_group.py

When the highest-priority pool in a pool group fails, traffic fails over to a "secondary" pool in the group with the next-highest priority. When the highest-priority pool comes back up, standard behaviour is that new connections/requests will start being sent to this pool again. In some cases, the customer may prefer for the failover to be "sticky", for example to allow some investigation into the cause of the failure before manually failing back.

The Pool Group configuration parameter `deactivate_primary_pool_on_down` was added in version 20.1.7 and provides similar functionality natively, but there may still be some scenarios where the ControlScript implementation is preferred:

- `deactivate_primary_pool_on_down` is a runtime feature and does not result in a configuration change. This means its effect does not survive Service Engine reboots or Virtual Service migration.
- `deactivate_primary_pool_on_down` requires manual intervention to restore the original "primary" (highest priority) Pool whereas this ControlScript simply "swaps" the priority of the "primary" Pool with the next-highest priority Pool that is operational, making that Pool the new "primary" pool.

The ControlScript should be triggered to run on the POOL_UP and POOL_DOWN events _for each of the Pools in the Pool Group_. Here is an example of the script's behaviour with a Pool Group with three Pools and multiple sequential failures:

For example if the pool group state starts as follows with all pools up (i.e. all traffic is going to pool-1):
pool-1 : Priority 100
pool-2 : Priority 50
pool-3 : Priority 10

Then if pool-1 fails, the script needs to swap the priorities of pool-1 and pool-2:
pool-1 : Priority 50 (DOWN)
pool-2 : Priority 100
pool-3 : Priority 10

If pool-2 were to fail now, the script needs to swap the priorities of pool-2 and pool-3 (ignoring pool-1 as it is not operational):
pool-1 : Priority 50 (DOWN)
pool-2 : Priority 10 (DOWN)
pool-3 : Priority 100

If pool-3 were to fail at this point, no action needs to be taken by the script since there is no longer any available pool in the pool group.

In the scenario where all pools in the pool group go down, the script also ensures that the first pool that subsequently comes back up is assigned the highest priority to ensure correct operation going forward, e.g.:

pool-1 : Priority 50 (DOWN)
pool-2 : Priority 10 (DOWN)
pool-3 : Priority 100 (DOWN)

If pool-2 now comes back online:

pool-1 : Priority 50 (DOWN)
pool-2 : Priority 100
pool-3 : Priority 10 (DOWN)
