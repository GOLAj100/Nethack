"""Visual entity contract and compatibility regressions (no GL required)."""
import json
import random
import sys
import unittest
from types import SimpleNamespace

from engine.visual import Visual, VisualCamera
from engine.visual_manager import VisualManager
from game.level import Level
from game import mapgen as MG
from game.furniture import Furniture
from game.items import Item
from game.entities import Actor


def level():
    return Level(0, 8, 8, random.Random(123), generation={
        'tiles': [MG.FLOOR] * 64, 'rooms': [], 'kind': 'room', 'style': 0})


class VisualManagerTest(unittest.TestCase):
    def test_layers_visibility_spatial_lookup_and_dirty(self):
        manager = VisualManager()
        floor = Visual(x=1, y=1, z=0, layer=0)
        actor = Visual(x=1, y=1, z=0, layer=4)
        hidden = Visual(x=1, y=1, layer=5, visible=False)
        ids = [manager.add(v) for v in (actor, floor, hidden)]
        self.assertEqual(len(set(ids)), 3)
        self.assertIs(manager.get_at(1.5, 1.5, .5), actor)
        self.assertEqual(list(manager.iter_visible(VisualCamera(bounds=(0, 0, 3, 3, -1, 2)))), [floor, actor])
        manager.clear_dirty()
        self.assertFalse(actor.dirty)
        actor.x = -2
        manager.mark_dirty(ids[0])
        self.assertTrue(actor.dirty)
        self.assertIs(manager.get_at(-1.5, 1.5, .5), actor)
        self.assertIs(manager.get_at(1.5, 1.5, .5), floor)
        manager.remove(ids[0])
        self.assertIsNone(manager.get_at(-1.5, 1.5, .5))

    def test_depth_order_and_footprint_visibility(self):
        manager = VisualManager()
        back = Visual(x=-2, y=1, z=0, width=3, depth=2, layer=2)
        front = Visual(x=0, y=2, z=0, layer=2)
        upper = Visual(z=1, layer=2)
        for obj in (upper, front, back):
            manager.add(obj)
        self.assertEqual(manager.get_by_layer(2), [back, front, upper])
        self.assertEqual(list(manager.iter_visible(VisualCamera(cells=frozenset({(0, 1, 0)})))), [back])


class LevelVisualTest(unittest.TestCase):
    def test_terrain_direct_writes_slices_doors_and_air(self):
        lv = level()
        manager = lv.visual_manager
        self.assertEqual(len(manager.get_by_layer(0)), 64)
        lv.tiles[lv.idx(2, 2)] = MG.WALL
        self.assertEqual(len(manager.get_by_layer(1)), 1)
        self.assertTrue(manager.blocks_cell(2, 2))
        lv.set(2, 2, MG.DOOR)
        lv.doors[2, 2] = {'open': False, 'broken': False}
        self.assertTrue(manager.blocks_cell(2, 2))
        lv.doors[2, 2]['open'] = True
        self.assertFalse(manager.blocks_cell(2, 2))
        lv.tiles[:] = [MG.AIR] * 64
        self.assertEqual(manager.get_by_layer(0), [])
        self.assertFalse(manager.has_floor(2, 2))

    def test_dynamic_objects_move_die_remove_and_replace(self):
        lv = level()
        manager = lv.visual_manager
        chair = Furniture('chair', 2, 2)
        item = Item('water')
        monster = Actor(4, 4, hp=10, glyph='M')
        lv.furniture.append(chair)
        lv.items[3, 3] = item
        lv.monsters.append(monster)
        furniture = manager.get_by_layer(2)[0]
        entity = manager.get_by_layer(4)[0]
        self.assertEqual(len(manager.get_by_layer(3)), 1)
        manager.clear_dirty()
        chair.x = 5
        monster.x = 6
        self.assertIs(manager.get_by_layer(2)[0], furniture)
        self.assertEqual(furniture.x, 5)
        self.assertEqual(manager.get_by_layer(4)[0].x, 6)
        self.assertTrue(entity.dirty)
        monster.hp = 0
        self.assertEqual(manager.get_by_layer(4), [])
        lv.items.pop((3, 3))
        self.assertEqual(manager.get_by_layer(3), [])
        lv.furniture = [Furniture('wardrobe', 1, 1, rotated=True)]
        self.assertTrue(manager.blocks_cell(2, 1))
        self.assertFalse(manager.blocks_cell(1, 2))
        self.assertIsNone(lv.furniture_at(5, 2))

    def test_world_coordinates_light_and_save_compatibility(self):
        lv = level()
        lv.chunk_x, lv.chunk_y, lv.world_z = -2, 3, -1
        lv.profile = {'floor_texture': 'metal', 'wall_texture': 'wallpaper'}
        lv.furniture.append(Furniture('lamp post', 1, 2))
        lv.items[2, 2] = Item('water')
        floor = lv.visual_manager.get_by_layer(0)[0]
        self.assertEqual((floor.x, floor.y, floor.z, floor.material), (-16, 24, -1, 'metal'))
        lamp = lv.visual_manager.get_by_layer(2)[0]
        self.assertTrue(lamp.emits_light)
        self.assertGreater(lamp.light_radius, 0)
        self.assertIsNone(lamp.mesh_id)
        data = json.loads(json.dumps(lv.serialize()))
        restored = Level.deserialize(data, random.Random(123))
        self.assertEqual(len(restored.visual_manager.get_by_layer(0)), 64)
        self.assertEqual(len(restored.visual_manager.get_by_layer(3)), 1)
        self.assertNotIn('visual_manager', data)

    def test_ray_context_reads_visual_index(self):
        from engine.volume import RayContext
        lv = level()
        lv.set(3, 3, MG.WALL)
        context = RayContext(SimpleNamespace(world=None, level=lv))
        # The render path must no longer call gameplay visibility for walls.
        lv.can_see_through = lambda *args: self.fail('legacy wall lookup')
        self.assertTrue(context.resolve(3, 3, 0)[3])
        self.assertFalse(context.resolve(2, 3, 0)[3])

    def test_monster_movement_reuses_terrain_snapshot(self):
        lv = level()
        monster = Actor(2, 2, hp=10)
        lv.monsters.append(monster)
        manager = lv.visual_manager
        grid = manager.grid()
        revision = manager.geometry_revision
        monster.x = 3
        self.assertIs(manager.grid(), grid)
        self.assertEqual(manager.geometry_revision, revision)
        self.assertEqual(manager.get_by_layer(4)[0].x, 3)

    def test_billboards_use_visuals_once_per_footprint_and_world_offsets(self):
        from engine.volume import collect_sprites
        lv = level()
        lv.chunk_x, lv.chunk_y, lv.world_z = -1, 1, -2
        lv.furniture.append(Furniture('sofa', 2, 2))
        lv.items[3, 2] = Item('water')
        lv.monsters.append(Actor(4, 2, hp=10, glyph='M'))
        player = SimpleNamespace(x=0, y=0, chunk_x=-1, chunk_y=1, world_z=-2)
        game = SimpleNamespace(level=lv, world=SimpleNamespace(w=8, h=8), player=player,
                               visible_world={(x, 2): (lv, x, 2) for x in (2, 3, 4)})
        lv.item_at = lv.monster_at = lv.furniture_at = lambda *args: self.fail('legacy lookup')
        sprites = collect_sprites(game)
        self.assertEqual([s[2] for s in sprites], ['∩', lv.items[3, 2].glyph, 'M'])
        self.assertEqual(sprites[0][:2], (2.5, 2.0))
        self.assertAlmostEqual(sprites[-1][4], .45)

    def test_cast_frame_matches_reference_rays_with_doors_and_furniture(self):
        import pygame
        from engine.volume import cast, cast_frame, camera, RayContext
        lv = level()
        lv.set(4, 3, MG.DOOR)
        lv.doors[4, 3] = {'open': False}
        lv.furniture.append(Furniture('wardrobe', 5, 2))
        player = SimpleNamespace(x=2, y=3, world_z=0, chunk_x=0, chunk_y=0)
        game = SimpleNamespace(level=lv, world=None, player=player,
                               tile_glyph=lambda *args: ('#', (150, 150, 150)))
        view = SimpleNamespace(quality=0, yaw=.1, pitch=.2, draw_distance=12, show_ceiling=True)
        area = pygame.Rect(0, 0, 120, 60)
        frame = cast_frame(view, game, area)
        origin, forward, right, up, width, height, _ = camera(view, game, area)
        for sy in range(0, height, 7):
            for sx in range(0, width, 9):
                u = (sx+.5-width/2)/frame['focal']
                v = (height/2-sy-.5)/frame['focal']
                direction = tuple(forward[i]+u*right[i]+v*up[i] for i in range(3))
                hit = cast(origin, direction, lambda x, y, z:
                           (lv, x, y) if z == 0 and lv.in_bounds(x, y) else None, 12)
                expected = hit[0] if hit is not None and hit[1] is not None else float('inf')
                self.assertAlmostEqual(frame['depth'][sy*width+sx], expected, places=10)
        # A visual-only wall must affect the same ray source as legacy terrain.
        lv.visual_manager.add(Visual(x=3, y=3, z=0, layer=1, opaque=True))
        self.assertTrue(RayContext(game).resolve(3, 3, 0)[3])


if __name__ == '__main__':
    unittest.main(argv=[sys.argv[0] or 'visual_entity_test'])
