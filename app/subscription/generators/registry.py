from app.subscription.contracts import SubscriptionGenerator
from app.subscription.generators.outline import OutlineSubscriptionGenerator
from app.subscription.generators.singbox import SingBoxSubscriptionGenerator
from app.subscription.generators.uri import UriSubscriptionGenerator
from app.subscription.generators.xray_json import XrayJsonSubscriptionGenerator
from app.subscription.generators.yaml import ClashSubscriptionGenerator, MihomoSubscriptionGenerator


class GeneratorRegistry:
    generators = {
        "v2ray": UriSubscriptionGenerator,
        "v2ray-json": XrayJsonSubscriptionGenerator,
        "clash": ClashSubscriptionGenerator,
        "mihomo": MihomoSubscriptionGenerator,
        "sing-box": SingBoxSubscriptionGenerator,
        "outline": OutlineSubscriptionGenerator,
    }

    def for_target(self, target: str) -> SubscriptionGenerator:
        return self.generators[target]()
