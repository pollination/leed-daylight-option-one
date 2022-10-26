from pollination.leed_daylight_option_one.entry import LeedDaylightOptionIEntryPoint
from queenbee.recipe.dag import DAG


def test_leed_daylight_option_I():
    recipe = LeedDaylightOptionIEntryPoint().queenbee
    assert recipe.name == 'leed-daylight-option-i-entry-point'
    assert isinstance(recipe, DAG)
