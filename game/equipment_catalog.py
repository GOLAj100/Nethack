"""Layered clothing: occupation tiers, not strictly increasing usefulness."""
SLOTS={'underwear':('underwear','нижнее бельё'),'socks':('socks','носки'),'base_top':('T-shirt','футболка'),'mid_top':('sweater','кофта'),'armor':('jacket','куртка'),'base_legs':('leggings','подштанники'),'trousers':('trousers','брюки'),'over_legs':('overtrousers','верхние штаны'),'boots':('boots','обувь'),'gloves':('gloves','перчатки'),'helm':('headgear','головной убор'),'cloak':('rain cape','накидка'),'vest':('vest','жилет')}
TIERS={1:('casual','обычная',.4,0,1),2:('sports','спортивная',.25,0,1),3:('work','рабочая',.65,1,2),4:('construction','строительная',1.,2,2),5:('military','военная',1.2,3,3)}
NAMES={}
def install(items):
    for tier,(prefix,ru,weight,protection,warmth) in TIERS.items():
        for slot,(en,label) in SLOTS.items():
            name=f'{prefix} {slot}'; thin=slot in ('underwear','socks','base_top','base_legs'); heavy=slot in ('armor','over_legs','vest','boots','helm')
            items[name]=dict(kind='armor',slot=slot,glyph='[',color=(150,156,130),ac=0,protection=0 if thin else protection,weight=round(weight*(1.5 if heavy else .5),2),warmth=warmth,mobility=1 if tier==2 and slot in ('trousers','boots') else 0,price=10*tier,tier=tier,bench=max(0,tier-2))
            NAMES[name]=(f'{prefix} {en}',f'{label} — {ru} серия')
