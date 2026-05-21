"""
Lectura externa y configurable del estado del juego.

No inyecta DLL ni ejecuta rutinas dentro del cliente. Solo usa ReadProcessMemory
via pymem, igual que una lectura externa estilo Cheat Engine.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Optional

import config
import game_memory


@dataclass
class MemoryEntity:
    address: int
    entity_id: Optional[int] = None
    entity_type: Optional[int] = None
    name: str = ""
    x: Optional[int] = None
    y: Optional[int] = None
    distance: Optional[int] = None
    state: Optional[int] = None
    alive: Optional[bool] = None
    source: str = ""


@dataclass
class MemoryDrop:
    address: int
    value_from_recv: Optional[int] = None
    item_id: Optional[int] = None
    x: Optional[int] = None
    y: Optional[int] = None
    owner_id: Optional[int] = None


@dataclass
class MemoryItem:
    address: int
    item_id: Optional[int] = None
    type_id: Optional[int] = None
    name: str = ""
    amount: Optional[int] = None
    amount_limit: Optional[int] = None
    is_arrow: bool = False
    source: str = ""


@dataclass
class MemorySnapshot:
    ok: bool = False
    error: str = ""
    player_base: Optional[int] = None
    player_pointer_source: str = ""
    player_id_address: Optional[int] = None
    player_id: Optional[int] = None
    player_x: Optional[int] = None
    player_y: Optional[int] = None
    coclassic_role_mgr: Optional[int] = None
    coclassic_hero: Optional[int] = None
    coclassic_hero_id: Optional[int] = None
    coclassic_hero_name: str = ""
    coclassic_hero_x: Optional[int] = None
    coclassic_hero_y: Optional[int] = None
    coclassic_hero_status: Optional[int] = None
    coclassic_hero_dead: bool = False
    coclassic_hero_xp_ready: bool = False
    coclassic_hero_max_hp: Optional[int] = None
    coclassic_hero_stamina: Optional[int] = None
    coclassic_hero_max_stamina: Optional[int] = None
    coclassic_hero_stat_table: Optional[int] = None
    coclassic_hero_max_mana: Optional[int] = None
    coclassic_hero_max_mana_valid: Optional[int] = None
    coclassic_bag_count: Optional[int] = None
    coclassic_bag_full: Optional[bool] = None
    coclassic_arrow_equipped: Optional[int] = None
    coclassic_arrow_packs: int = 0
    coclassic_inventory_items: list[MemoryItem] = field(default_factory=list)
    coclassic_deque_map: Optional[int] = None
    coclassic_deque_map_size: Optional[int] = None
    coclassic_deque_offset: Optional[int] = None
    coclassic_deque_size: Optional[int] = None
    coclassic_roles_read: int = 0
    coclassic_roles_debug: list[MemoryEntity] = field(default_factory=list)
    coclassic_deque_debug: list[str] = field(default_factory=list)
    entities: list[MemoryEntity] = field(default_factory=list)
    nearby_entities: list[MemoryEntity] = field(default_factory=list)
    drops: list[MemoryDrop] = field(default_factory=list)

    def to_dict(self) -> dict:
        data = asdict(self)
        if self.player_base is not None:
            data["player_base_hex"] = f"{self.player_base:08X}"
        if self.player_id_address is not None:
            data["player_id_address_hex"] = f"{self.player_id_address:08X}"
        if self.coclassic_role_mgr is not None:
            data["coclassic_role_mgr_hex"] = f"{self.coclassic_role_mgr:016X}"
        if self.coclassic_hero is not None:
            data["coclassic_hero_hex"] = f"{self.coclassic_hero:016X}"
        if self.coclassic_hero_stat_table is not None:
            data["coclassic_hero_stat_table_hex"] = f"{self.coclassic_hero_stat_table:016X}"
        if self.coclassic_deque_map is not None:
            data["coclassic_deque_map_hex"] = f"{self.coclassic_deque_map:016X}"
        return data


def _cfg_int(name: str, default: int = 0) -> int:
    try:
        value = getattr(config, name, default)
        if value is None or value == "":
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def _cfg_bool(name: str, default: bool = False) -> bool:
    return bool(getattr(config, name, default))


def _cfg_addr(name: str) -> Optional[int]:
    return game_memory.parse_hex_address(str(getattr(config, name, "") or ""))


def _fmt_chain(chain: dict) -> str:
    module = str(chain.get("module", ""))
    base_offset = int(chain.get("base_offset", 0) or 0)
    offsets = chain.get("offsets", []) or []
    joined = ",".join(f"{int(o):X}" for o in offsets)
    return f"{module}+{base_offset:08X} [{joined}]"


def _read_u8(proc: str, address: int) -> tuple[Optional[int], Optional[str]]:
    return game_memory.read_uint8_at(proc, address)


def _read_u16(proc: str, address: int) -> tuple[Optional[int], Optional[str]]:
    return game_memory.read_uint16_at(proc, address)


def _read_u32(proc: str, address: int) -> tuple[Optional[int], Optional[str]]:
    return game_memory.read_uint32_at(proc, address)


def _read_u64(proc: str, address: int) -> tuple[Optional[int], Optional[str]]:
    return game_memory.read_uint64_at(proc, address)


def _read_i32(proc: str, address: int) -> tuple[Optional[int], Optional[str]]:
    return game_memory.read_int32_at(proc, address)


def _looks_like_process_pointer(value: Optional[int]) -> bool:
    if not value:
        return False
    return 0x10000 <= int(value) <= 0x00007FFFFFFFFFFF


def _read_coord(proc: str, base: int, offset: int, shift: int) -> Optional[int]:
    value, _err = _read_u32(proc, base + offset)
    if value is None:
        return None
    if shift > 0:
        value >>= shift
    return int(value)


def _resolve_player_base(proc: str, snapshot: MemorySnapshot) -> Optional[int]:
    chains = getattr(config, "MEMORY_PLAYER_POINTER_CHAINS", []) or []
    expected_id = getattr(config, "MEMORY_PLAYER_EXPECTED_ID", None)
    id_offset = _cfg_int("MEMORY_PLAYER_ID_OFFSET", 0)
    pointer_size = _cfg_int("MEMORY_POINTER_SIZE", 4)

    for chain in chains:
        if not isinstance(chain, dict):
            continue
        module = str(chain.get("module", "") or "")
        base_offset = int(chain.get("base_offset", 0) or 0)
        offsets = [int(o) for o in (chain.get("offsets", []) or [])]
        if not module:
            continue

        addr, err = game_memory.resolve_module_pointer_chain(
            proc,
            module,
            base_offset,
            offsets,
            pointer_size,
        )
        if err or not addr:
            snapshot.error = err or "Pointer chain sin resultado"
            continue

        if expected_id is not None:
            value, value_err = game_memory.read_uint32_at(proc, addr + id_offset)
            if value_err or value != int(expected_id):
                continue

        snapshot.player_pointer_source = _fmt_chain(chain)
        snapshot.error = ""
        return addr

    direct = _cfg_addr("MEMORY_PLAYER_BASE_ADDRESS_HEX")
    if direct:
        snapshot.player_pointer_source = "direct"
        return direct

    ptr_addr = _cfg_addr("MEMORY_PLAYER_PTR_ADDRESS_HEX")
    if not ptr_addr:
        return None

    pointer_size = _cfg_int("MEMORY_POINTER_SIZE", 4)
    player_base, err = game_memory.read_pointer_at(proc, ptr_addr, pointer_size)
    if err:
        snapshot.error = f"player ptr: {err}"
        return None
    snapshot.player_pointer_source = "pointer_address"
    return player_base


def _entity_addresses(proc: str, base: int) -> list[int]:
    list_addr = _cfg_addr("MEMORY_ENTITY_LIST_ADDRESS_HEX")
    if not list_addr and base:
        offset = _cfg_int("MEMORY_ENTITY_LIST_OFFSET_FROM_PLAYER", 0)
        if offset:
            list_addr = base + offset
    if not list_addr:
        return []

    count = max(0, _cfg_int("MEMORY_ENTITY_LIST_COUNT", 0))
    stride = max(1, _cfg_int("MEMORY_ENTITY_LIST_STRIDE", 4))
    pointer_size = _cfg_int("MEMORY_POINTER_SIZE", 4)
    pointer_list = _cfg_bool("MEMORY_ENTITY_LIST_IS_POINTERS", True)
    limit = min(count, max(0, _cfg_int("MEMORY_ENTITY_MAX_READ", 80)))
    addresses: list[int] = []

    for index in range(limit):
        slot = list_addr + (index * stride)
        if pointer_list:
            addr, err = game_memory.read_pointer_at(proc, slot, pointer_size)
            if err or not addr:
                continue
            addresses.append(int(addr))
        else:
            addresses.append(slot)
    return addresses


def _read_entities(proc: str, base: int) -> list[MemoryEntity]:
    id_offset = _cfg_int("MEMORY_ENTITY_ID_OFFSET", 0x190)
    type_offset = _cfg_int("MEMORY_ENTITY_TYPE_OFFSET", 0x1BC)
    x_offset = _cfg_int("MEMORY_ENTITY_X_OFFSET", 0x4)
    y_offset = _cfg_int("MEMORY_ENTITY_Y_OFFSET", 0x8)
    state_offset = _cfg_int("MEMORY_ENTITY_STATE_OFFSET", 0x70)
    dead_state = _cfg_int("MEMORY_ENTITY_DEAD_STATE", 0x3A)
    coord_shift = _cfg_int("MEMORY_ENTITY_COORD_SHIFT", 6)

    entities: list[MemoryEntity] = []
    seen: set[int] = set()
    for address in _entity_addresses(proc, base):
        if address in seen:
            continue
        seen.add(address)
        entity = MemoryEntity(address=address)
        entity.entity_id, _ = _read_u32(proc, address + id_offset)
        entity.entity_type, _ = _read_u32(proc, address + type_offset)
        entity.state, _ = _read_u8(proc, address + state_offset)
        entity.x = _read_coord(proc, address, x_offset, coord_shift)
        entity.y = _read_coord(proc, address, y_offset, coord_shift)
        if entity.state is not None:
            entity.alive = entity.state != dead_state
        if entity.entity_id or entity.entity_type or entity.x is not None:
            entities.append(entity)
    return entities


def _drop_addresses() -> list[int]:
    list_addr = _cfg_addr("MEMORY_DROP_LIST_ADDRESS_HEX")
    if not list_addr:
        return []
    count = max(0, _cfg_int("MEMORY_DROP_LIST_COUNT", 0))
    stride = max(1, _cfg_int("MEMORY_DROP_LIST_STRIDE", 32))
    limit = min(count, max(0, _cfg_int("MEMORY_DROP_MAX_READ", 80)))
    return [list_addr + (index * stride) for index in range(limit)]


def _read_drops(proc: str) -> list[MemoryDrop]:
    value_offset = _cfg_int("MEMORY_DROP_VALUE_OFFSET", 0x4)
    id_offset = _cfg_int("MEMORY_DROP_ID_OFFSET", 0x8)
    x_offset = _cfg_int("MEMORY_DROP_X_OFFSET", 0xC)
    y_offset = _cfg_int("MEMORY_DROP_Y_OFFSET", 0xE)
    owner_offset = _cfg_int("MEMORY_DROP_OWNER_ID_OFFSET", 0x18)

    drops: list[MemoryDrop] = []
    for address in _drop_addresses():
        drop = MemoryDrop(address=address)
        drop.value_from_recv, _ = _read_u32(proc, address + value_offset)
        drop.item_id, _ = _read_u32(proc, address + id_offset)
        drop.x, _ = _read_u16(proc, address + x_offset)
        drop.y, _ = _read_u16(proc, address + y_offset)
        drop.owner_id, _ = _read_u32(proc, address + owner_offset)
        if drop.value_from_recv or drop.item_id:
            drops.append(drop)
    return drops


def _is_coclassic_monster(entity_id: Optional[int], name: str, status: Optional[int]) -> bool:
    if entity_id is None or not (400000 <= int(entity_id) < 500000):
        return False
    if name.startswith("Guard") or name.startswith("Patrol"):
        return False
    status_value = int(status or 0)
    userstatus_dead = 1 << 5
    userstatus_ghost = 1 << 10
    return (status_value & (userstatus_dead | userstatus_ghost)) == 0


def _chebyshev_distance(
    ax: Optional[int],
    ay: Optional[int],
    bx: Optional[int],
    by: Optional[int],
) -> Optional[int]:
    if ax is None or ay is None or bx is None or by is None:
        return None
    return max(abs(int(ax) - int(bx)), abs(int(ay) - int(by)))


def _read_coclassic_role(proc: str, role_addr: int) -> Optional[MemoryEntity]:
    if not _looks_like_process_pointer(role_addr):
        return None

    id_offset = _cfg_int("MEMORY_COCLASSIC_ROLE_ID_OFFSET", 0x68)
    name_offset = _cfg_int("MEMORY_COCLASSIC_ROLE_NAME_OFFSET", 0x94)
    name_size = _cfg_int("MEMORY_COCLASSIC_ROLE_NAME_SIZE", 16)
    x_offset = _cfg_int("MEMORY_COCLASSIC_ROLE_X_OFFSET", 0xD8)
    y_offset = _cfg_int("MEMORY_COCLASSIC_ROLE_Y_OFFSET", 0xDC)
    status_offset = _cfg_int("MEMORY_COCLASSIC_ROLE_STATUS_OFFSET", 0x30)

    entity_id, id_err = _read_u32(proc, role_addr + id_offset)
    if id_err or entity_id is None:
        return None
    name, _ = game_memory.read_c_string_at(proc, role_addr + name_offset, name_size)
    x, _ = _read_i32(proc, role_addr + x_offset)
    y, _ = _read_i32(proc, role_addr + y_offset)
    status, _ = _read_u64(proc, role_addr + status_offset)

    entity = MemoryEntity(address=int(role_addr), source="coclassic")
    entity.entity_id = entity_id
    entity.entity_type = entity_id
    entity.name = name or ""
    entity.x = x
    entity.y = y
    entity.state = status
    entity.alive = _is_coclassic_monster(entity_id, entity.name, status)
    return entity


def _read_coclassic_item(proc: str, item_addr: int, source: str = "") -> Optional[MemoryItem]:
    if not _looks_like_process_pointer(item_addr):
        return None

    id_offset = _cfg_int("MEMORY_COCLASSIC_ITEM_ID_OFFSET", 0x08)
    type_offset = _cfg_int("MEMORY_COCLASSIC_ITEM_TYPE_OFFSET", 0x10)
    name_offset = _cfg_int("MEMORY_COCLASSIC_ITEM_NAME_OFFSET", 0x18)
    name_size = _cfg_int("MEMORY_COCLASSIC_ITEM_NAME_SIZE", 16)
    amount_offset = _cfg_int("MEMORY_COCLASSIC_ITEM_AMOUNT_OFFSET", 0x62)
    limit_offset = _cfg_int("MEMORY_COCLASSIC_ITEM_AMOUNT_LIMIT_OFFSET", 0x64)

    item_id, id_err = _read_u32(proc, item_addr + id_offset)
    type_id, type_err = _read_u32(proc, item_addr + type_offset)
    if (id_err and type_err) or (item_id is None and type_id is None):
        return None

    name, _ = game_memory.read_c_string_at(proc, item_addr + name_offset, name_size)
    amount, _ = _read_u16(proc, item_addr + amount_offset)
    amount_limit, _ = _read_u16(proc, item_addr + limit_offset)
    type_value = int(type_id or 0)
    text_name = name or ""

    item = MemoryItem(address=int(item_addr), source=source)
    item.item_id = item_id
    item.type_id = type_id
    item.name = text_name
    item.amount = amount
    item.amount_limit = amount_limit
    item.is_arrow = (1050000 <= type_value < 1060000) or ("Arrow" in text_name)
    return item


def _read_shared_ptr_deque(
    proc: str,
    deque_addr: int,
    max_read: int,
    reader,
) -> tuple[list, list[str], Optional[int]]:
    qwords: list[int] = []
    raw_debug: list[str] = []
    for qindex in range(8):
        value, _ = _read_u64(proc, deque_addr + qindex * 8)
        qwords.append(int(value or 0))

    layouts: list[tuple[int, int, int, int, str]] = []
    for start in (0, 8, 16, 24):
        if start + 24 >= 64:
            continue
        layouts.append((
            qwords[start // 8],
            qwords[start // 8 + 1],
            qwords[start // 8 + 2],
            qwords[start // 8 + 3],
            f"start=+{start:02X}",
        ))

    best_items: list = []
    best_size: Optional[int] = None
    best_score = -1
    shared_ptr_size = 16

    for map_addr, map_size, myoff, size, layout_name in layouts:
        if not (
            _looks_like_process_pointer(map_addr)
            and map_size
            and int(map_size) <= 0x10000
            and int(size) <= 10000
        ):
            continue

        limit = min(int(size), max(0, max_read))
        for block_size in (1, 2, 4, 8, 16):
            for ptr_delta in (0, 8):
                local_items: list = []
                local_seen: set[int] = set()
                for index in range(limit):
                    logical_index = int(myoff or 0) + index
                    block_index = (logical_index // block_size) % int(map_size)
                    item_index = logical_index % block_size
                    block_ptr, block_err = _read_u64(proc, int(map_addr) + block_index * 8)
                    if block_err or not _looks_like_process_pointer(block_ptr):
                        continue
                    shared_ptr_addr = int(block_ptr) + item_index * shared_ptr_size + ptr_delta
                    item_ptr, item_err = _read_u64(proc, shared_ptr_addr)
                    if item_err or not _looks_like_process_pointer(item_ptr):
                        continue
                    if int(item_ptr) in local_seen:
                        continue
                    local_seen.add(int(item_ptr))
                    item = reader(proc, int(item_ptr))
                    if item:
                        local_items.append(item)

                score = len(local_items)
                if score > best_score:
                    best_score = score
                    best_items = local_items
                    best_size = int(size)
                    raw_debug = [f"using {layout_name} block={block_size} delta={ptr_delta} size={int(size)}"]

    return best_items, raw_debug, best_size


def _read_coclassic_inventory(proc: str, hero: int, snapshot: MemorySnapshot) -> None:
    max_bag = max(1, _cfg_int("MEMORY_COCLASSIC_MAX_BAG_ITEMS", 40))
    item_limit = max_bag
    deque_addr = int(hero) + _cfg_int("MEMORY_COCLASSIC_HERO_INVENTORY_OFFSET", 0xB20)
    items, debug, size = _read_shared_ptr_deque(
        proc,
        deque_addr,
        item_limit,
        lambda p, addr: _read_coclassic_item(p, addr, "bag"),
    )
    snapshot.coclassic_inventory_items = items[:max_bag]
    snapshot.coclassic_bag_count = size if size is not None else len(items)
    snapshot.coclassic_bag_full = int(snapshot.coclassic_bag_count or 0) >= max_bag
    if debug:
        snapshot.coclassic_deque_debug.extend([f"bag {line}" for line in debug])

    equipment_offset = _cfg_int("MEMORY_COCLASSIC_HERO_EQUIPMENT_OFFSET", 0xB88)
    left_weapon_slot = _cfg_int("MEMORY_COCLASSIC_EQUIP_LWEAPON_SLOT", 4)
    equipped_ptr, _ = _read_u64(proc, int(hero) + equipment_offset + left_weapon_slot * 16)
    equipped = _read_coclassic_item(proc, int(equipped_ptr or 0), "equip_lweapon")
    if equipped and equipped.is_arrow:
        snapshot.coclassic_arrow_equipped = int(equipped.amount or 0)

    arrow_packs = 0
    if equipped and equipped.is_arrow and int(equipped.amount or 0) > 3:
        arrow_packs += 1
    for item in snapshot.coclassic_inventory_items:
        if item.is_arrow and int(item.amount or 0) > 3:
            arrow_packs += 1
    snapshot.coclassic_arrow_packs = arrow_packs


def _read_coclassic_roles(proc: str, snapshot: MemorySnapshot) -> tuple[list[MemoryEntity], list[MemoryEntity]]:
    shared_ptr_size = 16
    roles: list[MemoryEntity] = []
    debug_roles: list[MemoryEntity] = []
    seen: set[int] = set()
    raw_debug: list[str] = []
    best_meta: tuple[int, int, int, int, str, int, int] | None = None
    deque_addr = int(snapshot.coclassic_role_mgr or 0) + _cfg_int("MEMORY_COCLASSIC_ROLE_MGR_DEQUE_OFFSET", 0x70)
    qwords: list[int] = []
    for qindex in range(8):
        value, _ = _read_u64(proc, deque_addr + qindex * 8)
        qwords.append(int(value or 0))
    raw_debug.append(
        "deque qwords: "
        + " ".join(f"+{i * 8:02X}={value:016X}" for i, value in enumerate(qwords))
    )

    layouts: list[tuple[int, int, int, int, str]] = []
    for start in (0, 8, 16, 24):
        if start + 24 >= 64:
            continue
        map_addr = qwords[start // 8]
        map_size = qwords[start // 8 + 1]
        myoff = qwords[start // 8 + 2]
        size = qwords[start // 8 + 3]
        layouts.append((map_addr, map_size, myoff, size, f"start=+{start:02X}"))

    # MSVC deque usually uses block_size=1 for 16-byte shared_ptr<T>, but
    # packed/inlined builds can leave us needing a small layout probe.
    for map_addr, map_size, myoff, size, layout_name in layouts:
        if not (
            _looks_like_process_pointer(map_addr)
            and map_size
            and size
            and int(map_size) <= 0x10000
            and int(size) <= 10000
        ):
            raw_debug.append(
                f"{layout_name}: skip map={int(map_addr or 0):016X} "
                f"mapsize={int(map_size or 0)} off={int(myoff or 0)} size={int(size or 0)}"
            )
            continue

        limit = min(int(size), max(0, _cfg_int("MEMORY_ENTITY_MAX_READ", 80)))
        for block_size in (1, 2, 4, 8, 16):
          for ptr_delta in (0, 8):
            local_roles: list[MemoryEntity] = []
            local_debug: list[MemoryEntity] = []
            local_seen: set[int] = set()
            local_raw: list[str] = []

            for index in range(limit):
                logical_index = int(myoff or 0) + index
                block_index = (logical_index // block_size) % int(map_size)
                item_index = logical_index % block_size
                block_slot = int(map_addr) + block_index * 8
                block_ptr, block_err = _read_u64(proc, block_slot)
                if block_err or not _looks_like_process_pointer(block_ptr):
                    if len(local_raw) < 8:
                        raw_block = "?"
                        if block_ptr is not None:
                            raw_block = f"{int(block_ptr):016X}"
                        local_raw.append(f"{layout_name} bs{block_size}/d{ptr_delta} i{index}: block={raw_block}")
                    continue

                shared_ptr_addr = int(block_ptr) + item_index * shared_ptr_size + ptr_delta
                role_ptr, role_err = _read_u64(proc, shared_ptr_addr)
                if role_err or not _looks_like_process_pointer(role_ptr):
                    if len(local_raw) < 8:
                        raw_role = "?"
                        if role_ptr is not None:
                            raw_role = f"{int(role_ptr):016X}"
                        local_raw.append(
                            f"{layout_name} bs{block_size}/d{ptr_delta} i{index}: "
                            f"blk={int(block_ptr):016X} role={raw_role}"
                        )
                    continue
                if int(role_ptr) in local_seen:
                    continue
                local_seen.add(int(role_ptr))
                role = _read_coclassic_role(proc, int(role_ptr))
                if not role:
                    if len(local_raw) < 8:
                        local_raw.append(
                            f"{layout_name} bs{block_size}/d{ptr_delta} i{index}: role={int(role_ptr):016X} unread"
                        )
                    continue

                if len(local_debug) < 12:
                    local_debug.append(role)
                if _is_coclassic_monster(role.entity_id, role.name, role.state):
                    local_roles.append(role)

            if len(local_debug) > len(debug_roles):
                roles = local_roles
                debug_roles = local_debug
                best_meta = (int(map_addr), int(map_size), int(myoff), int(size), layout_name, block_size, ptr_delta)
                raw_debug.append(f"BEST {layout_name} block={block_size} delta={ptr_delta}")
                raw_debug.extend(local_raw)
            elif local_raw and len(raw_debug) < 14:
                raw_debug.append(f"TRY {layout_name} block={block_size} delta={ptr_delta}")
                raw_debug.extend(local_raw[:3])

    if best_meta:
        map_addr, map_size, myoff, size, layout_name, block_size, ptr_delta = best_meta
        snapshot.coclassic_deque_map = map_addr
        snapshot.coclassic_deque_map_size = map_size
        snapshot.coclassic_deque_offset = myoff
        snapshot.coclassic_deque_size = size
        raw_debug.insert(1, f"using {layout_name} block={block_size} delta={ptr_delta} size={size}")

    snapshot.coclassic_deque_debug = raw_debug[:18]

    return roles, debug_roles


def _update_nearby_entities(snapshot: MemorySnapshot) -> None:
    max_range = max(0, _cfg_int("MEMORY_MOB_NEARBY_RANGE", 20))
    nearby: list[MemoryEntity] = []
    for entity in snapshot.entities:
        entity.distance = _chebyshev_distance(
            snapshot.coclassic_hero_x,
            snapshot.coclassic_hero_y,
            entity.x,
            entity.y,
        )
        if entity.distance is not None and entity.distance <= max_range:
            nearby.append(entity)
    nearby.sort(key=lambda e: (999999 if e.distance is None else e.distance, e.entity_id or 0))
    snapshot.nearby_entities = nearby


def _read_coclassic_debug(proc: str, snapshot: MemorySnapshot) -> None:
    if not _cfg_bool("MEMORY_COCLASSIC_DEBUG_ENABLED", True):
        return

    module = str(getattr(config, "MEMORY_COCLASSIC_MODULE", "") or "")
    role_mgr_offset = _cfg_int("MEMORY_COCLASSIC_ROLE_MGR_OFFSET", 0)
    if not module or not role_mgr_offset:
        return

    module_base, err = game_memory.get_module_base(proc, module)
    if err or not module_base:
        snapshot.error = snapshot.error or f"coclassic module: {err}"
        return

    role_mgr = int(module_base) + role_mgr_offset
    snapshot.coclassic_role_mgr = role_mgr

    hero_offset = _cfg_int("MEMORY_COCLASSIC_ROLE_MGR_HERO_OFFSET", 0)
    hero, hero_err = _read_u64(proc, role_mgr + hero_offset)
    if hero_err or not hero:
        snapshot.error = snapshot.error or f"coclassic hero: {hero_err or 'puntero nulo'}"
        return

    snapshot.coclassic_hero = int(hero)
    id_offset = _cfg_int("MEMORY_COCLASSIC_ROLE_ID_OFFSET", 0x68)
    name_offset = _cfg_int("MEMORY_COCLASSIC_ROLE_NAME_OFFSET", 0x94)
    name_size = _cfg_int("MEMORY_COCLASSIC_ROLE_NAME_SIZE", 16)
    x_offset = _cfg_int("MEMORY_COCLASSIC_ROLE_X_OFFSET", 0xD8)
    y_offset = _cfg_int("MEMORY_COCLASSIC_ROLE_Y_OFFSET", 0xDC)
    status_offset = _cfg_int("MEMORY_COCLASSIC_ROLE_STATUS_OFFSET", 0x30)
    max_hp_offset = _cfg_int("MEMORY_COCLASSIC_ROLE_MAX_HP_OFFSET", 0x3D0)
    stamina_offset = _cfg_int("MEMORY_COCLASSIC_ROLE_STAMINA_OFFSET", 0x6E0)
    max_stamina_offset = _cfg_int("MEMORY_COCLASSIC_ROLE_MAX_STAMINA_OFFSET", 0x6E4)
    stat_table_offset = _cfg_int("MEMORY_COCLASSIC_HERO_STAT_TABLE_OFFSET", 0x968)
    max_mana_offset = _cfg_int("MEMORY_COCLASSIC_HERO_MAX_MANA_OFFSET", 0xCA8)
    max_mana_valid_offset = _cfg_int("MEMORY_COCLASSIC_HERO_MAX_MANA_VALID_OFFSET", 0xCAC)

    snapshot.coclassic_hero_id, _ = _read_u32(proc, hero + id_offset)
    snapshot.coclassic_hero_name, _ = game_memory.read_c_string_at(proc, hero + name_offset, name_size)
    snapshot.coclassic_hero_x, _ = _read_i32(proc, hero + x_offset)
    snapshot.coclassic_hero_y, _ = _read_i32(proc, hero + y_offset)
    snapshot.coclassic_hero_status, _ = _read_u64(proc, hero + status_offset)
    status_value = int(snapshot.coclassic_hero_status or 0)
    snapshot.coclassic_hero_xp_ready = bool(status_value & (1 << 4))
    snapshot.coclassic_hero_dead = bool(status_value & (1 << 5))
    snapshot.coclassic_hero_max_hp, _ = _read_i32(proc, hero + max_hp_offset)
    snapshot.coclassic_hero_stamina, _ = _read_i32(proc, hero + stamina_offset)
    snapshot.coclassic_hero_max_stamina, _ = _read_i32(proc, hero + max_stamina_offset)
    snapshot.coclassic_hero_stat_table, _ = _read_u64(proc, hero + stat_table_offset)
    snapshot.coclassic_hero_max_mana, _ = _read_i32(proc, hero + max_mana_offset)
    snapshot.coclassic_hero_max_mana_valid, _ = _read_u8(proc, hero + max_mana_valid_offset)

    deque = role_mgr + _cfg_int("MEMORY_COCLASSIC_ROLE_MGR_DEQUE_OFFSET", 0x70)
    snapshot.coclassic_deque_map, _ = _read_u64(proc, deque + 0x00)
    snapshot.coclassic_deque_map_size, _ = _read_u64(proc, deque + 0x08)
    snapshot.coclassic_deque_offset, _ = _read_u64(proc, deque + 0x10)
    snapshot.coclassic_deque_size, _ = _read_u64(proc, deque + 0x18)
    snapshot.entities, snapshot.coclassic_roles_debug = _read_coclassic_roles(proc, snapshot)
    snapshot.coclassic_roles_read = len(snapshot.entities)
    _read_coclassic_inventory(proc, int(hero), snapshot)
    _update_nearby_entities(snapshot)


def read_snapshot() -> MemorySnapshot:
    proc = str(getattr(config, "GAME_PROCESS_NAME", "") or "").strip()
    snapshot = MemorySnapshot()
    if not proc:
        snapshot.error = "GAME_PROCESS_NAME vacio"
        return snapshot

    player_base = _resolve_player_base(proc, snapshot)
    snapshot.player_base = player_base

    if player_base:
        id_offset = _cfg_int("MEMORY_PLAYER_ID_OFFSET", 0x190)
        x_offset = _cfg_int("MEMORY_PLAYER_X_OFFSET", 0x4)
        y_offset = _cfg_int("MEMORY_PLAYER_Y_OFFSET", 0x8)
        coord_shift = _cfg_int("MEMORY_PLAYER_COORD_SHIFT", 6)

        snapshot.player_id_address = player_base + id_offset
        snapshot.player_id, _ = _read_u32(proc, snapshot.player_id_address)
        snapshot.player_x = _read_coord(proc, player_base, x_offset, coord_shift)
        snapshot.player_y = _read_coord(proc, player_base, y_offset, coord_shift)
        snapshot.entities = _read_entities(proc, player_base)

    _read_coclassic_debug(proc, snapshot)
    snapshot.drops = _read_drops(proc)
    snapshot.ok = bool(
        player_base
        or snapshot.coclassic_hero
        or snapshot.entities
        or snapshot.drops
    )
    if not snapshot.ok and not snapshot.error:
        snapshot.error = "Sin direcciones externas configuradas"
    return snapshot
