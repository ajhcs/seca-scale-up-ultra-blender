"""Contract-level offline scenarios for the portable synthetic study."""
import json,pathlib,sys
ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'source/synthetic_study'))
from study import Study,LB_PER_KG
checks={};a=Study('A');b=Study('B')
a.set_weight(10);a.tare();a.set_weight(75);a.hold();a.set_weight(100);a.set_units('lb');a.scan('SYNTH-100')
checks['tare_hold_units']=a.display()=={'value':round(65*LB_PER_KG,2),'units':'lb','held':True,'synthetic_id':'SYNTH-100'}
checks['independent_instances']=b.display()['value']==0 and not b.display()['held'] and not b.synthetic_id
try:a.scan('person-name');checks['reject_non_synthetic_fixture']=False
except ValueError:checks['reject_non_synthetic_fixture']=True
s=a.start_transfer(mode='RECEIVER',failures=1,max_attempts=1,latency=1);a.tick(1)
checks['failure_snapshot']=a.state()['transfer_status']=='FAILED' and not a.receiver and s['net_kg']==65
before=s.copy();a.reset_live();a.retry(failures=0);a.tick(1)
checks['manual_retry_preserves_snapshot']=a.state()['transfer_status']=='ACKNOWLEDGED' and a.receiver[s['id']]==before and a.outbox[0]['payload']==before
c=Study('C');c.set_weight(70);payload=c.start_transfer(mode='ACK_LOST',failures=1,max_attempts=2,latency=1,retry_delay=.4);c.tick(2.4)
checks['lost_ack_idempotent_retry']=c.state()['transfer_status']=='ACKNOWLEDGED' and len(c.receiver)==1 and c.receiver[payload['id']]==payload and [e['event'] for e in c.attempt_events]==['ACK_LOST','ACKNOWLEDGED']
d=Study('D');e=Study('D');
for item in (d,e):item.start_transfer(mode='ACK_LOST',failures=1,max_attempts=2,latency=1,retry_delay=.4)
d.tick(2.4)
for i in range(24):e.tick(.1)
checks['timing_partition_invariant']=d.state()==e.state()
f=Study('F');f.set_weight(5);snapshot=f.start_transfer();f.reset_live();f.tick(1)
checks['reset_does_not_erase_pending_or_history']=f.receiver[snapshot['id']]==snapshot and f.display()['value']==0
report={'checks':checks,'scenario_a':a.state(),'scenario_ack_lost':c.state(),'scenario_reset':f.state(),
 'scope':'Independent fictional subset with explicit synthetic inputs, deterministic local mock receiver and no Blender, USD screen adapter, sensor, device firmware, patient data or network. No claim of parity with the original Blender simulator.'}
(ROOT/'validation/synthetic-study.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({'checks':checks,'scope':report['scope']},indent=2));assert all(checks.values())
