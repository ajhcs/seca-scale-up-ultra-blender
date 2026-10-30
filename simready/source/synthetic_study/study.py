"""Deterministic, offline study of a small synthetic scale workflow.

This is an independent interpretation, not an implementation of seca firmware
and not a clinical, metrology, networking or sensor model. No I/O occurs here.
"""
from dataclasses import dataclass,field
from copy import deepcopy
from math import isfinite

LB_PER_KG=2.2046226218487757

@dataclass
class Study:
    instance_id: str
    gross_kg: float=0.0
    tare_kg: float=0.0
    units: str='kg'
    held: dict|None=None
    synthetic_id: str=''
    outbox: list=field(default_factory=list)
    receiver: dict=field(default_factory=dict)
    attempt_events: list=field(default_factory=list)
    _serial: int=0
    _active: dict|None=None

    def set_weight(self,kg):
        kg=float(kg)
        if not isfinite(kg) or not 0<=kg<=360: raise ValueError('synthetic weight must be finite and within 0..360 kg')
        self.gross_kg=kg

    def set_units(self,units):
        if units not in ('kg','lb'):raise ValueError('units must be kg or lb')
        self.units=units

    def tare(self):
        self.tare_kg=self.gross_kg

    def clear_tare(self):
        self.tare_kg=0.0

    def _live(self):
        return {'gross_kg':self.gross_kg,'tare_kg':self.tare_kg,'net_kg':self.gross_kg-self.tare_kg}

    def hold(self):
        self.held=self._live()

    def release_hold(self):
        self.held=None

    def scan(self,synthetic_id):
        if not isinstance(synthetic_id,str) or not synthetic_id.startswith('SYNTH-') or not synthetic_id[6:].isdigit():
            raise ValueError('use a fictional ID of the form SYNTH-<digits>')
        self.synthetic_id=synthetic_id

    def display(self):
        result=self.held if self.held is not None else self._live()
        value=result['net_kg']*(LB_PER_KG if self.units=='lb' else 1.0)
        return {'value':round(value,2),'units':self.units,'held':self.held is not None,'synthetic_id':self.synthetic_id}

    def start_transfer(self,*,mode='NONE',failures=0,max_attempts=3,latency=1.0,retry_delay=0.4):
        if self._active and self._active['status'] in ('PENDING','RETRY_WAIT'):raise RuntimeError('transfer already active')
        if mode not in ('NONE','RECEIVER','ACK_LOST'):raise ValueError('unknown mock failure mode')
        if not isinstance(failures,int) or failures<0 or not isinstance(max_attempts,int) or max_attempts<1:raise ValueError('invalid attempts')
        if not isfinite(latency) or latency<=0 or not isfinite(retry_delay) or retry_delay<=0:raise ValueError('invalid mock timing')
        self._serial+=1
        snapshot={'id':f'{self.instance_id}-{self._serial:06d}','synthetic_id':self.synthetic_id,**deepcopy(self.held if self.held is not None else self._live())}
        record={'payload':snapshot,'status':'PENDING','attempts':1,'mode':mode,'failures_remaining':failures,'max_attempts':max_attempts,
                'latency':float(latency),'retry_delay':float(retry_delay),'elapsed':0.0}
        self.outbox.append(record);self._active=record
        return deepcopy(snapshot)

    def retry(self,*,failures=0,max_attempts=3):
        a=self._active
        if not a or a['status']!='FAILED':raise RuntimeError('no failed transfer')
        if not isinstance(failures,int) or failures<0 or not isinstance(max_attempts,int) or max_attempts<1:raise ValueError('invalid attempts')
        a.update(status='PENDING',attempts=1,failures_remaining=failures,max_attempts=max_attempts,elapsed=0.0)

    def tick(self,seconds):
        seconds=float(seconds)
        if not isfinite(seconds) or seconds<0:raise ValueError('time must be finite and nonnegative')
        a=self._active
        while a and a['status'] in ('PENDING','RETRY_WAIT'):
            duration=a['latency'] if a['status']=='PENDING' else a['retry_delay']
            needed=max(0.0,duration-a['elapsed'])
            if seconds+1e-10<needed:
                a['elapsed']+=seconds;break
            seconds=max(0.0,seconds-needed);a['elapsed']=0.0
            if a['status']=='RETRY_WAIT':
                a['attempts']+=1;a['status']='PENDING';continue
            failed=a['mode']!='NONE' and a['failures_remaining']>0
            if failed:a['failures_remaining']-=1
            payload=deepcopy(a['payload']);key=payload['id']
            if not failed or a['mode']=='ACK_LOST':
                previous=self.receiver.get(key)
                if previous is not None and previous!=payload:
                    a['status']='FAILED';self.attempt_events.append({'id':key,'event':'ID_CONFLICT'});break
                self.receiver[key]=payload
            event=('ACK_LOST' if a['mode']=='ACK_LOST' else 'RECEIVER_UNAVAILABLE') if failed else 'ACKNOWLEDGED'
            self.attempt_events.append({'id':key,'event':event})
            if not failed:a['status']='ACKNOWLEDGED'
            elif a['attempts']>=a['max_attempts']:a['status']='FAILED'
            else:a['status']='RETRY_WAIT'

    def reset_live(self):
        """Clear live data only; pending work, holds in snapshots and history survive."""
        self.gross_kg=0.0;self.tare_kg=0.0;self.units='kg';self.held=None;self.synthetic_id=''

    def state(self):
        return {'instance_id':self.instance_id,'display':self.display(),
                'transfer_status':self._active['status'] if self._active else 'IDLE',
                'outbox':deepcopy(self.outbox),'receiver':deepcopy(self.receiver),'attempt_events':deepcopy(self.attempt_events)}
