"""Low overhead rolling frame metrics; optional psutil for OS counters."""
from collections import deque
import time
import math
import pygame


class Performance:
    def __init__(self):
        self.enabled=False
        self.samples=deque(maxlen=300)
        self.last_wall=time.perf_counter()
        self.last_cpu=time.process_time()
        self.next_sample=0
        self.process_cpu=0
        self.system_cpu=None
        self.rss=None
        self.system_ram=None
        self.process=None
        self.psutil=None
        try:
            import psutil
            self.psutil=psutil
            self.process=psutil.Process()
            psutil.cpu_percent(None)
        except (ImportError,OSError):
            pass
        self.font=None

    def reset(self):
        self.samples.clear()
        self.last_wall=time.perf_counter()
        self.last_cpu=time.process_time()
        self.next_sample=0

    def record(self, frame, update, draw, present):
        if not self.enabled: return
        self.samples.append((frame,update,draw,present))
        now=time.perf_counter()
        if now<self.next_sample: return
        self.next_sample=now+1
        cpu=time.process_time()
        self.process_cpu=100*(cpu-self.last_cpu)/max(.001,now-self.last_wall)
        self.last_cpu,self.last_wall=cpu,now
        if self.psutil:
            try:
                self.rss=self.process.memory_info().rss/1048576
                self.system_cpu=self.psutil.cpu_percent(None)
                self.system_ram=self.psutil.virtual_memory().percent
            except (OSError,self.psutil.Error):
                self.rss=self.system_cpu=self.system_ram=None

    def stats(self):
        if not self.samples: return None
        n=len(self.samples)
        means=[sum(s[i] for s in self.samples)/n for i in range(4)]
        frames=sorted(s[0] for s in self.samples)
        return means,frames[max(0,math.ceil(n*.99)-1)],frames[-1]

    def draw(self,game):
        if not self.enabled: return
        if self.font is None: self.font=pygame.font.SysFont('consolas',15)
        display=game.display
        backend=display.backend if display else 'software'
        gpu=display.gpu_name if display else 'Software'
        lines=[f'PERF | {backend} | {game.views.mode} | cap 60 FPS',gpu]
        stats=self.stats()
        if stats:
            means,p99,peak=stats
            lines += [f'FPS {1000/max(.001,means[0]):.1f} | frame {means[0]:.2f} ms',
                      f'p99 {p99:.2f} ms | max {peak:.2f} ms | N={len(self.samples)}',
                      f'Update/input {means[1]:.2f} | draw {means[2]:.2f} | present {means[3]:.2f} ms']
        lines += [f'Game CPU {self.process_cpu:.1f}% (100% = one core)',
                  f'System CPU {self.system_cpu:.1f}% | RAM {self.system_ram:.1f}%' if self.system_cpu is not None else 'System CPU/RAM: install psutil',
                  f'Game RAM (RSS) {self.rss:.1f} MiB' if self.rss is not None else 'Game RAM: unavailable',
                  f'Chunks cached {len(game.world.chunks) if game.world else 1}',
                  'GPU load/VRAM: not measured | F12 hide']
        rendered=[self.font.render(line,True,(220,235,245)) for line in lines]
        w=min(game.r.surface.get_width(),max(s.get_width() for s in rendered)+16)
        h=len(lines)*19+62
        panel=pygame.Surface((w,h),pygame.SRCALPHA)
        panel.fill((8,12,20,240))
        for i,s in enumerate(rendered): panel.blit(s,(8,6+i*19))
        # Last 150 frame times, fixed 0..50 ms scale; red line = 60 FPS budget.
        top=len(lines)*19+12
        pygame.draw.line(panel,(180,80,65),(8,top+40-13),(w-8,top+40-13))
        values=list(self.samples)[-150:]
        if len(values)>1:
            points=[(8+i*(w-16)/(len(values)-1),top+40-min(50,s[0])*.8) for i,s in enumerate(values)]
            pygame.draw.lines(panel,(80,205,170),False,points,1)
        game.r.surface.blit(panel,(0,0))
