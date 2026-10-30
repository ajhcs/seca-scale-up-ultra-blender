"""One-degree-of-freedom analytical check of the optional drive hypothesis.

This integrates an ideal hinge with fixed base and specified COM/inertia under
constant gravity. It is not a USD solver, a contact simulation or device data.
"""
import json,math,pathlib
import numpy as np
from scipy.integrate import solve_ivp
from scipy.optimize import brentq
ROOT=pathlib.Path(__file__).resolve().parents[1]
d=json.loads((ROOT/'validation/articulation-model.json').read_text())
name='Display_Tilt';drive=d['provisional_display_drives']['DisplayTilt']
mass=d['body_mass_kg'][name];x,y,z=d['body_com_local_m'][name];inertia=d['body_diagonal_inertia_kg_m2'][name][0]+mass*(y*y+z*z)
k=drive['stiffness_Nm_per_degree']*180/math.pi;c=drive['damping_Nm_s_per_degree']*180/math.pi;cap=drive['max_torque_Nm'];g=9.81
# The position/velocity targets are zero, angular displacement is in radians
# internally, and the force drive is clipped to its stated torque cap.
def torque_gravity(theta):return -mass*g*(y*math.cos(theta)-z*math.sin(theta))
def torque_drive(theta,omega):return max(-cap,min(cap,-k*theta-c*omega))
def rhs(t,s):return [s[1],(torque_gravity(s[0])+torque_drive(*s))/inertia]
equilibrium=brentq(lambda q:torque_gravity(q)+torque_drive(q,0),-.4,.4)
scenarios=[]
for angle in (-.4,0,.4):
 sol=solve_ivp(rhs,(0,5),(angle,0),t_eval=np.linspace(0,5,501),rtol=1e-8,atol=1e-10,max_step=.01)
 torques=[torque_drive(a,v) for a,v in zip(sol.y[0],sol.y[1])]
 scenarios.append({'initial_angle_rad':angle,'final_angle_rad':float(sol.y[0,-1]),'final_velocity_rad_s':float(sol.y[1,-1]),
                   'min_angle_rad':float(min(sol.y[0])),'max_angle_rad':float(max(sol.y[0])),
                   'max_abs_drive_torque_Nm':max(abs(x) for x in torques),'solver_success':sol.success})
checks={'finite_positive_parameters':all(math.isfinite(x) and x>0 for x in (mass,inertia,k,c,cap)),
        'equilibrium_in_study_range':abs(equilibrium)<.4,
        'all_three_scenarios_approach_equilibrium':all(s['solver_success'] and abs(s['final_angle_rad']-equilibrium)<.002 and abs(s['final_velocity_rad_s'])<.01 for s in scenarios),
        'torque_cap_respected':all(s['max_abs_drive_torque_Nm']<=cap+1e-10 for s in scenarios)}
out={'assumed_input':{'mass_kg':mass,'center_of_mass_yz_m':[y,z],'pivot_inertia_kg_m2':inertia,'gravity_m_s2':g,
 'stiffness_Nm_per_degree':drive['stiffness_Nm_per_degree'],'damping_Nm_s_per_degree':drive['damping_Nm_s_per_degree'],'cap_Nm':cap},
 'equilibrium_rad':equilibrium,'equilibrium_degrees':math.degrees(equilibrium),'scenarios':scenarios,'checks':checks,
 'scope':'Ideal isolated 1-DOF fixed-base hinge with constant gravity and an assumed capped angular spring-damper. No impact, other link motion, collision, joint solver, USD runtime, PhysX, measured mechanism or physical verification.'}
(ROOT/'validation/analytic-display-drive.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out,indent=2));assert all(checks.values())
