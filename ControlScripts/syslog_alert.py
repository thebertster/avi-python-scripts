#!/usr/bin/env python3
import sys
import json
import socket
import datetime
import os

# --- Configuration ---
SYSLOG_SERVER = "<syslog server>"
SYSLOG_PORT = 514
SYSLOG_HOSTNAME = "Avi-Controller-Cluster"
SYSLOG_TAG = "Avi-Control-Script INFO"
# ---------------------

#UDP specifically chosen to prevent the Control Script from getting stuck waiting for TCP timeouts
def send_udp_syslog(target_ip, message):
    """Formats and sends the message via raw UDP socket."""
    # <14> = Priority for Facility 1 (User), Severity 6 (Informational)
    timestamp = datetime.datetime.now().strftime('%b %d %H:%M:%S')
    
    # Standard Syslog Format: <PRI>TIMESTAMP HOSTNAME TAG: MESSAGE
    syslog_msg = f"<14>{timestamp} {SYSLOG_HOSTNAME} {SYSLOG_TAG}: {message}"
    
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.sendto(syslog_msg.encode('utf-8'), (target_ip, SYSLOG_PORT))
        sock.close()
    except Exception as e:
        print(f"Socket error: {str(e)}")

def main():
    # 1. Resolve DNS for the logging server
    try:
        target_ip = socket.gethostbyname(SYSLOG_SERVER)
    except socket.gaierror as e:
        print(f"DNS Resolution failed: {str(e)}")
        sys.exit(1)

    # 2. Grab the environment description provided by Avi
    env_description = os.environ.get('EVENT_DESCRIPTION')

    # 3. Handle the JSON payload passed via arguments
    raw_input = sys.argv[1] if len(sys.argv) > 1 else "{}"

    try:
        alert_dict = json.loads(raw_input)
        events = alert_dict.get('events', [])
        
        if not events:
            # Handle metric alerts or alerts without nested events
            msg = env_description if env_description else f"Metric Alert: {alert_dict.get('name', 'Unknown')}"
            send_udp_syslog(target_ip, msg)
            return

        for event in events:
            event_id = event.get('event_id', 'UNKNOWN_EVENT')
            obj_name = event.get('obj_name', 'Unknown Object')
            
            # Prioritize: Environment Variable -> JSON event_description -> event_details
            event_desc = env_description
            if not event_desc:
                event_desc = event.get('event_description')
            if not event_desc:
                details = event.get('event_details', {})
                event_desc = json.dumps(details) if details else "No description available"
            
            formatted_msg = f"Alert: {obj_name} | ID: {event_id} | Details: {event_desc}"
            send_udp_syslog(target_ip, formatted_msg)

    except Exception as e:
        # Fallback to sending the environment description if JSON parsing fails
        if env_description:
            send_udp_syslog(target_ip, f"Alert Summary: {env_description} (JSON Parse Error)")
        else:
            print(f"Unexpected error: {str(e)}")

if __name__ == "__main__":
    main()