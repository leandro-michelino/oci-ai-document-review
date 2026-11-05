from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from src.model_catalog import available_chat_model_ids


def model(
    name="cohere.command-a-03-2025",
    *,
    region="uk-london-1",
    modes=None,
    retired=None,
    access="HOSTED",
    capabilities=None
):
    return SimpleNamespace(
        model_id=name,
        model_access=access,
        capabilities=capabilities or ["CHAT"],
        availability=[
            SimpleNamespace(
                region=region,
                serving_modes=modes or ["ON_DEMAND"],
                time_on_demand_retired=retired,
            )
        ],
    )


def test_catalog_filters_region_serving_mode_vendor_and_retirement():
    items = [
        model(),
        model(region="us-chicago-1"),
        model(modes=["DEDICATED"]),
        model(retired=datetime.now(timezone.utc) - timedelta(days=1)),
        model(access="PROXY"),
        model("meta.llama-test"),
        model(capabilities=["TEXT_EMBEDDINGS"]),
    ]
    assert available_chat_model_ids(items, "uk-london-1") == [
        "cohere.command-a-03-2025"
    ]


def test_catalog_accepts_future_retirement_and_deduplicates():
    item = model(retired=datetime.now(timezone.utc) + timedelta(days=30))
    assert available_chat_model_ids([item, item], "uk-london-1") == [item.model_id]
