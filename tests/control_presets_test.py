import os
import sys
sys.path.insert(0,os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pygame
from game.controls import Controls

c=Controls()
c.assign('inventory',0,pygame.K_F9)
c.switch_preset('newcomer')
assert c.action_for(pygame.K_e,0)=='interact'
assert c.action_for(pygame.K_r,0)=='rest'
assert c.action_for(pygame.K_q,0) is None
assert not c.bindings['quaff']
c.assign('inventory',0,pygame.K_F12)
data={'control_preset':c.preset,'control_profiles':c.save_profiles(),'keys':c.save()}
d=Controls()
d.load_profiles(data)
assert d.action_for(pygame.K_F12,0)=='inventory'
assert not d.bindings['quaff']
d.switch_preset('classic')
assert d.action_for(pygame.K_F9,0)=='inventory'
assert d.action_for(pygame.K_e,0)=='eat'
d.switch_preset('newcomer')
assert d.action_for(pygame.K_F12,0)=='inventory'
d.reset()
assert d.action_for(pygame.K_F12,0) is None
assert d.action_for(pygame.K_e,0)=='interact'
print('CONTROL PRESETS OK')
