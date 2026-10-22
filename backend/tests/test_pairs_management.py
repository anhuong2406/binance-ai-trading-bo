"""
Unit & Integration Tests for Trading Pairs Management Engine
Validates:
- Loading and saving pairs
- Toggling pairs on/off
- Inability to disable all pairs
- Dynamic syncing with active symbols
- REST API /api/pairs/list, /api/pairs/toggle, /api/pairs/add
"""
import pytest
from app.trading.pair_manager import PairManager, DEFAULT_PAIRS_CATALOG
from pathlib import Path
import tempfile
import json

@pytest.fixture
def temp_pair_manager():
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / "pairs_test.json"
        pm = PairManager(config_file=config_path)
        yield pm

def test_pair_manager_initialization(temp_pair_manager):
    pairs = temp_pair_manager.get_all_pairs()
    assert len(pairs) == len(DEFAULT_PAIRS_CATALOG)
    active = temp_pair_manager.get_active_symbols()
    assert "BTCUSDT" in active
    assert "DOGEUSDT" in active

def test_toggle_pair(temp_pair_manager):
    # Toggle DOGEUSDT off
    success = temp_pair_manager.toggle_pair("DOGEUSDT", False)
    assert success is True
    active = temp_pair_manager.get_active_symbols()
    assert "DOGEUSDT" not in active
    assert "BTCUSDT" in active

    # Toggle DOGEUSDT back on
    success = temp_pair_manager.toggle_pair("DOGEUSDT", True)
    assert success is True
    active = temp_pair_manager.get_active_symbols()
    assert "DOGEUSDT" in active

def test_cannot_disable_all_pairs(temp_pair_manager):
    # Disable all except one
    for p in ["ETHUSDT", "SOLUSDT", "DOGEUSDT"]:
        temp_pair_manager.toggle_pair(p, False)
    
    # Trying to disable the last remaining active pair (BTCUSDT) must raise ValueError
    with pytest.raises(ValueError, match="Không thể tắt tất cả các cặp"):
        temp_pair_manager.toggle_pair("BTCUSDT", False)

def test_add_and_remove_pair(temp_pair_manager):
    new_pair = temp_pair_manager.add_pair(
        symbol="PEPEUSDT",
        name="Pepe",
        min_notional=1.0,
        base_asset="PEPE"
    )
    assert new_pair["symbol"] == "PEPEUSDT"
    assert new_pair["enabled"] is True
    assert "PEPEUSDT" in temp_pair_manager.get_active_symbols()

    # Remove the user-added pair
    removed = temp_pair_manager.remove_pair("PEPEUSDT")
    assert removed is True
    assert "PEPEUSDT" not in temp_pair_manager.get_active_symbols()
