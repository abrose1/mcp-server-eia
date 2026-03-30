from mcp_server_eia.mappings import seds_co2_series_id
from mcp_server_eia.plant_id import parse_plant_id


def test_parse_plant_id_ok():
    assert parse_plant_id("OH-3470") == ("OH", "3470")


def test_parse_plant_id_rejects_bare_number():
    try:
        parse_plant_id("3470")
        assert False
    except ValueError:
        pass


def test_seds_co2_series_total():
    assert seds_co2_series_id("total", "total") == "TETCE"


def test_seds_co2_series_coal_electric():
    assert seds_co2_series_id("electric_power", "coal") == "CLEIE"
