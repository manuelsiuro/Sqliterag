"""Inventory and item management tools (Phase 4)."""

from __future__ import annotations

from app.services.builtin_tools._common import (
    AsyncSession,
    calculate_modifier,
    get_character_by_name,
    get_or_create_session,
    json,
    select,
)


async def create_item(
    name: str,
    item_type: str = "misc",
    description: str = "",
    weight: float = 0.0,
    value_gp: int = 0,
    properties: str = "{}",
    rarity: str = "common",
    *,
    session: AsyncSession,
    conversation_id: str,
) -> str:
    """Create a new item template."""
    from app.models.rpg import Item

    # Check for duplicate
    result = await session.execute(select(Item).where(Item.name.ilike(name)))
    existing = result.scalars().first()
    if existing:
        return json.dumps({"type": "item_detail", "error": f"Item '{name}' already exists."})

    item = Item(
        name=name,
        item_type=item_type,
        description=description,
        weight=weight,
        value_gp=value_gp,
        properties=properties if isinstance(properties, str) else json.dumps(properties),
        rarity=rarity,
    )
    session.add(item)
    await session.flush()

    return json.dumps({
        "type": "item_detail",
        "name": item.name,
        "item_type": item.item_type,
        "description": item.description,
        "weight": item.weight,
        "value_gp": item.value_gp,
        "properties": json.loads(item.properties),
        "rarity": item.rarity,
    })


async def give_item(
    character: str,
    item_name: str,
    quantity: int = 1,
    *,
    session: AsyncSession,
    conversation_id: str,
) -> str:
    """Give an item to a character's inventory."""
    from app.models.rpg import InventoryItem, Item

    gs = await get_or_create_session(session, conversation_id)
    char = await get_character_by_name(session, gs.id, character)
    if not char:
        return json.dumps({"type": "inventory", "error": f"Character '{character}' not found."})

    result = await session.execute(select(Item).where(Item.name.ilike(item_name)))
    item = result.scalars().first()
    if not item:
        return json.dumps({"type": "inventory", "error": f"Item '{item_name}' not found. Create it first with create_item."})

    # Check if already in inventory
    result = await session.execute(
        select(InventoryItem).where(
            InventoryItem.character_id == char.id,
            InventoryItem.item_id == item.id,
        )
    )
    inv_item = result.scalars().first()
    if inv_item:
        inv_item.quantity += quantity
    else:
        inv_item = InventoryItem(character_id=char.id, item_id=item.id, quantity=quantity)
        session.add(inv_item)

    await session.flush()
    return await get_inventory(character, session=session, conversation_id=conversation_id)


async def equip_item(
    character: str,
    item_name: str,
    *,
    session: AsyncSession,
    conversation_id: str,
) -> str:
    """Equip an item from inventory. Updates AC for armor."""
    from app.models.rpg import InventoryItem, Item

    gs = await get_or_create_session(session, conversation_id)
    char = await get_character_by_name(session, gs.id, character)
    if not char:
        return json.dumps({"type": "inventory", "error": f"Character '{character}' not found."})

    result = await session.execute(
        select(InventoryItem).join(Item).where(
            InventoryItem.character_id == char.id,
            Item.name.ilike(item_name),
        )
    )
    inv_item = result.scalars().first()
    if not inv_item:
        return json.dumps({"type": "inventory", "error": f"'{item_name}' not in {character}'s inventory."})

    inv_item.is_equipped = True

    # If armor, update AC
    result = await session.execute(select(Item).where(Item.id == inv_item.item_id))
    item = result.scalars().first()
    if item and item.item_type == "armor":
        props = json.loads(item.properties)
        if "ac" in props:
            dex_mod = calculate_modifier(char.dexterity)
            max_dex = props.get("max_dex_bonus")
            effective_dex = min(dex_mod, max_dex) if max_dex is not None else dex_mod
            char.armor_class = props["ac"] + effective_dex

    await session.flush()
    return await get_inventory(character, session=session, conversation_id=conversation_id)


async def unequip_item(
    character: str,
    item_name: str,
    *,
    session: AsyncSession,
    conversation_id: str,
) -> str:
    """Unequip an item. Resets AC if armor."""
    from app.models.rpg import InventoryItem, Item

    gs = await get_or_create_session(session, conversation_id)
    char = await get_character_by_name(session, gs.id, character)
    if not char:
        return json.dumps({"type": "inventory", "error": f"Character '{character}' not found."})

    result = await session.execute(
        select(InventoryItem).join(Item).where(
            InventoryItem.character_id == char.id,
            Item.name.ilike(item_name),
        )
    )
    inv_item = result.scalars().first()
    if not inv_item:
        return json.dumps({"type": "inventory", "error": f"'{item_name}' not in {character}'s inventory."})

    result = await session.execute(select(Item).where(Item.id == inv_item.item_id))
    item = result.scalars().first()

    inv_item.is_equipped = False

    # Reset AC if it was armor
    if item and item.item_type == "armor":
        dex_mod = calculate_modifier(char.dexterity)
        char.armor_class = 10 + dex_mod

    await session.flush()
    return await get_inventory(character, session=session, conversation_id=conversation_id)


async def get_inventory(
    character: str,
    *,
    session: AsyncSession,
    conversation_id: str,
) -> str:
    """Get a character's full inventory with weight and capacity."""
    from app.models.rpg import InventoryItem, Item

    gs = await get_or_create_session(session, conversation_id)
    char = await get_character_by_name(session, gs.id, character)
    if not char:
        return json.dumps({"type": "inventory", "error": f"Character '{character}' not found."})

    result = await session.execute(
        select(InventoryItem, Item)
        .join(Item)
        .where(InventoryItem.character_id == char.id)
    )
    rows = result.all()

    items = []
    total_weight = 0.0
    total_value = 0
    for inv_item, item in rows:
        item_weight = item.weight * inv_item.quantity
        total_weight += item_weight
        total_value += item.value_gp * inv_item.quantity
        items.append({
            "name": item.name,
            "item_type": item.item_type,
            "quantity": inv_item.quantity,
            "weight_each": item.weight,
            "weight_total": item_weight,
            "value_gp": item.value_gp,
            "is_equipped": inv_item.is_equipped,
            "rarity": item.rarity,
        })

    capacity = char.strength * 15

    return json.dumps({
        "type": "inventory",
        "character": char.name,
        "items": items,
        "total_weight": round(total_weight, 1),
        "capacity": capacity,
        "encumbered": total_weight > capacity,
        "total_value_gp": total_value,
    })


async def transfer_item(
    from_character: str,
    to_character: str,
    item_name: str,
    quantity: int = 1,
    *,
    session: AsyncSession,
    conversation_id: str,
) -> str:
    """Transfer items between characters."""
    from app.models.rpg import InventoryItem, Item

    gs = await get_or_create_session(session, conversation_id)
    from_char = await get_character_by_name(session, gs.id, from_character)
    to_char = await get_character_by_name(session, gs.id, to_character)
    if not from_char:
        return json.dumps({"type": "inventory", "error": f"Character '{from_character}' not found."})
    if not to_char:
        return json.dumps({"type": "inventory", "error": f"Character '{to_character}' not found."})

    result = await session.execute(
        select(InventoryItem).join(Item).where(
            InventoryItem.character_id == from_char.id,
            Item.name.ilike(item_name),
        )
    )
    inv_item = result.scalars().first()
    if not inv_item or inv_item.quantity < quantity:
        return json.dumps({"type": "inventory", "error": f"'{from_character}' doesn't have {quantity}x {item_name}."})

    # Remove from source
    inv_item.quantity -= quantity
    if inv_item.quantity <= 0:
        await session.delete(inv_item)

    # Add to target
    result = await session.execute(
        select(InventoryItem).where(
            InventoryItem.character_id == to_char.id,
            InventoryItem.item_id == inv_item.item_id,
        )
    )
    tgt_inv = result.scalars().first()
    if tgt_inv:
        tgt_inv.quantity += quantity
    else:
        new_inv = InventoryItem(character_id=to_char.id, item_id=inv_item.item_id, quantity=quantity)
        session.add(new_inv)

    await session.flush()

    return json.dumps({
        "type": "transfer_result",
        "from": from_character,
        "to": to_character,
        "item": item_name,
        "quantity": quantity,
        "message": f"Transferred {quantity}x {item_name} from {from_character} to {to_character}.",
    })
