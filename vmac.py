#!/usr/bin/env python

import sys
from hashlib import md5

if len(sys.argv) != 3:
    print('Syntax: vmac <segroup uuid> <floating ip>')
    exit()

seg_uuid = sys.argv[1]
floating_ip = sys.argv[2]

segrp_fip_str = seg_uuid + floating_ip

vmac_id = md5(segrp_fip_str.encode('utf-8')).hexdigest()

vmac = '0e:' + ':'.join(['%0.2x' % (int(vmac_id[i:i+2], base=16) ^ 255)
                         for i in range(0, 10, 2)])

print(f'Virtual MAC: {vmac}')
