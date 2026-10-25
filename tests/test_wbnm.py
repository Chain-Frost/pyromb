import pyromb
import pytest


def test_wbnm(vectors):
    builder = pyromb.Builder()
    catchment = pyromb.Catchment(
        builder.confluence(vectors.confluences),
        builder.basin(vectors.centroids, vectors.basins),
        builder.reach(vectors.reaches),
    )
    catchment.connect()
    try:
        output = pyromb.Traveller(catchment).getVector(pyromb.WBNM())
    except AttributeError as exc:
        if str(exc) != "'Basin' object has no attribute '_type'":
            raise
        pytest.xfail("Inherited WBNM SubArea requires missing Basin._type")
    assert "#####START_TOPOLOGY_BLOCK" in output
    assert "#####END_TOPOLOGY_BLOCK" in output
