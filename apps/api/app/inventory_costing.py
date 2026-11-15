from decimal import Decimal, ROUND_HALF_UP

CENT = Decimal("0.01")


def _money(value: Decimal) -> Decimal:
    return Decimal(value).quantize(CENT, rounding=ROUND_HALF_UP)


def _value(row, key):
    if isinstance(row, dict):
        return Decimal(row.get(key) or 0)
    return Decimal(getattr(row, key) or 0)


def replay_fifo_layers(movements):
    """Rebuild remaining FIFO receipt layers from chronologically ordered ledger rows."""
    layers = []
    for movement in movements:
        quantity_in = _value(movement, "quantity_in")
        quantity_out = _value(movement, "quantity_out")
        unit_cost = _value(movement, "unit_cost")
        if quantity_in < 0 or quantity_out < 0:
            raise ValueError("negative stock movement quantity")
        if quantity_in and quantity_out:
            raise ValueError("a stock movement cannot be both a receipt and an issue")
        if quantity_in:
            layers.append({"quantity": quantity_in, "unit_cost": unit_cost})
        if quantity_out:
            issue_fifo_layers(layers, quantity_out)
    return layers


def issue_fifo_layers(layers, quantity: Decimal) -> Decimal:
    """Consume oldest receipt layers and return the rounded extended FIFO cost."""
    remaining = Decimal(quantity)
    if remaining <= 0:
        raise ValueError("FIFO issue quantity must be positive")
    available = sum((layer["quantity"] for layer in layers), Decimal("0"))
    if available < remaining:
        raise ValueError(f"Insufficient FIFO quantity: requested {remaining}, available {available}")
    total = Decimal("0")
    for layer in layers:
        if remaining == 0:
            break
        taken = min(layer["quantity"], remaining)
        total += taken * layer["unit_cost"]
        layer["quantity"] -= taken
        remaining -= taken
    layers[:] = [layer for layer in layers if layer["quantity"] > 0]
    return _money(total)


def fifo_layer_totals(layers):
    quantity = sum((layer["quantity"] for layer in layers), Decimal("0"))
    value = _money(sum((layer["quantity"] * layer["unit_cost"] for layer in layers), Decimal("0")))
    return quantity, value
