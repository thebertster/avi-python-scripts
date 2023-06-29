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

## clear_alerts.py

This ControlScript should be triggered to run on the VS_UP EVENT and will automatically clear any previous alerts generated for the VS_DOWN EVENT for that VS.
