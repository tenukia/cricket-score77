import pytest
import tempfile
import json
import os

from your_module import CricketDataManager


def test_get_default_data():
    # Test to check if default data is loaded correctly
    manager = CricketDataManager()
    default_data = manager.get_default_data()
    assert default_data == expected_data_structure


def test_load_data_returns_default():
    # Test loading data returns default when data file is missing
    manager = CricketDataManager()
    with tempfile.NamedTemporaryFile(delete=False) as temp_file:
        assert manager.load_data(temp_file.name) == manager.get_default_data()


def test_save_data():
    # Test saving data correctly
    manager = CricketDataManager()
    data_to_save = {'key': 'value'}
    with tempfile.NamedTemporaryFile(delete=False) as temp_file:
        manager.save_data(temp_file.name, data_to_save)
        with open(temp_file.name, 'r') as file:
            saved_data = json.load(file)
        assert saved_data == data_to_save


def test_calculate_run_rate():
    # Test run rate calculation
    manager = CricketDataManager()
    run_rate = manager.calculate_run_rate(200, 50)
    assert run_rate == 4.0


def test_calculate_run_rate_zero_balls():
    # Test run rate calculation with zero balls
    manager = CricketDataManager()
    run_rate = manager.calculate_run_rate(200, 0)
    assert run_rate == 0


def test_format_overs():
    # Test correct formatting of overs
    manager = CricketDataManager()
    formatted_overs = manager.format_overs(10)
    assert formatted_overs == '10.0'


def test_batting_stats_initialization():
    # Test batting stats are initialized correctly
    player_stats = manager.initialize_batting_stats()
    assert player_stats['runs'] == 0


def test_bowling_stats_initialization():
    # Test bowling stats are initialized correctly
    player_stats = manager.initialize_bowling_stats()
    assert player_stats['wickets'] == 0


def test_add_player_to_squad():
    # Test adding a player to the squad
    manager = CricketDataManager()
    player = {'name': 'John Doe'}
    manager.add_player_to_squad(player)
    assert player in manager.squad


def test_load_corrupted_json():
    # Test loading a corrupted JSON file
    manager = CricketDataManager()
    with tempfile.NamedTemporaryFile(delete=False) as temp_file:
        temp_file.write(b'\x00')  # corrupted json
        temp_file.flush()
        assert manager.load_data(temp_file.name) == manager.get_default_data()


def test_man_of_match_by_runs():
    # Test determining the man of the match by runs
    manager = CricketDataManager()
    man_of_the_match = manager.man_of_match(['player1', 'player2'], by='runs')
    assert man_of_the_match == 'expected_player_name'


def test_man_of_match_by_wickets():
    # Test determining the man of the match by wickets
    manager = CricketDataManager()
    man_of_the_match = manager.man_of_match(['player1', 'player2'], by='wickets')
    assert man_of_the_match == 'expected_player_name'